import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
from django.core.management.base import BaseCommand

from analyzers.management.commands.build_text_eval import Command as EvalBuilder
from analyzers.management.commands.build_text_eval import bucket, usable
from analyzers.management.commands.build_text_seeds import refine_split
from analyzers.text.normalize import normalize_for_model

ANONYMIZED = re.compile(r"Generic_\w+|\b[A-Z]{3,}_NAME\b|PROPER_NAME")
HELDOUT_GENERATORS = {"gemma3-12b"}
COLING_EN_AI = {"gpt4o", "gpt4", "llama3-70b", "llama3-8b", "gemma2-9b-it", "gemma-7b-it", "mixtral-8x7b", "cohere", "gpt-3.5-turbo"}
SPLITS = ("train", "calib", "test")
FAMILY_SHARE = {("en", 0, "daigt"): 0.6}
COLING_EN_HUMAN_SHARE = 0.15
PRIORITY_SOURCES = {"wiki-pre2022"}


def row(rid, lang, split, label, source, text, generator="", mode=""):
    return {"id": rid, "lang": lang, "split": split, "label": label, "source": source, "generator": generator, "mode": mode, "text": text.strip()}


def latin_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isascii() for c in letters) / len(letters) if letters else 0.0


def side_split(key: str) -> str:
    return "train" if bucket(f"{key}:side") < 0.8 else "calib"


def strip_hint(text: str, hint: str) -> str:
    head = normalize_for_model(hint)[:40].lower()
    if len(head) < 20 or not normalize_for_model(text).lower().startswith(head):
        return text
    parts = re.split(r"(?<=[.!?…])\s+", text.strip(), maxsplit=1)
    return parts[1] if len(parts) == 2 else text


class Command(BaseCommand):
    help = "Assemble dataset/text_t4 (train/calib/test) for the supervised text classifier"

    def add_arguments(self, parser):
        parser.add_argument("--raw", default="dataset/text_raw")
        parser.add_argument("--eval", default="dataset/text_eval")
        parser.add_argument("--gen", default="dataset/text_gen")
        parser.add_argument("--out", default="dataset/text_t4")
        parser.add_argument("--train-cap", type=int, default=2500, help="max texts per class per language in train")
        parser.add_argument("--calib-cap", type=int, default=400)
        parser.add_argument("--seed", type=int, default=29)

    def handle(self, *args, **opts):
        raw, out = Path(opts["raw"]), Path(opts["out"])
        rng = random.Random(opts["seed"])
        csv.field_size_limit(sys.maxsize)
        pool = {s: [] for s in SPLITS}
        self._legacy(raw, pool)
        self._extra(raw, pool)
        self._fresh(Path(opts["gen"]), pool)
        pool["test"] += self._frozen_test(Path(opts["eval"]))

        seen, picked = set(), {s: [] for s in SPLITS}
        for split in SPLITS:
            rows = pool[split]
            rng.shuffle(rows)
            rows.sort(key=lambda r: r["mode"] not in ("generate", "humanize") and r["source"] not in PRIORITY_SOURCES)
            cap = {"train": opts["train_cap"], "calib": opts["calib_cap"]}.get(split)
            taken = Counter()
            for r in rows:
                key = hashlib.sha1(normalize_for_model(r["text"]).encode()).hexdigest()
                if key in seen or ANONYMIZED.search(r["text"]):
                    continue
                group = (r["lang"], r["label"])
                family = (*group, r["source"].split(":")[0])
                if cap and taken[group] >= cap:
                    continue
                if cap and family in FAMILY_SHARE and taken[family] >= cap * FAMILY_SHARE[family]:
                    continue
                seen.add(key)
                taken[group] += 1
                taken[family] += 1
                picked[split].append(r)

        out.mkdir(parents=True, exist_ok=True)
        summary = {}
        for split, rows in picked.items():
            rng.shuffle(rows)
            with open(out / f"{split}.jsonl", "w") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            summary[split] = {f"{lang}/{'ai' if label else 'human'}": n for (lang, label), n in sorted(Counter((r["lang"], r["label"]) for r in rows).items())}
            summary[f"{split}:fresh"] = dict(Counter(r["generator"] for r in rows if r["mode"] in ("generate", "humanize")))
        self.stdout.write(json.dumps(summary, indent=1))

    def _legacy(self, raw: Path, pool: dict):
        builder = EvalBuilder()
        for lang, rows in (("en", builder._english(raw)), ("ru", builder._russian(raw)), ("fr", builder._french(raw))):
            for label_name, items in rows.items():
                for r in items:
                    split = refine_split(r)
                    if split == "test" or r["source"].startswith("textsight"):
                        continue
                    pool[split].append(row(r["id"], lang, split, int(label_name == "ai"), r["source"], r["text"], r.get("generator", "")))

    def _extra(self, raw: Path, pool: dict):
        for r in pq.read_table(raw / "coling_ml_dev.parquet").to_pylist():
            if r["lang"] not in ("en", "ru") or not usable(r["text"]):
                continue
            if r["lang"] == "en" and r["label"] == 1 and r["model"] not in COLING_EN_AI:
                continue
            if r["lang"] == "en" and r["label"] == 0 and bucket(r["id"]) > COLING_EN_HUMAN_SHARE:
                continue
            split = side_split(r["id"])
            pool[split].append(row(f'coling-{r["id"]}', r["lang"], split, int(r["label"]), f'coling:{r["source"]}', r["text"], r["model"] if r["label"] else ""))
        coat_train = raw / "coat_auth_train.parquet"
        if coat_train.exists():
            for r in pq.read_table(coat_train).to_pylist():
                if not usable(r["text"]):
                    continue
                key = f'coat-auth-{r["id"]}'
                split = side_split(key)
                label = int(r["label"] != "Human")
                pool[split].append(row(key, "ru", split, label, "coat-train", r["text"], r["label"] if label else ""))
        for path in sorted(raw.glob("wiki_*.jsonl")):
            for r in map(json.loads, open(path)):
                pool[r["split"]].append(row(r["id"], r["lang"], r["split"], 0, "wiki-pre2022", r["text"]))
        with open(raw / "mmgt_fra.csv", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                if r["Type"] != "undecided" or bucket(f"mmgt-u-{i}") > 0.03 or not usable(r["Original text"]):
                    continue
                split = side_split(f"mmgt-u-{i}")
                pool[split].append(row(f"mmgt-fra-u-{i}", "fr", split, 0, "mmgt-fra-news", r["Original text"]))

    def _fresh(self, gen: Path, pool: dict):
        hints = {}
        for name in ("seeds.jsonl", "wiki_seeds.jsonl"):
            if (gen / name).exists():
                hints |= {s["id"]: s["hint"] for s in map(json.loads, open(gen / name))}
        if not (gen / "ai.jsonl").exists():
            return
        for r in map(json.loads, open(gen / "ai.jsonl")):
            heldout = r["generator"] in HELDOUT_GENERATORS or r.get("base_generator") in HELDOUT_GENERATORS
            if heldout and r["split"] != "test":
                continue
            text = strip_hint(r["text"], hints.get(r["seed_id"], ""))
            if len(text.split()) < 60 or (r["lang"] == "ru" and latin_share(text) > 0.3):
                continue
            source = "fresh-wiki" if r.get("genre") == "wiki" else "fresh"
            pool[r["split"]].append(row(r["id"], r["lang"], r["split"], 1, source, text, r["generator"], r["mode"]))

    def _frozen_test(self, eval_dir: Path) -> list:
        rows = []
        for path in sorted(eval_dir.glob("*/*.jsonl")):
            lang, label_name = path.parent.name, path.stem
            for r in map(json.loads, open(path)):
                if r["split"] != "test":
                    continue
                mode = f'char:{r["humanize"]}' if r.get("humanize") else ""
                rows.append(row(r["id"], lang, "test", int(label_name != "human"), r["source"], r["text"], r.get("generator", ""), mode))
        return rows
