import argparse
import hashlib
import io
import json
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation")
DERIVED = ROOT / "derived"
EXTRA_REAL = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/hf/real")


def item(path: Path, subset: str, label: str, kind: str, base: str, mask: Path | None = None, variant: str = "original") -> dict:
    rel = str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)
    return {
        "id": f"{subset}__{variant}__{path.name}",
        "path": str(path),
        "rel": rel,
        "subset": subset,
        "label": label,
        "kind": kind,
        "base": base,
        "mask": str(mask) if mask else None,
        "variant": variant,
    }


def split_of(base: str) -> str:
    h = int(hashlib.sha256(base.encode()).hexdigest()[:8], 16)
    return "calib" if h % 2 == 0 else "test"


def authentic_items() -> list[dict]:
    out = []
    for p in sorted((ROOT / "tgif/orig").glob("*_orig.png")):
        out.append(item(p, "tgif_orig", "authentic", "authentic", "coco" + p.name.split("_")[0]))
    for variant, subset in (("nat", "vision_nat"), ("natWA", "vision_wa"), ("natFBH", "vision_fbh")):
        for p in sorted((ROOT / "vision" / variant).glob("*.jpg")):
            m = re.match(r"(D\d+)_I_\w+?_(\d+)\.jpg", p.name)
            out.append(item(p, subset, "authentic", "authentic", "vision" + m.group(1) + m.group(2)))
    for p in sorted((ROOT / "opensdi_flux/real").glob("*")):
        out.append(item(p, "opensdi_real", "authentic", "authentic", "opensdi" + p.stem))
    for p in sorted((ROOT / "sid_set/real").glob("*")):
        out.append(item(p, "sid_real", "authentic", "authentic", "sid" + p.stem))
    for p in sorted((ROOT / "cocoglide").glob("*.png")):
        if p.name.endswith("_mask.png") or p.name.startswith("glide_"):
            continue
        out.append(item(p, "cocoglide_real", "authentic", "authentic", "coco" + p.stem.rsplit("_", 1)[-1]))
    for p in sorted((ROOT / "grip_cmfd/images").glob("IMG_C*_[0-9][0-9][0-9].png")):
        out.append(item(p, "grip_orig", "authentic", "authentic", "grip" + p.stem[4:]))
    for p in sorted((ROOT / "unsplash1280").glob("*.jpg")):
        out.append(item(p, "unsplash", "authentic", "authentic", "unsplash" + p.stem))
    return out


def manipulated_items() -> list[dict]:
    out = []
    masks = ROOT / "tgif/masks"
    for p in sorted((ROOT / "tgif/ps-sp").glob("*.png")):
        m = re.match(r"(\d+)_mask_(\w+?)\.png_ps_\d\.png", p.name)
        gt = masks / f"{m.group(1)}_mask_{m.group(2)}.png_ps_mask.png"
        out.append(item(p, "tgif_ps_sp", "manipulated", "ai_inpaint_spliced", "coco" + m.group(1), gt))
    for p in sorted((ROOT / "tgif/sd2-sp").glob("*.png")):
        m = re.match(r"(\d+)_mask_(\w+?)\.png_ps_mask\.png_sd2_\d\.png", p.name)
        gt = masks / f"{m.group(1)}_mask_{m.group(2)}.png_ps_mask.png"
        out.append(item(p, "tgif_sd2_sp", "manipulated", "ai_inpaint_spliced", "coco" + m.group(1), gt))
    for p in sorted((ROOT / "tgif/flux1filldev-sp").glob("*.png")):
        m = re.match(r"(\d+)_mask_(\w+?)\.png_ps_mask\.png_flux1filldev_\d\.png", p.name)
        size = Image.open(p).size
        gt = None
        for cand in (
            ROOT / "tgif/masks-flux" / f"{m.group(1)}_mask_{m.group(2)}.png",
            ROOT / "tgif/masks-flux" / f"{m.group(1)}_mask_{m.group(2)}_1024.png",
            masks / f"{m.group(1)}_mask_{m.group(2)}.png_ps_mask.png",
        ):
            if cand.exists() and Image.open(cand).size == size:
                gt = cand
                break
        out.append(item(p, "tgif_flux_sp", "manipulated", "ai_inpaint_spliced", "coco" + m.group(1), gt))
    for p in sorted((ROOT / "tgif/sd2-fr").glob("*.png")):
        m = re.match(r"(\d+)_mask_(\w+?)\.png_sd2-512_\d\.png", p.name)
        gt = masks / f"{m.group(1)}_mask_{m.group(2)}_512.png"
        out.append(item(p, "tgif_sd2_fr", "manipulated", "ai_inpaint_regenerated", "coco" + m.group(1), gt if gt.exists() else None))
    by_id = {}
    for p in (ROOT / "cocoglide").glob("*_mask.png"):
        by_id[p.stem.split("_")[-2]] = p
    for p in sorted((ROOT / "cocoglide").glob("glide_inpainting_val2017_*_up.png")):
        cid = p.stem.split("_")[-2]
        out.append(item(p, "cocoglide_fake", "manipulated", "ai_inpaint_spliced", "coco" + cid, by_id.get(cid)))
    for p in sorted((ROOT / "opensdi_flux/partial").glob("*")):
        gt = ROOT / "opensdi_flux/masks" / (p.stem + ".png")
        out.append(item(p, "opensdi_partial", "manipulated", "ai_local_edit", "opensdi" + p.stem, gt if gt.exists() else None))
    for p in sorted((ROOT / "sid_set/tampered").glob("*")):
        gt = ROOT / "sid_set/masks" / (p.stem + ".png")
        out.append(item(p, "sid_tampered", "manipulated", "ai_local_edit", "sid" + p.stem, gt if gt.exists() else None))
    for p in sorted((ROOT / "grip_cmfd/forged_images").glob("TP_*_copy.png")):
        gt = p.with_name(p.name.replace("_copy.png", "_gt.png"))
        out.append(item(p, "grip_copy", "manipulated", "copy_move", "grip" + p.stem[3:-5], gt))
    return out


def _save_variant(rgb: np.ndarray, variant: str) -> tuple[bytes, str]:
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    if variant == "jpeg75":
        img.save(buf, format="JPEG", quality=75)
        return buf.getvalue(), ".jpg"
    if variant == "jpeg90":
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue(), ".jpg"
    if variant == "resize50":
        img.resize((max(1, img.width // 2), max(1, img.height // 2)), Image.Resampling.LANCZOS).save(buf, format="JPEG", quality=90)
        return buf.getvalue(), ".jpg"
    if variant == "screenshot":
        scale = min(1.0, 1280 / max(img.size))
        small = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.BILINEAR)
        jb = io.BytesIO()
        small.save(jb, format="JPEG", quality=85)
        Image.open(io.BytesIO(jb.getvalue())).convert("RGB").save(buf, format="PNG")
        return buf.getvalue(), ".png"
    raise ValueError(variant)


def _variant_mask(mask_path: str, variant: str, size: tuple[int, int], dest: Path) -> Path:
    m = Image.open(mask_path).convert("L")
    if m.size != size:
        m = m.resize(size, Image.Resampling.NEAREST)
    dest.parent.mkdir(parents=True, exist_ok=True)
    m.save(dest)
    return dest


def derived_items(base_items: list[dict], variants: list[str], per_subset: dict, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    by_subset: dict[str, list[dict]] = {}
    for it in base_items:
        by_subset.setdefault(it["subset"], []).append(it)
    for subset, n in per_subset.items():
        items = list(by_subset.get(subset, []))
        rng.shuffle(items)
        for it in items[:n]:
            rgb = np.asarray(Image.open(it["path"]).convert("RGB"))
            for variant in variants:
                data, ext = _save_variant(rgb, variant)
                dest = DERIVED / variant / subset / (Path(it["path"]).stem + ext)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    dest.write_bytes(data)
                mask = None
                if it["mask"]:
                    size = Image.open(io.BytesIO(data)).size
                    mask = _variant_mask(it["mask"], variant, size, DERIVED / variant / (subset + "_masks") / (Path(it["path"]).stem + ".png"))
                new = item(dest, subset, it["label"], it["kind"], it["base"], mask, variant)
                out.append(new)
    return out


CAPS = {"vision_nat": 35, "vision_fbh": 70, "cocoglide_real": 200, "cocoglide_fake": 200}


def apply_caps(items: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_subset: dict[str, list[dict]] = {}
    for it in items:
        by_subset.setdefault(it["subset"], []).append(it)
    out = []
    for subset, group in by_subset.items():
        cap = CAPS.get(subset)
        if cap and len(group) > cap:
            group = sorted(rng.sample(group, cap), key=lambda x: x["path"])
        out.extend(group)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "index.json"))
    parser.add_argument("--seed", type=int, default=3)
    args = parser.parse_args()
    auth = apply_caps(authentic_items(), args.seed)
    manip = apply_caps(manipulated_items(), args.seed)
    auth_variants = derived_items(
        auth,
        ["jpeg75", "jpeg90", "resize50", "screenshot"],
        {"vision_nat": 20, "tgif_orig": 20, "opensdi_real": 20, "unsplash": 20},
        args.seed,
    )
    manip_variants = derived_items(
        manip,
        ["jpeg75", "resize50"],
        {"tgif_ps_sp": 40, "grip_copy": 30, "cocoglide_fake": 30, "opensdi_partial": 30},
        args.seed,
    )
    core = auth + manip
    random.Random(args.seed).shuffle(core)
    variants = auth_variants + manip_variants
    random.Random(args.seed + 1).shuffle(variants)
    items = core + variants
    for it in items:
        it["split"] = split_of(it["base"])
    Path(args.out).write_text(json.dumps(items, indent=1))
    counts: dict[tuple, int] = {}
    for it in items:
        key = (it["label"], it["subset"], it["variant"])
        counts[key] = counts.get(key, 0) + 1
    for key in sorted(counts):
        print(key, counts[key])
    print("total", len(items))


if __name__ == "__main__":
    main()
