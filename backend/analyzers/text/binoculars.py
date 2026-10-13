import threading
from dataclasses import dataclass

try:
    import torch
    import torch.nn.functional as F
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from analyzers._device import get_device
except Exception as exc:
    torch = F = AutoModelForCausalLM = AutoTokenizer = get_device = None
    IMPORT_ERROR: Exception | None = exc
else:
    IMPORT_ERROR = None

WINDOW_TOKENS = 512
DEFAULT_OBSERVER = "Qwen/Qwen3-1.7B-Base"
DEFAULT_PERFORMER = "Qwen/Qwen3-1.7B"


class BinocularsUnavailable(RuntimeError):
    pass


@dataclass
class BinocularsScore:
    score: float
    tokens: int
    windows: list[float]


class BinocularsScorer:
    def __init__(self, observer_id: str = DEFAULT_OBSERVER, performer_id: str = DEFAULT_PERFORMER, device: str | None = None):
        if IMPORT_ERROR is not None:
            raise BinocularsUnavailable(f"binoculars unavailable: {IMPORT_ERROR}")
        self.observer_id, self.performer_id = observer_id, performer_id
        self.device = device or get_device()
        if device is None and self.device == "cpu" and torch.backends.mps.is_available():
            self.device = "mps"
        dtype = torch.float32 if self.device == "cpu" else torch.float16
        self.tokenizer = AutoTokenizer.from_pretrained(observer_id)
        performer_tokenizer = AutoTokenizer.from_pretrained(performer_id)
        if performer_tokenizer.get_vocab() != self.tokenizer.get_vocab():
            raise BinocularsUnavailable("observer and performer tokenizers differ")
        self.observer = AutoModelForCausalLM.from_pretrained(observer_id, dtype=dtype).to(self.device).eval()
        self.performer = AutoModelForCausalLM.from_pretrained(performer_id, dtype=dtype).to(self.device).eval()

    def _window(self, ids):
        with torch.inference_mode():
            observer_logits = self.observer(input_ids=ids).logits[:, :-1].float()
            performer_logits = self.performer(input_ids=ids).logits[:, :-1].float()
            targets = ids[:, 1:]
            vocab = min(observer_logits.shape[-1], performer_logits.shape[-1])
            observer_logits, performer_logits = observer_logits[..., :vocab], performer_logits[..., :vocab]
            log_ppl = F.cross_entropy(performer_logits.transpose(1, 2), targets, reduction="mean")
            observer_probs = F.softmax(observer_logits, dim=-1)
            performer_log_probs = F.log_softmax(performer_logits, dim=-1)
            x_ppl = -(observer_probs * performer_log_probs).sum(-1).mean()
        return float(log_ppl / x_ppl), int(targets.shape[1])

    def score(self, text: str) -> BinocularsScore:
        ids = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids
        windows, weights = [], []
        for start in range(0, ids.shape[1], WINDOW_TOKENS):
            chunk = ids[:, start:start + WINDOW_TOKENS]
            if chunk.shape[1] < 16:
                continue
            value, count = self._window(chunk.to(self.device))
            windows.append(value)
            weights.append(count)
        if not windows:
            raise ValueError("text too short to score")
        total = sum(weights)
        score = sum(v * w for v, w in zip(windows, weights)) / total
        return BinocularsScore(score=score, tokens=total, windows=[round(v, 4) for v in windows])


_lock = threading.Lock()
_scorers: dict[tuple[str, str], BinocularsScorer] = {}


def get_scorer(observer_id: str = DEFAULT_OBSERVER, performer_id: str = DEFAULT_PERFORMER) -> BinocularsScorer:
    key = (observer_id, performer_id)
    with _lock:
        if key not in _scorers:
            _scorers[key] = BinocularsScorer(observer_id, performer_id)
        return _scorers[key]
