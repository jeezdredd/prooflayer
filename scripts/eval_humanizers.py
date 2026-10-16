import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from analyzers.text.classifier import TextClassifier
from analyzers.text.normalize import normalize_for_model

HUMANIZERS = ROOT / "dataset/humanizers/all.jsonl"
ADVERSARIAL = ROOT / "dataset/text_gen/adversarial.jsonl"
MODELS = ROOT / "dataset/text_models"
HELDOUT = {"humbot", "undetectable", "stealth-writer", "walter-writes", "gptinf", "notegpt"}


def split_of(text: str) -> str:
    key = "humanizer:" + hashlib.sha1(normalize_for_model(text).encode()).hexdigest()
    share = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if share < 0.6 else "calib" if share < 0.75 else "test"


def humanizer_rows() -> list[dict]:
    rows = [json.loads(line) for line in HUMANIZERS.open()]
    return [r for r in rows if r["humanizer"] in HELDOUT or split_of(r["input"]) == "test"]


def adversarial_rows() -> list[dict]:
    if not ADVERSARIAL.exists():
        return []
    return [r for r in map(json.loads, ADVERSARIAL.open()) if r["split"] == "test"]


def evaluate(name: str, device: str) -> None:
    model = MODELS / name
    calibration = json.load((model / "calibration.json").open())["languages"]
    clf = TextClassifier(str(model), device=device)
    cache: dict[str, float] = {}

    def score(text: str) -> float:
        if text not in cache:
            cache[text] = clf.score(text).score
        return cache[text]

    threshold = calibration["en"]["threshold_fpr1"]
    held = [0, 0, 0]
    seen = [0, 0, 0]
    for r in humanizer_rows():
        group = held if r["humanizer"] in HELDOUT else seen
        group[0] += 1
        group[1] += score(r["input"]) >= threshold
        group[2] += score(r["output"]) >= threshold
    print(f"{name}  en threshold {threshold:.3f}")
    for label, (n, raw, hum) in (("held-out humanizers", held), ("seen humanizers, unseen texts", seen)):
        if n:
            print(f"  {label:31} n={n:<4} raw AI {raw / n:>4.0%}  humanized {hum / n:>4.0%}")
    hits = collections.Counter()
    totals = collections.Counter()
    for r in adversarial_rows():
        totals[r["lang"]] += 1
        hits[r["lang"]] += score(r["text"]) >= calibration[r["lang"]]["threshold_fpr1"]
    if totals:
        print("  adversarial paraphrase       " + "  ".join(f"{lang} {hits[lang]}/{totals[lang]} ({hits[lang] / totals[lang]:.0%})" for lang in sorted(totals)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Humanized and adversarially paraphrased AI text caught at each model's 1% FPR threshold")
    parser.add_argument("models", nargs="+", help="directory names under dataset/text_models")
    parser.add_argument("--device", default="mps")
    args = parser.parse_args()
    for name in args.models:
        evaluate(name, args.device)


if __name__ == "__main__":
    main()
