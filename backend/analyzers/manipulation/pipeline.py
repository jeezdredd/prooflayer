import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import torch

from analyzers.manipulation.ai_tiles import score_tiles
from analyzers.manipulation.catnet import catnet_map
from analyzers.manipulation.copymove import copymove_detect
from analyzers.manipulation.fusion import FusionConfig, ManipulationMap, MethodOutputs, fuse
from analyzers.manipulation.imageio import LoadedImage, load_image
from analyzers.manipulation.jpeg_grid import zero_detect
from analyzers.manipulation.safire import safire_predict

WORK_MAX_SIDE = 768


@dataclass
class Models:
    catnet: object | None = None
    safire: object | None = None
    tile_model: object | None = None
    tile_processor: object | None = None
    safire_points: int = 8
    threads: int = 4


@dataclass
class RawResult:
    outputs: MethodOutputs
    timings: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


def work_shape(h: int, w: int, max_side: int = WORK_MAX_SIDE) -> tuple[int, int]:
    s = min(1.0, max_side / max(h, w))
    return max(1, round(h * s)), max(1, round(w * s))


def _resize_prob(prob: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if prob.shape == shape:
        return prob.astype(np.float32)
    return cv2.resize(prob.astype(np.float32), (shape[1], shape[0]), interpolation=cv2.INTER_AREA)


def _resize_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape == shape:
        return mask.astype(bool)
    return cv2.resize(mask.astype(np.float32), (shape[1], shape[0]), interpolation=cv2.INTER_AREA) >= 0.5


def run_methods(image: LoadedImage, models: Models, methods: tuple = ("catnet", "safire", "zero", "copymove", "tiles")) -> RawResult:
    torch.set_num_threads(models.threads)
    h, w = image.height, image.width
    shape = work_shape(h, w)
    out = MethodOutputs(shape=shape, orig_shape=(h, w), is_jpeg=image.is_jpeg, jpeg_quality=image.jpeg_quality)
    timings, extra = {}, {}

    if "catnet" in methods and models.catnet is not None:
        t0, c0 = time.perf_counter(), time.process_time()
        out.catnet = _resize_prob(catnet_map(image, models.catnet), shape)
        timings["catnet"] = (time.perf_counter() - t0, time.process_time() - c0)

    if "safire" in methods and models.safire is not None:
        t0, c0 = time.perf_counter(), time.process_time()
        res = safire_predict(image.rgb, models.safire, points_per_side=models.safire_points)
        out.safire = _resize_prob(res.prob, shape)
        extra["safire"] = {
            "front_area": res.front_area,
            "back_area": res.back_area,
            "cluster_distance": res.cluster_distance,
            "single_cluster": res.single_cluster,
            "front": np.round(res.front * 255).astype(np.uint8),
            "back": np.round(res.back * 255).astype(np.uint8),
        }
        timings["safire"] = (time.perf_counter() - t0, time.process_time() - c0)

    if "zero" in methods:
        t0, c0 = time.perf_counter(), time.process_time()
        z = zero_detect(image.rgb, eps=1.0)
        out.zero_main_grid = z.main_grid
        regions = []
        for r in z.regions:
            src = z.foreign_mask if r.kind == "foreign_grid" else z.missing_mask
            full = np.zeros((h, w), dtype=bool)
            x0, y0, x1, y1 = r.bbox
            full[y0:y1, x0:x1] = src[y0:y1, x0:x1]
            regions.append(
                {
                    "kind": r.kind,
                    "grid": r.grid,
                    "log10_nfa": r.log10_nfa,
                    "mask": _resize_mask(full, shape),
                    "main_density_inside": r.main_density_inside,
                    "main_density_outside": r.main_density_outside,
                }
            )
        out.zero_regions = regions
        extra["zero"] = {
            "main_grid": z.main_grid,
            "main_log10_nfa": z.main_log10_nfa,
            "main_share": z.main_share,
            "n_global": len(z.global_grids),
        }
        timings["zero"] = (time.perf_counter() - t0, time.process_time() - c0)

    if "copymove" in methods:
        t0, c0 = time.perf_counter(), time.process_time()
        cm = copymove_detect(image.rgb, eps=0.01, min_matches=2)
        out.copymove_groups = [
            {
                "matches": g.matches,
                "log10_nfa": g.log10_nfa,
                "target_mask": _resize_mask(g.target_mask, shape),
                "source_mask": _resize_mask(g.source_mask, shape),
            }
            for g in cm.groups[:5]
        ]
        extra["copymove"] = {"keypoints": cm.keypoints, "validated_matches": cm.validated_matches}
        timings["copymove"] = (time.perf_counter() - t0, time.process_time() - c0)

    if "tiles" in methods and models.tile_model is not None:
        t0, c0 = time.perf_counter(), time.process_time()
        ts = score_tiles(image.rgb, models.tile_model, models.tile_processor)
        sy, sx = shape[0] / h, shape[1] / w
        if len(ts.boxes):
            boxes = np.stack(
                [ts.boxes[:, 0] * sx, ts.boxes[:, 1] * sy, ts.boxes[:, 2] * sx, ts.boxes[:, 3] * sy], axis=1
            ).round().astype(int)
        else:
            boxes = np.zeros((0, 4), dtype=int)
        out.tile_boxes = boxes
        out.tile_scores = ts.scores
        timings["tiles"] = (time.perf_counter() - t0, time.process_time() - c0)

    return RawResult(outputs=out, timings=timings, extra=extra)


def analyze_bytes(data: bytes, models: Models, config: FusionConfig | None = None, image_ai_verdict: str | None = None, is_photo: bool | None = None) -> tuple[ManipulationMap, RawResult]:
    image = load_image(data)
    raw = run_methods(image, models)
    raw.outputs.image_ai_verdict = image_ai_verdict
    raw.outputs.is_photo = is_photo
    return fuse(raw.outputs, config or FusionConfig()), raw
