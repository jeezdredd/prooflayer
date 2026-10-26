import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from evaluate import wilson_upper

ROOT = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation")
MIN_SHORT = 384


def pct(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{100 * x:.1f}%"


def num(x: float, digits: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.{digits}f}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def pooled(rows: list[dict], label: str, variant: str, splits: tuple) -> dict:
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["label"] != label or r["variant"] != variant or r["split"] not in splits:
            continue
        by[r["subset"]][0] += 1
        by[r["subset"]][1] += int(r["shown"])
    return by


def mappable(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("orig_short", 10**6) >= MIN_SHORT]


def fp_section(results: dict, config: str, splits=("test",)) -> str:
    rows = mappable(results["configs"][config]["rows"])
    by = pooled(rows, "authentic", "original", splits)
    lines = []
    tot_n = tot_k = 0
    for subset in sorted(by):
        n, k = by[subset]
        tot_n += n
        tot_k += k
        lines.append([subset, str(n), str(k), pct(k / n), pct(wilson_upper(k, n))])
    lines.append(["**all authentic**", str(tot_n), str(tot_k), pct(tot_k / max(tot_n, 1)), pct(wilson_upper(tot_k, tot_n))])
    return table(["subset", "n", "map shown", "rate", "Wilson 95% upper"], lines)


def variants_section(results: dict, config: str, label: str) -> str:
    rows = mappable(results["configs"][config]["rows"])
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["label"] != label or r["variant"] == "original":
            continue
        by[(r["variant"], r["subset"])][0] += 1
        by[(r["variant"], r["subset"])][1] += int(r["shown"])
    lines = []
    totals = defaultdict(lambda: [0, 0])
    for (variant, subset), (n, k) in sorted(by.items()):
        totals[variant][0] += n
        totals[variant][1] += k
        lines.append([variant, subset, str(n), str(k), pct(k / n)])
    for variant, (n, k) in sorted(totals.items()):
        lines.append([f"**{variant} all**", "", str(n), str(k), pct(k / n) + (f" (upper {pct(wilson_upper(k, n))})" if label == "authentic" else "")])
    return table(["variant", "subset", "n", "map shown", "rate"], lines)


def manip_section(results: dict, config: str, splits=("test",)) -> str:
    rows = results["configs"][config]["rows"]
    by = defaultdict(list)
    for r in rows:
        if r["label"] == "manipulated" and r["variant"] == "original" and r["split"] in splits:
            by[r["subset"]].append(r)
    lines = []
    for subset in sorted(by):
        g = by[subset]
        n = len(g)
        shown = [r for r in g if r["shown"]]
        gt = [r for r in g if "f1" in r]
        iou30 = sum(r["shown"] and r["iou"] >= 0.3 for r in gt) / len(gt) if gt else float("nan")
        f1_all = sum(r["f1"] for r in gt) / len(gt) if gt else float("nan")
        shown_gt = [r for r in gt if r["shown"]]
        f1_shown = sum(r["f1"] for r in shown_gt) / len(shown_gt) if shown_gt else float("nan")
        iou_shown = sum(r["iou"] for r in shown_gt) / len(shown_gt) if shown_gt else float("nan")
        abstain = sum(r["status"] == "abstain" for r in g)
        kinds = defaultdict(int)
        for r in shown:
            for k in r["kinds"]:
                kinds[k] += 1
        ai = sum(r["likely_ai"] for r in shown)
        lines.append(
            [
                subset,
                str(n),
                pct(len(shown) / n),
                pct(iou30),
                num(f1_all),
                num(f1_shown),
                num(iou_shown),
                pct(abstain / n),
                ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "-",
                str(ai),
            ]
        )
    return table(
        ["subset", "n", "map shown", "shown and IoU>=0.3", "pixel F1 (all)", "F1 (shown)", "IoU (shown)", "abstain", "region kinds", "likely-AI label"],
        lines,
    )


def method_section(results: dict) -> str:
    methods = results["methods"]
    subsets = sorted({s for m in methods.values() for s in m if s != "n_auth"})
    lines = []
    for name, res in methods.items():
        cells = [name, str(res.get("n_auth", 0))]
        for s in subsets:
            v = res.get(s, {})
            cells.append(f"{num(v.get('auc', float('nan')), 3)} (n={v.get('n', 0)})")
        lines.append(cells)
    return table(["method score", "n authentic"] + subsets, lines)


def pixel_section(results: dict, config: str, splits=("test",)) -> str:
    rows = results["configs"][config]["rows"]
    by = defaultdict(list)
    for r in rows:
        if r["label"] == "manipulated" and r["variant"] == "original" and r["split"] in splits and "f1" in r:
            by[r["subset"]].append(r)
    lines = []
    for subset in sorted(by):
        g = by[subset]
        def mean(key):
            vals = [r[key] for r in g if key in r]
            return sum(vals) / len(vals) if vals else float("nan")
        lines.append(
            [
                subset,
                str(len(g)),
                num(mean("catnet_f1_fixed")),
                num(mean("catnet_iou_fixed")),
                num(mean("catnet_f1_best")),
                num(mean("safire_f1_fixed")),
                num(mean("safire_iou_fixed")),
                num(mean("safire_f1_best")),
                num(mean("zero_f1_raw")),
                num(mean("copymove_f1_raw")),
            ]
        )
    return table(
        ["subset", "n", "CAT-Net F1@0.5", "CAT-Net IoU@0.5", "CAT-Net F1 best", "SAFIRE F1@0.5", "SAFIRE IoU@0.5", "SAFIRE F1 best", "ZERO F1 (raw)", "copy-move F1 (raw)"],
        lines,
    )


def runtime_section(results: dict) -> str:
    rt = results["runtime"]
    lines = []
    for name, buckets in rt.items():
        if not isinstance(buckets, dict):
            continue
        for b in ("<=1MP", "1-3MP", "3-8MP", ">8MP", "all"):
            v = buckets.get(b)
            if not v:
                continue
            lines.append([name, b, str(v["n"]), num(v["wall_median"], 1), num(v["wall_p90"], 1), num(v["cpu_median"], 1), num(v["cpu_p90"], 1)])
    return table(["method", "size", "n", "wall s median", "wall s p90", "CPU s median", "CPU s p90"], lines) + f"\n\nPeak RSS of one worker process (all models loaded): {num(rt.get('peak_rss_mb_max'), 0)} MB."


def calib_section(results: dict, config: str) -> str:
    lines = [["gates (from calibration-half positives)", json.dumps(results.get("gates", {}))]]
    for k, v in results["configs"][config]["calibration"].items():
        lines.append([k, json.dumps({a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})])
    return table(["parameter", "fitted on authentic calibration half"], lines)


def config_compare(results: dict, splits=("test",)) -> str:
    lines = []
    for config, data in results["configs"].items():
        rows = mappable(data["rows"])
        auth = [r for r in rows if r["label"] == "authentic" and r["variant"] == "original" and r["split"] in splits]
        k = sum(r["shown"] for r in auth)
        n = len(auth)
        worst = defaultdict(lambda: [0, 0])
        for r in auth:
            worst[r["subset"]][0] += 1
            worst[r["subset"]][1] += int(r["shown"])
        worst_rate = max((kk / nn for nn, kk in worst.values() if nn), default=0.0)
        man = [r for r in rows if r["label"] == "manipulated" and r["variant"] == "original" and r["split"] in splits]
        sp = [r for r in man if r["kind"] in ("ai_inpaint_spliced", "ai_local_edit", "copy_move")]
        fr = [r for r in man if r["kind"] == "ai_inpaint_regenerated"]
        tgif = [r for r in man if r["subset"] == "tgif_ps_sp" and "iou" in r]
        grip = [r for r in man if r["subset"] == "grip_copy"]
        lines.append(
            [
                config,
                f"{k}/{n} = {pct(k / max(n, 1))}",
                pct(wilson_upper(k, n)),
                pct(worst_rate),
                pct(sum(r["shown"] for r in sp) / max(len(sp), 1)),
                pct(sum(r["shown"] and r["iou"] >= 0.3 for r in tgif) / max(len(tgif), 1)),
                pct(sum(r["shown"] for r in grip) / max(len(grip), 1)),
                pct(sum(not r["shown"] for r in fr) / max(len(fr), 1)),
            ]
        )
    return table(
        ["config", "authentic map shown", "Wilson upper", "worst subset", "local edits shown", "TGIF PS-sp shown IoU>=0.3", "GRIP copy-move shown", "TGIF fully regenerated: no map"],
        lines,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(ROOT / "eval_results.json"))
    parser.add_argument("--config", default="full")
    args = parser.parse_args()
    results = json.loads(Path(args.results).read_text())
    parts = [
        "## Configurations compared (test half)",
        config_compare(results),
        f"## False alarms on authentic photos, config `{args.config}` (test half)",
        fp_section(results, args.config),
        f"## Authentic robustness copies, config `{args.config}` (thresholds never fitted on these)",
        variants_section(results, args.config, "authentic"),
        f"## Manipulated images, config `{args.config}` (test half)",
        manip_section(results, args.config),
        f"## Manipulated robustness copies, config `{args.config}`",
        variants_section(results, args.config, "manipulated"),
        "## Image-level AUC per method (test half, authentic originals as negatives)",
        method_section(results),
        "## Raw pixel scores per method (test half, before any gating)",
        pixel_section(results, args.config),
        "## Calibration",
        calib_section(results, args.config),
        "## Runtime (CPU only, shared machine)",
        runtime_section(results),
    ]
    print("\n\n".join(parts))


if __name__ == "__main__":
    main()
