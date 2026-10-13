import hashlib
import json
import os

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from analyzers._device import get_device

DEFAULT_BACKBONE = "openai/clip-vit-base-patch32"
EMBED_BATCH = 16

_backbones: dict[str, tuple] = {}


def load_backbone(name: str):
    if name not in _backbones:
        processor = CLIPProcessor.from_pretrained(name)
        try:
            model = CLIPModel.from_pretrained(name, use_safetensors=True).eval()
        except Exception:
            model = CLIPModel.from_pretrained(name).eval()
        _backbones[name] = (model.to(get_device()), processor)
    return _backbones[name]


def embed_images(images: list[Image.Image], backbone: str) -> np.ndarray:
    model, processor = load_backbone(backbone)
    inputs = processor(images=images, return_tensors="pt")
    inputs = {k: v.to(get_device()) for k, v in inputs.items()}
    with torch.no_grad():
        feats = model.get_image_features(**inputs)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
    return feats.float().cpu().numpy()


def embed_paths(paths: list[str], backbone: str, cache_dir: str | None = None) -> np.ndarray:
    cache_file = None
    if cache_dir:
        digest = hashlib.sha256((backbone + "|" + "|".join(paths)).encode()).hexdigest()[:16]
        cache_file = os.path.join(cache_dir, f"clip_{digest}.npy")
        if os.path.exists(cache_file):
            return np.load(cache_file)
    out = []
    for start in range(0, len(paths), EMBED_BATCH):
        chunk = []
        for path in paths[start:start + EMBED_BATCH]:
            with Image.open(path) as img:
                chunk.append(img.convert("RGB"))
        out.append(embed_images(chunk, backbone))
    feats = np.concatenate(out) if out else np.zeros((0, 1), dtype=np.float32)
    if cache_file:
        os.makedirs(cache_dir, exist_ok=True)
        np.save(cache_file, feats)
    return feats


def train_logreg(x: np.ndarray, y: np.ndarray, l2: float = 1e-3, steps: int = 300) -> tuple[np.ndarray, float]:
    """Class-balanced L2 logistic regression via LBFGS. Returns (weights, bias)."""
    xt = torch.tensor(x, dtype=torch.float64)
    yt = torch.tensor(y, dtype=torch.float64)
    pos = float(yt.sum())
    neg = float(len(yt) - pos)
    sample_w = torch.where(yt > 0.5, len(yt) / (2 * pos), len(yt) / (2 * neg))
    w = torch.zeros(xt.shape[1], dtype=torch.float64, requires_grad=True)
    b = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([w, b], lr=1.0, max_iter=steps, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        logits = xt @ w + b
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, yt, weight=sample_w)
        loss = loss + l2 * (w * w).sum()
        loss.backward()
        return loss

    opt.step(closure)
    return w.detach().numpy(), float(b.detach().item())


def predict(x: np.ndarray, weights: np.ndarray, bias: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(x @ weights + bias)))


def save_head(directory: str, backbone: str, weights: np.ndarray, bias: float, meta: dict) -> None:
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "head.json"), "w") as fh:
        json.dump({"backbone": backbone, "bias": bias, "weights": [round(float(v), 7) for v in weights]}, fh)
    with open(os.path.join(directory, "training_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)


def load_head(directory: str) -> dict | None:
    path = os.path.join(directory, "head.json")
    if not os.path.isfile(path):
        return None
    with open(path) as fh:
        head = json.load(fh)
    head["weights"] = np.asarray(head["weights"], dtype=np.float32)
    return head
