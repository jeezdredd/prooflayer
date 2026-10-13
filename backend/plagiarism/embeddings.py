import threading

import torch
import torch.nn.functional as F
from django.conf import settings
from transformers import AutoModel, AutoTokenizer

from analyzers._device import get_device, inputs_to_device

_lock = threading.Lock()
_model = None
_tokenizer = None
BATCH = 32


def _load():
    global _model, _tokenizer
    with _lock:
        if _model is None:
            name = getattr(settings, "PLAGIARISM_EMBED_MODEL", "intfloat/multilingual-e5-small")
            _tokenizer = AutoTokenizer.from_pretrained(name)
            _model = AutoModel.from_pretrained(name).to(get_device()).eval()
    return _model, _tokenizer


def embed(sentences: list[str]) -> list[list[float]]:
    if not sentences:
        return []
    model, tokenizer = _load()
    vectors: list[list[float]] = []
    with torch.inference_mode():
        for i in range(0, len(sentences), BATCH):
            batch = [f"query: {s}" for s in sentences[i:i + BATCH]]
            encoded = tokenizer(batch, padding=True, truncation=True, max_length=128, return_tensors="pt")
            encoded = inputs_to_device(dict(encoded))
            hidden = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            vectors.extend(F.normalize(pooled, p=2, dim=1).cpu().tolist())
    return vectors
