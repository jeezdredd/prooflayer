import math
import re
import threading
from dataclasses import dataclass

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from analyzers.text.language import sentences
from analyzers.text.normalize import normalize_for_model

MAX_TOKENS = 512
MAX_WINDOWS = 4
MIN_WINDOW_TOKENS = 32
SEGMENT_MIN_WORDS = 40
SEGMENT_SENTENCES = 3
MAX_SEGMENTS = 12
SEGMENT_BATCH = 8
PARAGRAPH = re.compile(r"\n\s*\n")


@dataclass
class ClassifierScore:
    score: float
    windows: list[float]
    tokens: int

    @property
    def probability(self) -> float:
        return 1 / (1 + math.exp(-self.score))


def split_segments(text: str) -> list[str]:
    parts = [p.strip() for p in PARAGRAPH.split(text) if p.strip()]
    if len(parts) < 2:
        sents = sentences(text)
        parts = [" ".join(sents[i : i + SEGMENT_SENTENCES]) for i in range(0, len(sents), SEGMENT_SENTENCES)]
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1].split()) < SEGMENT_MIN_WORDS:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    if len(merged) > 1 and len(merged[-1].split()) < SEGMENT_MIN_WORDS:
        tail = merged.pop()
        merged[-1] = f"{merged[-1]} {tail}"
    return merged[:MAX_SEGMENTS]


def pick_windows(chunks: list, limit: int = MAX_WINDOWS) -> list:
    if len(chunks) <= limit:
        return chunks
    step = (len(chunks) - 1) / (limit - 1)
    return [chunks[round(i * step)] for i in range(limit)]


class TextClassifier:
    def __init__(self, model_dir: str, device: str = "cpu", max_tokens: int = MAX_TOKENS):
        self.device = device
        self.max_tokens = max_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(device).eval()

    def token_ids(self, text: str) -> list[int]:
        return self.tokenizer(normalize_for_model(text), add_special_tokens=False)["input_ids"]

    def chunks(self, ids: list[int]) -> list[list[int]]:
        body = self.max_tokens - 2
        parts = [ids[i : i + body] for i in range(0, len(ids), body)]
        kept = [p for p in parts if len(p) >= MIN_WINDOW_TOKENS]
        return kept or parts[:1]

    @torch.inference_mode()
    def margins(self, chunks: list[list[int]]) -> list[float]:
        encoded = [self.tokenizer.build_inputs_with_special_tokens(c) for c in chunks]
        batch = self.tokenizer.pad({"input_ids": encoded}, return_tensors="pt").to(self.device)
        logits = self.model(**batch).logits.float()
        return (logits[:, 1] - logits[:, 0]).tolist()

    def segment_margins(self, segments: list[str]) -> list[float]:
        body = self.max_tokens - 2
        chunks = [ids[:body] for ids in (self.token_ids(s) for s in segments)]
        out: list[float] = []
        for i in range(0, len(chunks), SEGMENT_BATCH):
            out.extend(self.margins(chunks[i : i + SEGMENT_BATCH]))
        return out

    def score(self, text: str) -> ClassifierScore:
        ids = self.token_ids(text)
        if not ids:
            raise ValueError("text is empty after normalization")
        margins = self.margins(pick_windows(self.chunks(ids)))
        return ClassifierScore(score=sum(margins) / len(margins), windows=[round(m, 3) for m in margins], tokens=len(ids))


_cache: dict[tuple[str, str], TextClassifier] = {}
_lock = threading.Lock()


def get_classifier(model_dir: str, device: str = "cpu") -> TextClassifier:
    key = (model_dir, device)
    with _lock:
        if key not in _cache:
            _cache[key] = TextClassifier(model_dir, device)
        return _cache[key]
