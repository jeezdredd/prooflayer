import csv
import hashlib
import json
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from django.core.management.base import BaseCommand

MIN_WORDS = 80
MAX_WORDS = 900
HOMOGLYPHS = {"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "a": "а", "e": "е", "o": "о", "p": "р", "c": "с"}
HUMANIZE_MODES = ("homoglyph", "zero_width", "typos", "reorder")


def words(text: str) -> int:
    return len(text.split())


def usable(text: str) -> bool:
    return MIN_WORDS <= words(text) <= MAX_WORDS


def bucket(key: str) -> float:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def record(rid: str, text: str, source: str, license_: str, split: str, generator: str = "") -> dict:
    row = {"id": rid, "text": text.strip(), "source": source, "license": license_, "split": split}
    if generator:
        row["generator"] = generator
    return row


def humanize(text: str, rng: random.Random, mode: str) -> str:
    if mode == "homoglyph":
        return "".join(HOMOGLYPHS[c] if c in HOMOGLYPHS and rng.random() < 0.15 else c for c in text)
    if mode == "zero_width":
        return " ".join(w + ("​" if rng.random() < 0.2 else "") for w in text.split(" "))
    if mode == "typos":
        out = []
        for w in text.split(" "):
            if len(w) > 4 and rng.random() < 0.08:
                i = rng.randrange(1, len(w) - 2)
                w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
            out.append(w)
        return " ".join(out)
    sentences = [s for s in text.replace("! ", ". ").replace("? ", ". ").split(". ") if s]
    rng.shuffle(sentences)
    return ". ".join(sentences)


class Command(BaseCommand):
    help = "Build dataset/text_eval (ru, en, fr; human vs AI; calib/test split by group) from dataset/text_raw"

    def add_arguments(self, parser):
        parser.add_argument("--raw", default="dataset/text_raw")
        parser.add_argument("--out", default="dataset/text_eval")
        parser.add_argument("--per-split", type=int, default=300, help="max texts per class per split per language")
        parser.add_argument("--seed", type=int, default=13)

    def handle(self, *args, **opts):
        raw, out = Path(opts["raw"]), Path(opts["out"])
        cap, rng = opts["per_split"], random.Random(opts["seed"])
        csv.field_size_limit(sys.maxsize)
        data = {"en": self._english(raw), "ru": self._russian(raw), "fr": self._french(raw)}
        summary = {}
        for lang, rows in data.items():
            (out / lang).mkdir(parents=True, exist_ok=True)
            picked = {"human": [], "ai": []}
            for label in ("human", "ai"):
                for split in ("calib", "test"):
                    pool = [r for r in rows[label] if r["split"] == split and not r["source"].startswith("textsight")]
                    rng.shuffle(pool)
                    picked[label] += pool[:cap]
                picked[label] += [r for r in rows[label] if r["source"].startswith("textsight")]
            test_ai = [r for r in picked["ai"] if r["split"] == "test" and not r["source"].startswith("textsight")]
            humanized = [
                {**r, "id": f'{r["id"]}-{mode}', "text": humanize(r["text"], rng, mode), "humanize": mode}
                for i, r in enumerate(test_ai[: max(60, len(test_ai) // 4)])
                for mode in (HUMANIZE_MODES[i % len(HUMANIZE_MODES)],)
            ]
            for label, rows_out in (("human", picked["human"]), ("ai", picked["ai"]), ("ai_humanized", humanized)):
                with open(out / lang / f"{label}.jsonl", "w") as fh:
                    for r in rows_out:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                summary[f"{lang}/{label}"] = {s: sum(1 for r in rows_out if r["split"] == s) for s in ("calib", "test")}
        self.stdout.write(json.dumps(summary, indent=1))

    def _english(self, raw: Path) -> dict:
        table = pq.read_table(raw / "daigt.parquet", columns=["text", "label", "prompt_name", "source"]).to_pylist()
        prompts = sorted({r["prompt_name"] for r in table})
        calib_prompts = set(prompts[::2])
        rows = {"human": [], "ai": []}
        for i, r in enumerate(table):
            if not usable(r["text"]):
                continue
            split = "calib" if r["prompt_name"] in calib_prompts else "test"
            label = "ai" if int(r["label"]) == 1 else "human"
            generator = r["source"] if label == "ai" else ""
            rows[label].append(record(f"daigt-{i}", r["text"], f'daigt:{r["prompt_name"]}', "DAIGT v2 (Kaggle, research use)", split, generator))
        for name, label in (("textsight_ai.jsonl", "ai"), ("textsight_human_wiki.jsonl", "human")):
            path = raw / name
            if not path.exists():
                continue
            for line in open(path):
                r = json.loads(line)
                if words(r["text"]) >= 40:
                    generator = r["source"] if label == "ai" else ""
                    rows[label].append(record(f'ts-{r["id"]}', r["text"], f"textsight:{r.get('genre') or r['source']}", "CC BY-SA 4.0", "test", generator))
        return rows

    def _russian(self, raw: Path) -> dict:
        table = pq.read_table(raw / "coat_val.parquet").to_pylist()
        rows = {"human": [], "ai": []}
        for r in table:
            if not usable(r["text"]):
                continue
            label = "ai" if int(r["label"]) == 1 else "human"
            split = "calib" if bucket(str(r["id"])) < 0.5 else "test"
            rows[label].append(record(f'coat-{r["id"]}', r["text"], "coat", "Apache-2.0", split, "coat-mixed" if label == "ai" else ""))
        return rows

    def _french(self, raw: Path) -> dict:
        rows = {"human": [], "ai": []}
        with open(raw / "mmgt_fra.csv", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                kind, data_split = r["Type"], r["Data Split"]
                if kind not in ("Unchanged", "Rewritten") or data_split not in ("Train", "Dev", "Test"):
                    continue
                text = r["Modified text"] if kind == "Rewritten" else r["Original text"]
                if not usable(text):
                    continue
                label = "ai" if kind == "Rewritten" else "human"
                split = "test" if data_split == "Test" else "calib"
                generator = r["LLM used"] if label == "ai" else ""
                rows[label].append(record(f"mmgt-fra-{i}", text, "mmgt-fra-news", "see dataset card (research)", split, generator))
        return rows
