#!/usr/bin/env python3
"""
Download real photographs for AI detection training.
Uses Flickr30k (31k real CC photos) via HuggingFace Hub.

Requires: pip install huggingface_hub pillow

Usage:
  python3 scripts/download_real_dataset.py --out dataset/hf/real --count 500
"""

import argparse
import io
import zipfile
from pathlib import Path


REPO_ID = "nlphuji/flickr30k"
ZIP_FILE = "flickr30k-images.zip"


def download_flickr30k(out_dir: Path, count: int):
    try:
        from huggingface_hub import hf_hub_download
        from PIL import Image
    except ImportError:
        print("Install: pip install huggingface_hub pillow")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {ZIP_FILE} from {REPO_ID} (~2 GB) ...")
    try:
        zip_path = hf_hub_download(repo_id=REPO_ID, filename=ZIP_FILE, repo_type="dataset")
    except Exception as e:
        print(f"Download failed: {e}")
        return

    print("Extracting images ...")
    saved = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        img_names = [n for n in zf.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
        for name in img_names:
            if saved >= count:
                break
            stem = Path(name).stem
            out_path = out_dir / f"flickr_{stem}.jpg"
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

    print(f"\nDone. Saved {saved} real images -> {out_dir.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dataset/hf/real", help="Output directory")
    parser.add_argument("--count", type=int, default=500, help="Max images to extract")
    args = parser.parse_args()

    download_flickr30k(Path(args.out), args.count)
