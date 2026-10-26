from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage

MIN_AREA_SHARE = 0.003
MIN_SIDE = 32
PIXEL_THRESHOLD = 0.5
TEXTURE_STD = 2.0
TEXTURE_WINDOW = 5


@dataclass
class Component:
    mask: np.ndarray
    score: float
    area_share: float
    bbox: tuple[int, int, int, int]
    solidity: float
    texture_share: float = 1.0


def min_area(shape: tuple[int, int], ref_shape: tuple[int, int] | None = None) -> int:
    h, w = shape
    side = MIN_SIDE
    if ref_shape is not None:
        side = MIN_SIDE * h / ref_shape[0]
    return int(max(MIN_AREA_SHARE * h * w, side * side))


def solidity(mask: np.ndarray) -> float:
    pts = cv2.findNonZero(mask.astype(np.uint8))
    if pts is None or len(pts) < 3:
        return 1.0
    hull = cv2.convexHull(pts)
    area = cv2.contourArea(hull)
    return float(mask.sum() / area) if area > 0 else 1.0


def texture_map(rgb: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    small = cv2.resize(rgb, (shape[1], shape[0]), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)
    k = (TEXTURE_WINDOW, TEXTURE_WINDOW)
    mean = cv2.blur(gray, k)
    return np.sqrt(np.maximum(cv2.blur(gray * gray, k) - mean * mean, 0.0))


def texture_share(mask: np.ndarray, texture: np.ndarray | None) -> float:
    if texture is None or not mask.any():
        return 1.0
    return float((texture[mask] >= TEXTURE_STD).mean())


def fill_ratio(mask: np.ndarray) -> float:
    x0, y0, x1, y1 = bbox_of(mask)
    area = (x1 - x0) * (y1 - y0)
    return float(mask.sum() / area) if area else 0.0


def components(
    prob: np.ndarray,
    threshold: float = PIXEL_THRESHOLD,
    ref_shape: tuple[int, int] | None = None,
    min_pixels: int | None = None,
    texture: np.ndarray | None = None,
) -> list[Component]:
    binary = prob >= threshold
    binary = ndimage.binary_opening(binary, structure=np.ones((3, 3), dtype=bool))
    labels, n = ndimage.label(binary, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return []
    need = min_pixels if min_pixels is not None else min_area(prob.shape, ref_shape)
    total = prob.shape[0] * prob.shape[1]
    out = []
    objects = ndimage.find_objects(labels)
    sizes = np.bincount(labels.ravel(), minlength=n + 1)
    sums = ndimage.sum_labels(prob, labels, index=np.arange(n + 1))
    for lab in range(1, n + 1):
        if sizes[lab] < need:
            continue
        sl = objects[lab - 1]
        mask = labels == lab
        out.append(
            Component(
                mask=mask,
                score=float(sums[lab] / sizes[lab]),
                area_share=float(sizes[lab] / total),
                bbox=(sl[1].start, sl[0].start, sl[1].stop, sl[0].stop),
                solidity=solidity(mask[sl]),
                texture_share=texture_share(mask, texture),
            )
        )
    out.sort(key=lambda c: -c.score)
    return out


def window_max(prob: np.ndarray, ref_shape: tuple[int, int] | None = None) -> float:
    side = max(3, int(np.sqrt(min_area(prob.shape, ref_shape))))
    return float(ndimage.uniform_filter(prob.astype(np.float32), size=side, mode="nearest").max())


def image_score(
    prob: np.ndarray,
    ref_shape: tuple[int, int] | None = None,
    texture: np.ndarray | None = None,
    min_texture_share: float = 0.0,
) -> float:
    comps = [c for c in components(prob, ref_shape=ref_shape, texture=texture) if c.texture_share >= min_texture_share]
    if comps:
        return max(c.score for c in comps)
    return 0.5 * min(window_max(prob, ref_shape), 0.999)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    return float(np.logical_and(a, b).sum() / union)


def bbox_of(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return (0, 0, 0, 0)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
