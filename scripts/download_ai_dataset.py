#!/usr/bin/env python3
"""
Download AI-generated images from DiffusionDB (HuggingFace) for detection training.
Downloads zip parts directly - no loading script needed.

Each part-XXXXXX.zip = ~1000 Stable Diffusion images (PNG).
Requires: pip install huggingface_hub pillow

Usage:
  python3 scripts/download_ai_dataset.py --out dataset/hf --count 500
  python3 scripts/download_ai_dataset.py --out dataset/hf --count 2000 --parts 2
"""

import argparse
import io
import zipfile
from pathlib import Path


REPO_ID = "poloclub/diffusiondb"
IMAGES_PER_PART = 1000


def download_parts(out_dir: Path, count: int, parts: int):
    try:
        from huggingface_hub import hf_hub_download
        from PIL import Image
    except ImportError:
        print("Install: pip install huggingface_hub pillow")
        return

    ai_dir = out_dir / "ai_generated"
    ai_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    needed_parts = min(parts, (count + IMAGES_PER_PART - 1) // IMAGES_PER_PART)

    for part_num in range(1, needed_parts + 1):
        if saved >= count:
            break
        filename = f"diffusiondb-large-part-1/part-{part_num:06d}.zip"
        print(f"Downloading {filename} ...")
        try:
            zip_path = hf_hub_download(
                repo_id=REPO_ID,
                filename=filename,
                repo_type="dataset",
            )
        except Exception as e:
            print(f"  Failed to download part {part_num}: {e}")
            continue

        print(f"  Extracting images from part {part_num} ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            img_names = [n for n in zf.namelist() if n.lower().endswith((".png", ".jpg", ".webp"))]
            for name in img_names:
                if saved >= count:
                    break
                stem = Path(name).stem
                out_path = ai_dir / f"diffusiondb_{part_num:03d}_{stem}.jpg"
                if out_path.exists():
                    saved += 1
                    continue
                data = zf.read(name)
                try:
                    img = Image.open(io.BytesIO(data)).convert("RGB")
                    img.save(out_path, "JPEG", quality=92)
                    saved += 1
                    if saved % 100 == 0:
                        print(f"  {saved}/{count} saved")
                except Exception:
                    out_path.write_bytes(data)
                    saved += 1

    print(f"\nDone. Saved {saved} images -> {ai_dir.resolve()}")
    print("\nNext steps:")
    print("  1. Add real photos to dataset/real/ (same count)")
    print("  2. Use seed_labeled_samples or add to training pipeline")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dataset/hf", help="Output directory")
    parser.add_argument("--count", type=int, default=500, help="Max images to save")
    parser.add_argument("--parts", type=int, default=5, help="Max zip parts to download")
    args = parser.parse_args()

    download_parts(Path(args.out), args.count, args.parts)
