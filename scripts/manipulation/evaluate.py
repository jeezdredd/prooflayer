import argparse
import gzip
import json
import math
import pickle
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from analyzers.manipulation.fusion import STATUS_REGIONS, FusionConfig, MethodOutputs, fuse, input_class_of
from analyzers.manipulation.regions import image_score

ROOT = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation")
LEARNED = ("catnet", "safire")
SPLIT_FIT = "calib"


def wilson_upper(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + margin) / denom


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    scores = np.array(list(pos) + list(neg), dtype=np.float64)
    labels = np.array([1] * len(pos) + [0] * len(neg))
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    rp = ranks[labels == 1].sum()
    return float((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def load_cache(item_id: str) -> dict | None:
    merged = None
    for sub in ("cache", "cache_safire", "cache_cm"):
        p = ROOT / sub / (item_id + ".pkl.gz")
        if not p.exists():
            continue
        with gzip.open(p, "rb") as fh:
            d = pickle.load(fh)
        if merged is None:
            merged = d
            merged["timings"] = dict(d.get("timings", {}))
            merged["extra"] = dict(d.get("extra", {}))
            merged["sources"] = [sub]
            continue
        merged["sources"].append(sub)
        if sub == "cache_safire" and d.get("safire") is not None:
            merged["safire"] = d["safire"]
            merged["extra"]["safire"] = d["extra"].get("safire")
            merged["timings"]["safire"] = d["timings"].get("safire")
        if sub == "cache_cm":
            merged["copymove_groups"] = d["copymove_groups"]
            merged["extra"]["copymove"] = d["extra"].get("copymove")
            merged["timings"]["copymove"] = d["timings"].get("copymove")
            merged["cm_fresh"] = True
    return merged


def unpack_mask(packed: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    n = shape[0] * shape[1]
    return np.unpackbits(packed)[:n].reshape(shape).astype(bool)


def to_outputs(d: dict, safire_mode: str = "binary") -> MethodOutputs:
    shape = tuple(d["shape"])
    out = MethodOutputs(shape=shape, orig_shape=tuple(d["orig_shape"]), is_jpeg=d["is_jpeg"], jpeg_quality=d["jpeg_quality"])
    if d.get("catnet") is not None:
        out.catnet = d["catnet"].astype(np.float32) / 255.0
    if d.get("safire") is not None:
        if safire_mode == "front" and d["extra"].get("safire") and d["extra"]["safire"].get("front") is not None:
            front = d["extra"]["safire"]["front"].astype(np.float32) / 255.0
            out.safire = cv2.resize(front, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)
        else:
            out.safire = d["safire"].astype(np.float32) / 255.0
    out.zero_main_grid = d.get("zero_main_grid")
    out.zero_regions = [dict(r, mask=unpack_mask(r["mask"], shape)) for r in d.get("zero_regions", [])]
    if d.get("cm_fresh"):
        out.copymove_groups = [
            dict(g, target_mask=unpack_mask(g["target_mask"], shape), source_mask=unpack_mask(g["source_mask"], shape))
            for g in d.get("copymove_groups", [])
        ]
    out.tile_boxes = d.get("tile_boxes")
    out.tile_scores = d.get("tile_scores")
    return out


def gt_mask(item: dict, shape: tuple[int, int]) -> np.ndarray | None:
    if not item.get("mask"):
        return None
    m = Image.open(item["mask"]).convert("L")
    m = np.asarray(m.resize((shape[1], shape[0]), Image.Resampling.NEAREST)) > 127
    return m


def pixel_scores(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float]:
    tp = float(np.logical_and(pred, gt).sum())
    fp = float(np.logical_and(pred, ~gt).sum())
    fn = float(np.logical_and(~pred, gt).sum())
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    return f1, iou


def zero_best(out: MethodOutputs, config: FusionConfig) -> float:
    best = 0.0
    h, w = out.shape
    for r in out.zero_regions:
        m = r["mask"]
        if m.mean() > config.zero_max_area:
            continue
        if r["kind"] == "missing_grid":
            o, i = r.get("main_density_outside", 0.0), r.get("main_density_inside", 0.0)
            if o < config.zero_missing_min_outside or o < config.zero_missing_ratio * i:
                continue
        best = min(best, r["log10_nfa"])
    return -best


def method_scores(out: MethodOutputs, config: FusionConfig) -> dict:
    s = {}
    for name in LEARNED:
        prob = getattr(out, name)
        if prob is not None:
            s[name] = image_score(prob, out.orig_shape)
    s["zero"] = zero_best(out, config)
    s["copymove"] = float(max((g["matches"] for g in out.copymove_groups), default=0))
    if out.tile_scores is not None and len(out.tile_scores):
        s["tiles_max"] = float(np.max(out.tile_scores))
    return s


def calibrate(records: list[dict], config: FusionConfig, fp_quantile: float, strong_quantile: float) -> tuple[FusionConfig, dict]:
    report = {}
    auth = [
        r
        for r in records
        if r["label"] == "authentic"
        and r["split"] == SPLIT_FIT
        and r["variant"] == "original"
        and r["orig_short"] >= config.min_short_side
    ]
    report["n_authentic_fit"] = {"n": len(auth)}
    for name in LEARNED:
        by_class = defaultdict(list)
        for r in auth:
            if name in r["scores"]:
                by_class[r["input_class"]].append(r["scores"][name])
                by_class["all"].append(r["scores"][name])
        config.t[name] = {}
        config.strong[name] = {}
        for cls, vals in by_class.items():
            vals = np.array(vals)
            if len(vals) < 50 and cls != "all":
                continue
            t = float(np.quantile(vals, fp_quantile))
            if len(vals) >= 1000:
                strong = float(np.quantile(vals, strong_quantile))
            else:
                strong = float(min(0.999, vals.max() + 0.02))
            config.t[name][cls] = max(t, 0.5)
            config.strong[name][cls] = max(strong, config.t[name][cls])
            report[f"{name}/{cls}"] = {"n": int(len(vals)), "t": config.t[name][cls], "strong": config.strong[name][cls]}
    tiles = []
    for r in auth:
        tiles.extend(r.get("tile_scores_list", []))
    if tiles:
        config.tile_threshold = float(max(np.quantile(tiles, 0.999), 0.5))
        report["tiles"] = {"n_tiles": len(tiles), "threshold": config.tile_threshold}
    zero_vals = [r["scores"]["zero"] for r in auth]
    if zero_vals:
        q = float(np.quantile(zero_vals, fp_quantile))
        config.zero_log10_nfa = -max(2.0, q + 1e-6)
        report["zero"] = {"n": len(zero_vals), "auth_q": q, "max": float(np.max(zero_vals)), "threshold_log10_nfa": config.zero_log10_nfa}
    cm_vals = [r["scores"]["copymove"] for r in auth if r.get("cm_fresh")]
    if cm_vals:
        q = float(np.quantile(cm_vals, fp_quantile))
        config.copymove_min_matches = int(max(2, math.floor(q) + 1))
        report["copymove"] = {"n": len(cm_vals), "auth_q": q, "max": float(np.max(cm_vals)), "min_matches": config.copymove_min_matches}
    return config, report


def evaluate(records, config, raw_by_id, label_tag):
    rows = []
    for r in records:
        out = raw_by_id[r["id"]]
        res = fuse(out, config)
        shown = res.status == STATUS_REGIONS
        row = {
            "id": r["id"],
            "subset": r["subset"],
            "variant": r["variant"],
            "label": r["label"],
            "kind": r["kind"],
            "split": r["split"],
            "status": res.status,
            "reason": res.reason,
            "shown": shown,
            "score": res.score,
            "kinds": sorted({g.kind for g in res.regions}),
            "confidences": sorted({g.confidence for g in res.regions}),
            "likely_ai": any(g.likely_ai for g in res.regions),
            "input_class": res.input_class,
            "orig_short": r["orig_short"],
        }
        if r["label"] == "manipulated" and r.get("gt") is not None:
            gt = r["gt"]
            pred = res.map > 0 if shown and res.map is not None else np.zeros_like(gt)
            row["f1"], row["iou"] = pixel_scores(pred, gt)
            for name in LEARNED:
                prob = getattr(out, name)
                if prob is not None:
                    row[f"{name}_f1_fixed"], row[f"{name}_iou_fixed"] = pixel_scores(prob >= 0.5, gt)
                    best = max(pixel_scores(prob >= t, gt)[0] for t in (0.3, 0.5, 0.7, 0.9))
                    row[f"{name}_f1_best"] = best
            zmask = np.zeros_like(gt)
            for zr in out.zero_regions:
                zmask |= zr["mask"]
            row["zero_f1_raw"] = pixel_scores(zmask, gt)[0]
            if out.copymove_groups:
                g = out.copymove_groups[0]
                row["copymove_f1_raw"] = pixel_scores(g["target_mask"] | g["source_mask"], gt)[0]
        rows.append(row)
    return rows


def summarize(rows, records, label_tag):
    by = defaultdict(list)
    for row in rows:
        by[(row["label"], row["subset"], row["variant"], row["split"])].append(row)
    out = []
    for key in sorted(by):
        group = by[key]
        n = len(group)
        k = sum(r["shown"] for r in group)
        entry = {"label": key[0], "subset": key[1], "variant": key[2], "split": key[3], "n": n, "shown": k, "shown_rate": k / n}
        entry["shown_wilson_upper"] = wilson_upper(k, n)
        entry["abstain"] = sum(r["status"] == "abstain" for r in group)
        entry["clean"] = sum(r["status"] == "no_local_edits" for r in group)
        entry["inconclusive"] = sum(r["status"] == "inconclusive" for r in group)
        if key[0] == "manipulated":
            with_gt = [r for r in group if "f1" in r]
            if with_gt:
                entry["n_gt"] = len(with_gt)
                entry["shown_iou30"] = sum(r["shown"] and r["iou"] >= 0.3 for r in with_gt) / len(with_gt)
                entry["mean_f1_all"] = float(np.mean([r["f1"] for r in with_gt]))
                shown_rows = [r for r in with_gt if r["shown"]]
                entry["mean_f1_shown"] = float(np.mean([r["f1"] for r in shown_rows])) if shown_rows else float("nan")
                entry["mean_iou_shown"] = float(np.mean([r["iou"] for r in shown_rows])) if shown_rows else float("nan")
                for name in LEARNED:
                    vals = [r[f"{name}_f1_fixed"] for r in with_gt if f"{name}_f1_fixed" in r]
                    if vals:
                        entry[f"{name}_f1_fixed"] = float(np.mean(vals))
                        entry[f"{name}_iou_fixed"] = float(np.mean([r[f"{name}_iou_fixed"] for r in with_gt if f"{name}_iou_fixed" in r]))
                        entry[f"{name}_f1_best"] = float(np.mean([r[f"{name}_f1_best"] for r in with_gt if f"{name}_f1_best" in r]))
                entry["zero_f1_raw"] = float(np.mean([r.get("zero_f1_raw", 0.0) for r in with_gt]))
                entry["copymove_f1_raw"] = float(np.mean([r.get("copymove_f1_raw", 0.0) for r in with_gt]))
            entry["kinds"] = dict(sorted(_count([k for r in group if r["shown"] for k in r["kinds"]]).items()))
            entry["likely_ai"] = sum(r["likely_ai"] for r in group if r["shown"])
        else:
            entry["kinds"] = dict(sorted(_count([k for r in group if r["shown"] for k in r["kinds"]]).items()))
            entry["reasons"] = dict(sorted(_count([r["reason"] for r in group]).items()))
        out.append(entry)
    return out


def _count(values):
    c = defaultdict(int)
    for v in values:
        c[v] += 1
    return c


def method_level(records):
    out = {}
    auth_test = [r for r in records if r["label"] == "authentic" and r["variant"] == "original" and r["split"] == "test"]
    manip = defaultdict(list)
    for r in records:
        if r["label"] == "manipulated" and r["variant"] == "original" and r["split"] == "test":
            manip[r["subset"]].append(r)
    for name in ("catnet", "safire", "safire_front", "zero", "copymove", "tiles_max"):
        neg = [r["scores"][name] for r in auth_test if name in r["scores"]]
        res = {"n_auth": len(neg)}
        for subset, rs in sorted(manip.items()):
            pos = [r["scores"][name] for r in rs if name in r["scores"]]
            res[subset] = {"n": len(pos), "auc": auc(pos, neg)}
        out[name] = res
    return out


def runtime(records, raws):
    rows = defaultdict(lambda: defaultdict(list))
    for r in records:
        d = raws[r["id"]]
        mp = d["orig_shape"][0] * d["orig_shape"][1] / 1e6
        bucket = "<=1MP" if mp <= 1.05 else "1-3MP" if mp <= 3 else "3-8MP" if mp <= 8 else ">8MP"
        for name, t in d.get("timings", {}).items():
            if t is None:
                continue
            rows[name][bucket].append(t)
            rows[name]["all"].append(t)
    out = {}
    for name, buckets in rows.items():
        out[name] = {}
        for b, vals in buckets.items():
            wall = np.array([v[0] for v in vals])
            cpu = np.array([v[1] for v in vals])
            out[name][b] = {
                "n": len(vals),
                "wall_median": float(np.median(wall)),
                "wall_p90": float(np.quantile(wall, 0.9)),
                "cpu_median": float(np.median(cpu)),
                "cpu_p90": float(np.quantile(cpu, 0.9)),
            }
    rss = [raws[r["id"]].get("maxrss_mb") for r in records if raws[r["id"]].get("maxrss_mb")]
    out["peak_rss_mb_max"] = float(max(rss)) if rss else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=str(ROOT / "index.json"))
    parser.add_argument("--out", default=str(ROOT / "eval_results.json"))
    parser.add_argument("--fp-quantile", type=float, default=0.995)
    parser.add_argument("--strong-quantile", type=float, default=0.999)
    parser.add_argument("--safire-mode", default="binary")
    parser.add_argument("--require", nargs="+", default=["catnet", "safire"])
    parser.add_argument("--configs", nargs="+", default=["full", "no_learned_single", "classical_only", "catnet_only", "pair_only"])
    args = parser.parse_args()

    items = json.loads(Path(args.index).read_text())
    records, raws, outs = [], {}, {}
    missing = defaultdict(int)
    for it in items:
        d = load_cache(it["id"])
        if d is None:
            missing["no_cache"] += 1
            continue
        if any(d.get(name) is None for name in args.require):
            missing["incomplete"] += 1
            continue
        out = to_outputs(d, args.safire_mode)
        rec = dict(it)
        rec["cm_fresh"] = bool(d.get("cm_fresh"))
        cfg0 = FusionConfig()
        rec["scores"] = method_scores(out, cfg0)
        if d["extra"].get("safire") and d["extra"]["safire"].get("front") is not None:
            front = d["extra"]["safire"]["front"].astype(np.float32) / 255.0
            rec["scores"]["safire_front"] = image_score(cv2.resize(front, (out.shape[1], out.shape[0])), out.orig_shape)
        rec["input_class"] = input_class_of(out, cfg0)
        rec["orig_short"] = min(out.orig_shape)
        rec["tile_scores_list"] = [] if out.tile_scores is None else [float(x) for x in out.tile_scores]
        rec["gt"] = gt_mask(it, out.shape) if it["label"] == "manipulated" else None
        records.append(rec)
        raws[it["id"]] = d
        outs[it["id"]] = out
    print(f"loaded {len(records)} records; skipped {dict(missing)}")

    base_config, calib_report = calibrate(records, FusionConfig(), args.fp_quantile, args.strong_quantile)
    variants = {
        "full": {},
        "no_learned_single": {"use_learned_single": False},
        "classical_only": {"use_learned_single": False, "use_learned_pair": False},
        "catnet_only": {"use_learned_pair": False, "use_zero": False, "use_copymove": False},
        "pair_only": {"use_learned_single": False, "use_zero": False, "use_copymove": False},
        "zero_only": {"use_learned_single": False, "use_learned_pair": False, "use_copymove": False},
        "copymove_only": {"use_learned_single": False, "use_learned_pair": False, "use_zero": False},
    }
    results = {
        "calibration": calib_report,
        "fitted_config": dict(base_config.__dict__),
        "configs": {},
        "methods": method_level(records),
        "runtime": runtime(records, raws),
    }
    for name in args.configs:
        cfg = FusionConfig(**{**base_config.__dict__, **variants[name]})
        if name == "catnet_only":
            cfg.strong = dict(cfg.strong)
            cfg.strong["safire"] = {"all": 2.0}
            cfg.t = dict(cfg.t)
            cfg.t["safire"] = {"all": 2.0}
        rows = evaluate(records, cfg, outs, name)
        results["configs"][name] = {"summary": summarize(rows, records, name), "rows": rows}
        print(f"config {name} done")
    Path(args.out).write_text(json.dumps(results, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    print(f"written {args.out}")


if __name__ == "__main__":
    main()
