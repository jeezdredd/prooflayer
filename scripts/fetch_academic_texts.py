import hashlib
import itertools
import json
import os
import re
import sys
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dataset/text_academic"
SEEDS = ROOT / "dataset/text_gen/academic_seeds.jsonl"
FROZEN = ROOT / "dataset/text_eval_academic"
MIN_WORDS = 80
SPACES = re.compile(r"\s+")


def clean(text: str) -> str:
    text = text.replace("<S>", "").replace("</S>", "")
    return SPACES.sub(" ", re.sub(r"@x\w+", "", text)).strip()


def body_chunk(text: str, size: int = 1800) -> str:
    text = clean(text)
    cut = text[len(text) // 3:len(text) // 3 + size]
    first, last = cut.find(". "), cut.rfind(". ")
    return cut[first + 2:last + 1] if first != -1 and last > first else cut


def split_of(text: str) -> str:
    share = int(hashlib.sha256(("academic:" + text[:400]).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if share < 0.6 else "calib" if share < 0.75 else "test"


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0][:200]


def frozen_texts() -> set[str]:
    return {json.loads(line)["text"][:400] for path in FROZEN.glob("*.jsonl") for line in path.open()}


def english(dataset: str, tag: str, count: int):
    for i, r in enumerate(itertools.islice(load_dataset(dataset, split="train", streaming=True), count)):
        abstract, body = clean(r["abstract"]), body_chunk(r["article"])
        topic = first_sentence(abstract)
        yield {"id": f"acad-{tag}-{i}-a", "lang": "en", "source": f"academic-{tag}", "title": topic, "kind": "abstract", "text": abstract}
        yield {"id": f"acad-{tag}-{i}-b", "lang": "en", "source": f"academic-{tag}", "title": topic, "kind": "body", "text": body}


def russian_grnti(count: int):
    for i, r in enumerate(itertools.islice(load_dataset("ai-forever/ru-scibench-grnti-classification", split="train", streaming=True), count)):
        text = SPACES.sub(" ", r["text"]).strip()
        title, _, rest = text.partition(". ")
        yield {"id": f"acad-ru-grnti-{i}", "lang": "ru", "source": "academic-ru-grnti", "title": title.capitalize() if title.isupper() else title, "kind": "abstract", "text": text}


def russian_scibench(count: int, skip: int):
    rows = itertools.islice(load_dataset("mlsa-iai-msu-lab/ru_sci_bench", split="ru", streaming=True), skip, skip + count)
    for r in rows:
        text = SPACES.sub(" ", r["abstract"] or "").strip()
        yield {"id": f"acad-ru-scibench-{r['paper_id']}", "lang": "ru", "source": "academic-ru-scibench", "title": (r["title"] or "").strip(), "kind": "abstract", "text": text}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = frozen_texts()
    sources = [
        russian_grnti(2400),
        russian_scibench(2000, skip=1000),
        english("ccdv/arxiv-summarization", "arxiv", 300),
        english("ccdv/pubmed-summarization", "pubmed", 300),
    ]
    kept = []
    for rows in sources:
        for r in rows:
            if len(r["text"].split()) < MIN_WORDS or r["text"][:400] in frozen or len(r["title"].split()) < 3:
                continue
            r["split"] = split_of(r["text"])
            kept.append(r)
    with (OUT / "human.jsonl").open("w") as fh:
        for r in kept:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with SEEDS.open("w") as fh:
        for r in kept:
            words = max(120, min(320, len(r["text"].split())))
            seed = {"id": f"seed-{r['id']}", "lang": r["lang"], "split": r["split"], "hint": r["title"], "genre": f"academic-{r['kind']}", "words": words, "human_id": r["id"]}
            fh.write(json.dumps(seed, ensure_ascii=False) + "\n")
    counts = {}
    for r in kept:
        key = f"{r['source']}/{r['split']}"
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps(counts, indent=1, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
