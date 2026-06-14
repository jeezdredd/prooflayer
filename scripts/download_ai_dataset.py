#!/usr/bin/env python3
"""
Download AI-generated images from HuggingFace for detection training.
Requires: pip install datasets pillow

Sources:
- poloclub/diffusiondb  (Stable Diffusion, CC0) - 1k/10k/100k subsets
- Usage: python3 scripts/download_ai_dataset.py --out dataset/hf --count 500
"""

import argparse
import os
from pathlib import Path


DIFFUSIONDB_SUBSETS = {
    1000: "large_random_1k",
    10000: "large_random_10k",
    100000: "large_random_100k",
}


def download_diffusiondb(out_dir: Path, count: int):
    try:
        from datasets import load_dataset
    except ImportError:
        print("Install: pip install datasets")
        return

    subset = "large_random_1k"
    for threshold, name in sorted(DIFFUSIONDB_SUBSETS.items()):
        if count <= threshold:
            subset = name
            break

    print(f"Downloading DiffusionDB subset: {subset} (up to {count} images)")
    ds = load_dataset("poloclub/diffusiondb", subset, split="train", trust_remote_code=True)

    ai_dir = out_dir / "ai_generated"
    ai_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for i, item in enumerate(ds):
        if saved >= count:
            break
        img = item.get("image")
        if img is None:
            continue
        out_path = ai_dir / f"diffusiondb_{i:05d}.jpg"
        if out_path.exists():
            print(f"  skip {out_path.name}")
            saved += 1
            continue
        img.save(out_path, "JPEG", quality=92)
        saved += 1
        if saved % 50 == 0:
            print(f"  {saved}/{count} saved")

    print(f"\nDone. Saved {saved} images -> {ai_dir.resolve()}")
    print("\nNext steps:")
    print("  1. Add real photos to dataset/real/ (same count)")
    print("  2. Use seed_labeled_samples or add to training pipeline")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dataset/hf", help="Output directory")
    parser.add_argument("--count", type=int, default=500, help="Images to save")
    args = parser.parse_args()

    download_diffusiondb(Path(args.out), args.count)
