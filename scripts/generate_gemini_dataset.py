#!/usr/bin/env python3
"""
Generate AI-detection training images using Gemini API (free tier).
Requires: pip install google-genai pillow

Google AI Studio free tier: https://aistudio.google.com/apikey
- gemini-2.0-flash-preview-image-generation: 1500 req/day free

Usage:
  GEMINI_API_KEY=your_key python3 scripts/generate_gemini_dataset.py --out dataset/gemini --count 200
"""

import argparse
import os
import time
from pathlib import Path

PROMPTS = [
    "A professional news photograph of a protest rally in a European city square, daytime",
    "A press photo of a politician giving a speech at a podium, sharp focus",
    "A documentary-style photograph of refugees at a border crossing",
    "A news photograph of firefighters battling a building fire at night",
    "A photojournalist image of flood damage in a residential neighborhood",
    "A candid street photograph of a busy market in Southeast Asia",
    "A professional portrait photograph of a middle-aged businesswoman in an office",
    "A news photograph of soldiers in military uniform at a checkpoint",
    "A photojournalistic image of medical workers in a hospital corridor",
    "A documentary photograph of a courtroom during a trial",
    "A press photograph of scientists working in a laboratory with equipment",
    "A news photograph of a car accident on a highway with police",
    "A photojournalist image of athletes at a major sporting event stadium",
    "A professional photograph of a CEO at a company press conference",
    "A documentary image of construction workers on a large building site",
    "A satellite photograph of a coastal city from above, high resolution",
    "A news photograph of a wildfire burning through a forest near homes",
    "A photojournalistic image of a crowded airport terminal during delays",
    "A press photograph of a summit meeting between world leaders at a table",
    "A documentary photograph of workers in a factory production line",
    "A realistic photograph of a middle-aged man reading a newspaper on a park bench",
    "A candid photograph of a family having dinner at a restaurant",
    "A street photography image of pedestrians crossing a busy city intersection",
    "A professional photograph of a woman giving a TED-style talk on stage",
    "A news photograph of a ship arriving at a busy commercial port",
    "A photojournalistic image of people voting at a polling station",
    "A documentary photograph of a deforested area in a tropical region",
    "A press photograph of an earthquake aftermath in an urban area",
    "A realistic photograph of children playing in a schoolyard",
    "A professional news photograph of emergency services at a disaster scene",
    "A press photograph of a cryptocurrency conference with large screens",
    "A news image of solar panels being installed on a rooftop",
    "A documentary photograph of a refugee camp with tents and people",
    "A photojournalistic image of a climate protest march in a capital city",
    "A realistic photograph of a surgeon performing an operation",
    "A news photograph of a submarine at a naval base dock",
    "A press image of a tech product launch event with a presenter on stage",
    "A documentary photograph of farmers harvesting crops in a field",
    "A photojournalistic image of a stock exchange trading floor",
    "A realistic photograph of astronauts in spacesuits during training",
]


def generate(api_key: str, out_dir: Path, count: int, delay: float):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Install: pip install google-genai")
        return

    client = genai.Client(api_key=api_key)
    out_dir.mkdir(parents=True, exist_ok=True)

    ai_dir = out_dir / "ai_generated"
    ai_dir.mkdir(exist_ok=True)

    generated = 0
    errors = 0
    prompt_pool = PROMPTS * ((count // len(PROMPTS)) + 1)

    for i, prompt in enumerate(prompt_pool[:count]):
        out_path = ai_dir / f"gemini_{i:04d}.jpg"
        if out_path.exists():
            print(f"  skip {out_path.name} (exists)")
            generated += 1
            continue

        try:
            response = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/jpeg",
                ),
            )
            saved = False
            if response.generated_images:
                img = response.generated_images[0]
                with open(out_path, "wb") as f:
                    f.write(img.image.image_bytes)
                saved = True
            if saved:
                print(f"  [{i+1}/{count}] saved {out_path.name}")
                generated += 1
            else:
                print(f"  [{i+1}/{count}] no image in response")
        except Exception as exc:
            print(f"  [{i+1}/{count}] error: {exc}")
            errors += 1

        if delay > 0:
            time.sleep(delay)

    print(f"\nDone. Generated: {generated}, Errors: {errors}")
    print(f"Dataset at: {out_dir.resolve()}")
    print("\nNext steps:")
    print("  1. Add real photos to dataset/real/ (same count)")
    print("  2. Use seed_labeled_samples or add to training pipeline")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dataset/gemini", help="Output directory")
    parser.add_argument("--count", type=int, default=100, help="Images to generate")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between requests")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("Set GEMINI_API_KEY env var. Get free key at https://aistudio.google.com/apikey")
        exit(1)

    generate(api_key, Path(args.out), args.count, args.delay)
