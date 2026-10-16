#!/usr/bin/env python3
import argparse
import json
import random
import sys
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from analyzers.text.classifier import TextClassifier

PARAPHRASERS = {
    "qwen2.5-7b": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "qwen3-4b": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
}

PROMPTS = {
    "en": "Rephrase the text below without changing its meaning. Use a noticeably different style and your own wording. Output only the rewritten text.\n\n{text}",
    "ru": "Перескажи текст ниже своими словами, не меняя смысла. Стиль должен заметно отличаться. Выведи только переписанный текст.\n\n{text}",
    "fr": "Reformule le texte ci-dessous sans en changer le sens, avec un style nettement différent et tes propres mots. Donne uniquement le texte réécrit.\n\n{text}",
}

TOKENS_PER_WORD = {"en": 1.6, "ru": 2.6, "fr": 2.0}
WARMUP_TOKENS = 12
DETECTOR_WINDOW = 256
MLX_CACHE_BYTES = 2 * 1024**3
EMPTY_CACHE_EVERY = 64
MIN_PROB = 0.01


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def candidates(logits: mx.array, top_k: int, top_p: float) -> list[int]:
    probs = np.array(mx.softmax(logits.astype(mx.float32), axis=-1))
    order = np.argsort(-probs)[:top_k]
    kept, mass = [], 0.0
    for idx in order:
        if kept and probs[idx] < MIN_PROB:
            break
        kept.append(int(idx))
        mass += float(probs[idx])
        if mass >= top_p:
            break
    return kept


class Guide:
    def __init__(self, model_dir: str, device: str):
        self.clf = TextClassifier(model_dir, device=device)

        self.calls = 0

    @torch.inference_mode()
    def margins(self, texts: list[str]) -> list[float]:
        chunks = [self.clf.token_ids(t)[-DETECTOR_WINDOW:] or [self.clf.tokenizer.unk_token_id] for t in texts]
        encoded = [self.clf.tokenizer.build_inputs_with_special_tokens(c) for c in chunks]
        batch = self.clf.tokenizer.pad({"input_ids": encoded}, pad_to_multiple_of=64, return_tensors="pt").to(self.clf.device)
        logits = self.clf.model(**batch).logits.float()
        self.calls += 1
        if self.calls % EMPTY_CACHE_EVERY == 0 and self.clf.device == "mps":
            torch.mps.empty_cache()
        return (logits[:, 1] - logits[:, 0]).tolist()


def paraphrase(model, tokenizer, guide: Guide, text: str, lang: str, budget: int, top_k: int, top_p: float) -> str:
    prompt = tokenizer.apply_chat_template([{"role": "user", "content": PROMPTS[lang].format(text=text)}], add_generation_prompt=True)
    cache = make_prompt_cache(model)
    logits = model(mx.array([prompt]), cache=cache)[0, -1]
    out: list[int] = []
    eos = set(tokenizer.eos_token_ids) if hasattr(tokenizer, "eos_token_ids") else {tokenizer.eos_token_id}
    for _ in range(budget):
        options = candidates(logits, top_k, top_p)
        if options[0] in eos:
            break
        options = [o for o in options if o not in eos]
        if len(out) < WARMUP_TOKENS or len(options) == 1:
            choice = options[0]
        else:
            texts = [tokenizer.decode(out + [o]) for o in options]
            scores = guide.margins(texts)
            choice = options[int(np.argmin(scores))]
        out.append(choice)
        logits = model(mx.array([[choice]]), cache=cache)[0, -1]
    return tokenizer.decode(out).strip()


def main():
    parser = argparse.ArgumentParser(description="Detector-guided paraphrasing (Cheng et al. 2025) against our own text classifier")
    parser.add_argument("--paraphraser", default="qwen2.5-7b", choices=sorted(PARAPHRASERS))
    parser.add_argument("--guide", default="dataset/text_models/e5-small-t4", help="classifier that steers token choice")
    parser.add_argument("--guide-name", default="t4")
    parser.add_argument("--source", default="dataset/text_gen/ai.jsonl")
    parser.add_argument("--out", default="dataset/text_gen/adversarial.jsonl")
    parser.add_argument("--splits", nargs="*", default=["train", "test"])
    parser.add_argument("--langs", nargs="*", default=["en", "ru", "fr"])
    parser.add_argument("--per-lang", type=int, default=40)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    done = {r["id"] for r in read_jsonl(Path(args.out))}
    pool = [r for r in read_jsonl(Path(args.source)) if r.get("mode") == "generate" and r["generator"] != args.paraphraser]
    jobs = []
    for split in args.splits:
        for lang in args.langs:
            rows = [r for r in pool if r["split"] == split and r["lang"] == lang]
            rng.shuffle(rows)
            for r in rows[: args.per_lang]:
                rid = f'{r["id"]}-adv{args.guide_name}-{args.paraphraser}'
                if rid not in done:
                    jobs.append((rid, r))
    print(f"{len(jobs)} jobs", flush=True)
    if not jobs:
        return
    mx.set_cache_limit(MLX_CACHE_BYTES)
    model, tokenizer = load(PARAPHRASERS[args.paraphraser])
    guide = Guide(args.guide, args.device)
    started = time.time()
    with open(args.out, "a") as fh:
        for n, (rid, r) in enumerate(jobs, 1):
            budget = int(len(r["text"].split()) * TOKENS_PER_WORD[r["lang"]] * 1.4) + 64
            text = paraphrase(model, tokenizer, guide, r["text"], r["lang"], budget, args.top_k, args.top_p)
            if len(text.split()) >= 60:
                row = {
                    "id": rid,
                    "seed_id": r["seed_id"],
                    "lang": r["lang"],
                    "split": r["split"],
                    "generator": args.paraphraser,
                    "mode": "attack:adversarial",
                    "base_generator": r.get("base_generator") or r["generator"],
                    "guide": args.guide_name,
                    "text": text,
                }
                if r.get("genre"):
                    row["genre"] = r["genre"]
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
            print(f"{n}/{len(jobs)} {(time.time() - started) / n:.1f}s/text", flush=True)


if __name__ == "__main__":
    main()
