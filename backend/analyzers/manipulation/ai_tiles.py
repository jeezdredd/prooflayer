from dataclasses import dataclass

import cv2
import numpy as np
import torch
from transformers import AutoImageProcessor, AutoModelForImageClassification

MODEL_NAME = "buildborderless/CommunityForensics-DeepfakeDet-ViT"
TILE = 384
STRIDE = 384
MAX_TILES = 32
BATCH = 8
MIN_TEXTURE = 4.0

_state: dict = {}


@dataclass
class TileScores:
    boxes: np.ndarray
    scores: np.ndarray
    texture: np.ndarray


def load_tile_model():
    if "model" not in _state:
        _state["model"] = AutoModelForImageClassification.from_pretrained(MODEL_NAME, use_safetensors=True).eval()
        _state["processor"] = AutoImageProcessor.from_pretrained(MODEL_NAME)
    return _state["model"], _state["processor"]


def tile_boxes(h: int, w: int, tile: int = TILE, stride: int = STRIDE) -> list[tuple[int, int, int, int]]:
    if h < tile or w < tile:
        return []
    ys = list(range(0, h - tile + 1, stride))
    xs = list(range(0, w - tile + 1, stride))
    if ys[-1] != h - tile:
        ys.append(h - tile)
    if xs[-1] != w - tile:
        xs.append(w - tile)
    return [(x, y, x + tile, y + tile) for y in ys for x in xs]


def texture_score(gray: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = box
    patch = gray[y0:y1, x0:x1]
    lap = cv2.Laplacian(patch, cv2.CV_32F)
    return float(np.abs(lap).mean())


@torch.inference_mode()
def score_tiles(rgb: np.ndarray, model, processor, extra_boxes=None, max_tiles: int = MAX_TILES) -> TileScores:
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    boxes = tile_boxes(h, w)
    tex = [texture_score(gray, b) for b in boxes]
    order = sorted(range(len(boxes)), key=lambda i: -tex[i])
    chosen = [boxes[i] for i in order if tex[i] >= MIN_TEXTURE][:max_tiles]
    for b in extra_boxes or []:
        if b not in chosen:
            chosen.append(b)
    if not chosen:
        return TileScores(np.zeros((0, 4), int), np.zeros(0, np.float32), np.zeros(0, np.float32))
    scores = []
    for start in range(0, len(chosen), BATCH):
        crops = [rgb[y0:y1, x0:x1] for x0, y0, x1, y1 in chosen[start : start + BATCH]]
        inputs = processor(images=crops, return_tensors="pt", do_resize=False, do_center_crop=False)
        logits = model(**inputs).logits
        if logits.shape[-1] == 1:
            probs = torch.sigmoid(logits[:, 0])
        else:
            probs = torch.softmax(logits, dim=-1)[:, -1]
        scores.extend(probs.tolist())
    return TileScores(
        boxes=np.array(chosen, dtype=int),
        scores=np.array(scores, dtype=np.float32),
        texture=np.array([texture_score(gray, b) for b in chosen], dtype=np.float32),
    )
