import threading
from dataclasses import dataclass

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from analyzers.text.normalize import normalize_for_model

MAX_TOKENS = 512
MAX_WINDOWS = 4
MIN_WINDOW_TOKENS = 32


@dataclass
class ClassifierScore:
    probability: float
    windows: list[float]
    tokens: int


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
    def probabilities(self, chunks: list[list[int]]) -> list[float]:
        encoded = [self.tokenizer.build_inputs_with_special_tokens(c) for c in chunks]
        batch = self.tokenizer.pad({"input_ids": encoded}, return_tensors="pt").to(self.device)
        logits = self.model(**batch).logits.float()
        return torch.softmax(logits, dim=-1)[:, 1].tolist()

    def score(self, text: str) -> ClassifierScore:
        ids = self.token_ids(text)
        if not ids:
            raise ValueError("text is empty after normalization")
        probs = self.probabilities(pick_windows(self.chunks(ids)))
        return ClassifierScore(probability=sum(probs) / len(probs), windows=[round(p, 4) for p in probs], tokens=len(ids))


_cache: dict[tuple[str, str], TextClassifier] = {}
_lock = threading.Lock()


def get_classifier(model_dir: str, device: str = "cpu") -> TextClassifier:
    key = (model_dir, device)
    with _lock:
        if key not in _cache:
            _cache[key] = TextClassifier(model_dir, device)
        return _cache[key]
