#!/usr/bin/env python3
"""
Download labeled demo samples for ProofLayer evaluation and diploma demo.

Layout produced:
  samples/labeled/real/   - authentic photographs
  samples/labeled/fake/   - AI-generated images
  samples/demo/           - curated 3-scenario demo images + other media

Usage:
  python scripts/fetch_demo_samples.py
  python scripts/fetch_demo_samples.py --skip-hf   # only demo images, no HF bulk download
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
REAL_DIR = ROOT / "samples" / "labeled" / "real"
FAKE_DIR = ROOT / "samples" / "labeled" / "fake"
DEMO_DIR = ROOT / "samples" / "demo"

for d in (REAL_DIR, FAKE_DIR, DEMO_DIR):
    d.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://en.wikipedia.org/",
})


def _download(url: str, dest: Path, label: str = "", retries: int = 3) -> bool:
    if dest.exists():
        print(f"  skip  {dest.name} (exists)")
        return True
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=30, stream=True)
            if r.status_code == 429:
                wait = 8 * (attempt + 1)
                print(f"  429   {dest.name}  waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            dest.write_bytes(r.content)
            size = len(r.content) // 1024
            print(f"  ok    {dest.name}  {size}KB  {label}")
            time.sleep(2.0)
            return True
        except Exception as exc:
            if attempt == retries - 1:
                print(f"  FAIL  {dest.name}  {exc}", file=sys.stderr)
                return False
            time.sleep(4.0)
    return False


REAL_IMAGES = [
    (
        "https://images-assets.nasa.gov/image/as17-148-22727/as17-148-22727~small.jpg",
        "nasa_earth_apollo17.jpg",
        "real - NASA Apollo 17 Earth (public domain)",
    ),
    (
        "https://images-assets.nasa.gov/image/PIA23170/PIA23170~small.jpg",
        "nasa_pia23170.jpg",
        "real - NASA planetary (public domain)",
    ),
    (
        "https://images-assets.nasa.gov/image/GSFC_20171208_Archive_e001618/GSFC_20171208_Archive_e001618~small.jpg",
        "nasa_gsfc_2017.jpg",
        "real - NASA GSFC photo (public domain)",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/1/1e/Stonehenge.jpg",
        "wiki_stonehenge.jpg",
        "real - Stonehenge CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg",
        "wiki_ant_macro.jpg",
        "real - macro photo CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/4/43/Cute_dog.jpg",
        "wiki_cute_dog.jpg",
        "real - animal photo CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/b/b9/Above_Gotham.jpg",
        "wiki_above_gotham.jpg",
        "real - aerial photo CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/6/6d/Good_Food_Display_-_NCI_Visuals_Online.jpg",
        "wiki_food_display.jpg",
        "real - NCI photo public domain",
    ),
]

FAKE_IMAGES = [
    (
        "https://thispersondoesnotexist.com/",
        "tpdne_face_01.jpg",
        "fake - StyleGAN2 face",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/8/8e/Stable_Diffusion_1.5_-_Astronaut_in_the_ocean.png",
        "wiki_sd_astronaut_ocean.png",
        "fake - Stable Diffusion 1.5 CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/1/1e/Stable_diffusion_-_depiction_of_a_person.png",
        "wiki_sd_person.png",
        "fake - Stable Diffusion person CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/7/71/Stable_Diffusion_1.5_-_Cat_in_a_hat.png",
        "wiki_sd_cat_hat.png",
        "fake - Stable Diffusion cat CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/a/a8/Dall-e_3_artificial_intelligence_art.jpg",
        "wiki_dalle3_art.jpg",
        "fake - DALL-E 3 CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/0/0e/DALL-E_2_generated_image_of_a_panda_eating_bamboo.jpg",
        "wiki_dalle2_panda.jpg",
        "fake - DALL-E 2 CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/2/23/Stable_diffusion_generative_AI_art.jpg",
        "wiki_sd_generative_art.jpg",
        "fake - Stable Diffusion generative art CC",
    ),
    (
        "https://upload.wikimedia.org/wikipedia/commons/3/32/Midjourney_Imagine_Prompt_Explosion_of_Vibrant_Colors_and_Flowers.jpg",
        "wiki_mj_flowers.jpg",
        "fake - Midjourney CC",
    ),
]

DEMO_IMAGES = {
    "scenario_fake": (
        "https://thispersondoesnotexist.com/",
        "demo_fake_stylegan.jpg",
        "DEMO FAKE: StyleGAN2 face (thispersondoesnotexist.com) - expect CF/NPR to flag",
    ),
    "scenario_real": (
        "https://upload.wikimedia.org/wikipedia/commons/1/1e/Stonehenge.jpg",
        "demo_real_stonehenge.jpg",
        "DEMO REAL: Stonehenge photograph (Wikipedia CC) - expect authentic verdict",
    ),
    "scenario_real2": (
        "https://images-assets.nasa.gov/image/as17-148-22727/as17-148-22727~small.jpg",
        "demo_real_nasa.jpg",
        "DEMO REAL 2: NASA Apollo 17 Earth (public domain) - expect authentic verdict",
    ),
    "scenario_inconclusive": (
        "https://thispersondoesnotexist.com/",
        "demo_inconclusive_face.jpg",
        "DEMO INCONCLUSIVE/FAKE: Another StyleGAN face - expect fake or suspicious",
    ),
}

DEMO_TEXT = {
    "factcheck_claim.txt": (
        "The Eiffel Tower was built in 1889 and stands 330 meters tall. "
        "It was originally intended to be demolished after 20 years but was saved because it served as a giant radio antenna. "
        "The tower receives around 7 million visitors per year, making it the most visited paid monument in the world."
    ),
    "factcheck_fake_claim.txt": (
        "Scientists have confirmed that drinking 8 glasses of coffee per day prevents all forms of cancer. "
        "A Harvard study from 2024 showed 100% success rate in 50,000 patients. "
        "The WHO now recommends coffee as the primary cancer prevention method worldwide."
    ),
    "factcheck_mixed_claim.txt": (
        "COVID-19 vaccines were developed in record time using mRNA technology that had never been used in humans before. "
        "The vaccines are 95% effective against the original strain and provide lifetime immunity. "
        "Over 13 billion doses have been administered globally as of 2024."
    ),
}

DEMO_AUDIO_NOTES = """
Audio demo files - download these manually or record yourself:

1. REAL speech (authentic.wav):
   - Record 10-30s of yourself speaking naturally
   - Or download from: https://freesound.org (search "speech recording", CC0 license)
   - Expect: inconclusive or authentic (natural MFCC variation, normal pitch std)

2. SYNTHETIC TTS (fake_tts.mp3):
   - Generate via: https://elevenlabs.io (free tier) or https://ttsfree.com
   - Text: "This is an AI-generated voice sample for testing deepfake detection systems."
   - Expect: suspicious or fake (low MFCC variation, unnaturally uniform pitch)

3. Ambient noise (noise_floor.wav):
   - Download from: https://freesound.org (search "room tone", CC0)
   - Expect: inconclusive (no speech structure)
"""

DEMO_VIDEO_NOTES = """
Video demo files:

1. REAL video (real_clip.mp4):
   - Short clip (5-10s) from Wikimedia Commons public domain
   - https://commons.wikimedia.org/wiki/Category:Videos
   - Expect: authentic or inconclusive (depends on faces present)

2. DEEPFAKE video (fake_face_swap.mp4):
   - Use FaceForensics++ public samples:
     https://github.com/ondyari/FaceForensics (requires academic email)
   - Or use a public Celeb-DF sample if available
   - Expect: fake (face swap artifacts in ELA + ML flags)
"""


def fetch_hf_bulk():
    print("\n[1/3] Downloading labeled real images...")
    ok = 0
    for url, name, label in REAL_IMAGES:
        if _download(url, REAL_DIR / name, label):
            ok += 1
    print(f"      {ok}/{len(REAL_IMAGES)} real images")

    print("\n[2/3] Downloading labeled fake images...")
    ok = 0
    for url, name, label in FAKE_IMAGES:
        if _download(url, FAKE_DIR / name, label):
            ok += 1
    print(f"      {ok}/{len(FAKE_IMAGES)} fake images")


def fetch_demo():
    print("\n[3/3] Downloading curated demo images...")
    for scenario, (url, name, label) in DEMO_IMAGES.items():
        dest = DEMO_DIR / name
        _download(url, dest, label)

    print("\n      Writing demo text files...")
    for fname, content in DEMO_TEXT.items():
        path = DEMO_DIR / fname
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            print(f"  ok    {fname}")
        else:
            print(f"  skip  {fname} (exists)")

    notes_path = DEMO_DIR / "AUDIO_VIDEO_NOTES.txt"
    if not notes_path.exists():
        notes_path.write_text(DEMO_AUDIO_NOTES + "\n" + DEMO_VIDEO_NOTES, encoding="utf-8")
        print(f"  ok    AUDIO_VIDEO_NOTES.txt")

    print("\nDemo images summary:")
    print(f"  demo_fake_stylegan.jpg     -> Upload to ProofLayer -> expect: FAKE (StyleGAN2 face)")
    print(f"  demo_real_stonehenge.jpg   -> Upload to ProofLayer -> expect: AUTHENTIC")
    print(f"  demo_real_nasa.jpg         -> Upload to ProofLayer -> expect: AUTHENTIC (NASA photo)")
    print(f"  demo_inconclusive_face.jpg -> Upload to ProofLayer -> expect: FAKE/SUSPICIOUS")
    print(f"\n  factcheck_claim.txt        -> Paste into /factcheck -> expect: mostly_accurate")
    print(f"  factcheck_fake_claim.txt   -> Paste into /factcheck -> expect: misleading")
    print(f"  factcheck_mixed_claim.txt  -> Paste into /factcheck -> expect: mixed")
    print(f"\n  See AUDIO_VIDEO_NOTES.txt for audio/video demo preparation.")


def main():
    parser = argparse.ArgumentParser(description="Fetch ProofLayer demo samples")
    parser.add_argument("--skip-hf", action="store_true", help="Skip bulk labeled download, only demo images")
    args = parser.parse_args()

    print("ProofLayer demo sample fetcher")
    print(f"  real dir: {REAL_DIR}")
    print(f"  fake dir: {FAKE_DIR}")
    print(f"  demo dir: {DEMO_DIR}")

    if not args.skip_hf:
        fetch_hf_bulk()

    fetch_demo()

    real_count = len(list(REAL_DIR.glob("*.*")))
    fake_count = len(list(FAKE_DIR.glob("*.*")))
    demo_count = len(list(DEMO_DIR.glob("*")))
    print(f"\nTotal: {real_count} real, {fake_count} fake, {demo_count} demo files")


if __name__ == "__main__":
    main()
