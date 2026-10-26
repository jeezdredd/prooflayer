import numpy as np
import torch
import torch.nn.functional as F

from analyzers.manipulation.catnet_net import CATNet
from analyzers.manipulation.imageio import LoadedImage, estimate_luma_coefficients

DCT_CLIP = 20
TILE = 1024
OVERLAP = 128

_models: dict[str, CATNet] = {}


def load_catnet(weights_path: str) -> CATNet:
    if weights_path not in _models:
        model = CATNet()
        state = torch.load(weights_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        _models[weights_path] = model.eval()
    return _models[weights_path]


def dct_volume(coefs: np.ndarray) -> np.ndarray:
    a = np.minimum(np.abs(coefs), DCT_CLIP)
    vol = np.zeros((DCT_CLIP + 1,) + coefs.shape, dtype=np.float32)
    for k in range(DCT_CLIP + 1):
        vol[k] = a == k
    return vol


def prepare_inputs(image: LoadedImage) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = image.catnet_rgb()
    h, w = rgb.shape[:2]
    hp, wp = -(-h // 8) * 8, -(-w // 8) * 8
    rgb_f = np.full((hp, wp, 3), 127.5, dtype=np.float32)
    rgb_f[:h, :w] = rgb
    rgb_t = ((rgb_f - 127.5) / 127.5).transpose(2, 0, 1)
    coefs = estimate_luma_coefficients(image.jpeg_bytes, image.luma_qtable)[:hp, :wp]
    return rgb_t, coefs, image.luma_qtable.astype(np.float32)


def _tile_starts(size: int, tile: int, overlap: int) -> list[int]:
    if size <= tile:
        return [0]
    step = tile - overlap
    starts = list(range(0, size - tile, step))
    starts.append(size - tile)
    return sorted({(s // 8) * 8 for s in starts})


def _ramp(n: int, overlap: int) -> np.ndarray:
    r = np.ones(n, dtype=np.float32)
    k = min(overlap // 2, n // 2)
    if k > 0:
        edge = np.linspace(0.05, 1.0, k, dtype=np.float32)
        r[:k] = edge
        r[-k:] = edge[::-1]
    return r


@torch.inference_mode()
def catnet_map(image: LoadedImage, model: CATNet, tile: int = TILE, overlap: int = OVERLAP) -> np.ndarray:
    rgb_t, coefs, qtable = prepare_inputs(image)
    _, hp, wp = rgb_t.shape
    q = torch.from_numpy(qtable)[None, None]
    acc = np.zeros((hp, wp), dtype=np.float32)
    wsum = np.zeros((hp, wp), dtype=np.float32)
    ys = _tile_starts(hp, tile, overlap)
    xs = _tile_starts(wp, tile, overlap)
    for y0 in ys:
        for x0 in xs:
            y1, x1 = min(y0 + tile, hp), min(x0 + tile, wp)
            vol = dct_volume(coefs[y0:y1, x0:x1])
            x = np.concatenate([rgb_t[:, y0:y1, x0:x1], vol], axis=0)
            logits = model(torch.from_numpy(np.ascontiguousarray(x))[None], q)
            prob = F.softmax(logits, dim=1)[:, 1:2]
            prob = F.interpolate(prob, size=(y1 - y0, x1 - x0), mode="bilinear", align_corners=False)[0, 0].numpy()
            single = len(ys) == 1 and len(xs) == 1
            wy = np.ones(y1 - y0, dtype=np.float32) if single else _ramp(y1 - y0, overlap)
            wx = np.ones(x1 - x0, dtype=np.float32) if single else _ramp(x1 - x0, overlap)
            wgt = wy[:, None] * wx[None, :]
            acc[y0:y1, x0:x1] += prob * wgt
            wsum[y0:y1, x0:x1] += wgt
    out = acc / np.maximum(wsum, 1e-6)
    return out[: image.height, : image.width]
