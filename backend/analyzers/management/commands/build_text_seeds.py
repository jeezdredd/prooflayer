import csv
import json
import random
import re
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from analyzers.management.commands.build_text_eval import Command as EvalBuilder
from analyzers.management.commands.build_text_eval import bucket, words

GENRES = {"en": "essay", "ru": "mixed", "fr": "news"}
SENTENCE = re.compile(r"(?<=[.!?…])\s+")
TRAIN_SHARE = 0.75


def refine_split(row: dict) -> str:
    if row["split"] == "test":
        return "test"
    return "train" if bucket(f'{row["id"]}:train') < TRAIN_SHARE else "calib"


def hint_for(lang: str, row: dict) -> str:
    if lang == "en" and row["source"].startswith("daigt:"):
        return row["source"].split(":", 1)[1]
    first = SENTENCE.split(row["text"].strip(), maxsplit=1)[0]
    return " ".join(first.split()[:25])


class Command(BaseCommand):
    help = "Pick topic seeds from human texts (train/calib/test, same groups as text_eval) for fresh AI generation"

    def add_arguments(self, parser):
        parser.add_argument("--raw", default="dataset/text_raw")
        parser.add_argument("--out", default="dataset/text_gen/seeds.jsonl")
        parser.add_argument("--train", type=int, default=500)
        parser.add_argument("--calib", type=int, default=150)
        parser.add_argument("--test", type=int, default=150)
        parser.add_argument("--seed", type=int, default=17)

    def handle(self, *args, **opts):
        raw, out = Path(opts["raw"]), Path(opts["out"])
        rng = random.Random(opts["seed"])
        csv.field_size_limit(sys.maxsize)
        builder = EvalBuilder()
        data = {"en": builder._english(raw), "ru": builder._russian(raw), "fr": builder._french(raw)}
        out.parent.mkdir(parents=True, exist_ok=True)
        counts = {}
        with open(out, "w") as fh:
            for lang, rows in data.items():
                humans = [r for r in rows["human"] if not r["source"].startswith("textsight")]
                for split in ("train", "calib", "test"):
                    pool = [r for r in humans if refine_split(r) == split]
                    rng.shuffle(pool)
                    picked = pool[: opts[split]]
                    for r in picked:
                        seed = {
                            "id": f'{lang}-{split}-{r["id"]}',
                            "lang": lang,
                            "split": split,
                            "hint": hint_for(lang, r),
                            "genre": GENRES[lang],
                            "words": max(150, min(500, words(r["text"]))),
                            "human_id": r["id"],
                        }
                        fh.write(json.dumps(seed, ensure_ascii=False) + "\n")
                    counts[f"{lang}/{split}"] = len(picked)
        self.stdout.write(json.dumps(counts, indent=1))
