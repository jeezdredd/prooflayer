import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from analyzers.manipulation.fusion import FusionConfig, fuse
from analyzers.manipulation.regions import texture_map
from evaluate import ROOT, gt_mask, load_cache, to_outputs

PANEL = 320


def heat(prob: np.ndarray | None, shape) -> Image.Image:
    if prob is None:
        return Image.new("RGB", (shape[1], shape[0]), (40, 40, 40))
    u8 = np.clip(prob * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.applyColorMap(u8, cv2.COLORMAP_INFERNO)[:, :, ::-1])


def overlay(rgb: np.ndarray, fmap: np.ndarray | None, regions, shape) -> Image.Image:
    base = Image.fromarray(cv2.resize(rgb, (shape[1], shape[0]), interpolation=cv2.INTER_AREA)).convert("RGB")
    if fmap is not None:
        red = np.zeros((shape[0], shape[1], 4), dtype=np.uint8)
        red[..., 0] = 255
        red[..., 1] = 80
        red[..., 3] = (np.clip(fmap, 0, 1) * 150).astype(np.uint8)
        base = Image.alpha_composite(base.convert("RGBA"), Image.fromarray(red)).convert("RGB")
    return base


def fit(img: Image.Image) -> Image.Image:
    img = img.copy()
    img.thumbnail((PANEL, PANEL))
    canvas = Image.new("RGB", (PANEL, PANEL), (20, 20, 20))
    canvas.paste(img, ((PANEL - img.width) // 2, (PANEL - img.height) // 2))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(ROOT / "eval_results.json"))
    parser.add_argument("--config", default="full")
    parser.add_argument("--out", default=str(ROOT / "panels"))
    parser.add_argument("--per-group", type=int, default=6)
    args = parser.parse_args()
    results = json.loads(Path(args.results).read_text())
    cfg = FusionConfig(**results["configs"][args.config]["fitted_config"])
    rows = results["configs"][args.config]["rows"]
    items = {it["id"]: it for it in json.loads((ROOT / "index.json").read_text())}
    groups = {
        "false_alarm": [r for r in rows if r["label"] == "authentic" and r["shown"]],
        "hit": [r for r in rows if r["label"] == "manipulated" and r["shown"] and r.get("iou", 0) >= 0.3],
        "miss": [r for r in rows if r["label"] == "manipulated" and not r["shown"] and r["variant"] == "original"],
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for group, rs in groups.items():
        for r in rs[: args.per_group]:
            it = items[r["id"]]
            d = load_cache(r["id"])
            o = to_outputs(d)
            rgb = np.asarray(Image.open(it["path"]).convert("RGB"))
            o.texture = texture_map(rgb, o.shape)
            res = fuse(o, cfg)
            gt = gt_mask(it, o.shape)
            tiles = [
                fit(Image.fromarray(rgb)),
                fit(heat(gt.astype(np.float32) if gt is not None else None, o.shape)),
                fit(heat(o.catnet, o.shape)),
                fit(heat(o.safire, o.shape)),
                fit(overlay(rgb, res.map, res.regions, o.shape)),
            ]
            panel = Image.new("RGB", (PANEL * len(tiles), PANEL + 24), (0, 0, 0))
            for i, t in enumerate(tiles):
                panel.paste(t, (i * PANEL, 24))
            ImageDraw.Draw(panel).text(
                (6, 4), f"{group} | {r['subset']} {r['variant']} | {res.status} {res.reason} | {[g.kind for g in res.regions]}", fill=(255, 255, 255)
            )
            panel.save(out / f"{group}__{r['id'][:120]}.jpg", quality=85)
    print(f"panels in {out}")


if __name__ == "__main__":
    main()
