import io
import logging
import os
import time

import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.implementations.clip_detector import _photographic_score
from analyzers.manipulation.ai_tiles import load_tile_model
from analyzers.manipulation.catnet import load_catnet
from analyzers.manipulation.fusion import STATUS_REGIONS, FusionConfig
from analyzers.manipulation.pipeline import Models, analyze_bytes
from analyzers.manipulation.safire import load_safire

logger = logging.getLogger(__name__)

CATNET_FILE = "catnet_v2_state.pt"
SAFIRE_FILE = "safire_state.pt"
MAP_MAX_SIDE = 768
CALIBRATION = "2026-10-26 manipulation-map v1 (authentic p99.5 / p99.9 per input class, 215 calibration photos)"
FITTED = {
    "t": {
        "catnet": {"jpeg": 0.9174, "all": 0.8798, "nonjpeg": 0.8544},
        "safire": {"all": 0.9873},
    },
    "strong": {
        "catnet": {"jpeg": 0.985, "all": 0.985, "nonjpeg": 0.8756},
        "safire": {"all": 0.999},
    },
    "zero_min_fill": 0.05,
    "min_texture_share": 0.4,
    "copymove_min_matches": 2,
    "tile_threshold": 0.9992,
}

_state = {"models": None}
ORIENTATION_TAG = 0x0112
TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def orient_bbox(bbox, size: tuple[int, int], orientation: int) -> list[int]:
    w, h = size
    x0, y0, x1, y1 = bbox
    if orientation == 2:
        return [w - x1, y0, w - x0, y1]
    if orientation == 3:
        return [w - x1, h - y1, w - x0, h - y0]
    if orientation == 4:
        return [x0, h - y1, x1, h - y0]
    if orientation == 5:
        return [y0, x0, y1, x1]
    if orientation == 6:
        return [h - y1, x0, h - y0, x1]
    if orientation == 7:
        return [h - y1, w - x1, h - y0, w - x0]
    if orientation == 8:
        return [y0, w - x1, y1, w - x0]
    return [x0, y0, x1, y1]


def shown_size(size: tuple[int, int], orientation: int) -> list[int]:
    return [size[1], size[0]] if orientation in (5, 6, 7, 8) else [size[0], size[1]]


def fusion_config(use_safire: bool) -> FusionConfig:
    return FusionConfig(
        t=FITTED["t"],
        strong=FITTED["strong"],
        zero_min_fill=FITTED["zero_min_fill"],
        min_texture_share=FITTED["min_texture_share"],
        copymove_min_matches=FITTED["copymove_min_matches"],
        tile_threshold=FITTED["tile_threshold"],
        use_learned_pair=use_safire,
    )


def weights_dir() -> str:
    return settings.MANIPULATION_WEIGHTS_DIR


def _models() -> Models | None:
    if _state["models"] is not None:
        return _state["models"]
    catnet_path = os.path.join(weights_dir(), CATNET_FILE)
    if not os.path.isfile(catnet_path):
        return None
    models = Models(catnet=load_catnet(catnet_path), threads=settings.MANIPULATION_THREADS)
    safire_path = os.path.join(weights_dir(), SAFIRE_FILE)
    if settings.MANIPULATION_SAFIRE and os.path.isfile(safire_path):
        models.safire = load_safire(safire_path)
    models.tile_model, models.tile_processor = load_tile_model()
    _state["models"] = models
    return models


def save_map(fmap: np.ndarray, submission_id, orientation: int = 1) -> tuple[str, list[int]] | None:
    if not submission_id or fmap is None:
        return None
    gray = Image.fromarray(np.round(np.clip(fmap, 0.0, 1.0) * 255).astype(np.uint8), "L")
    if orientation in TRANSPOSE:
        gray = gray.transpose(TRANSPOSE[orientation])
    gray.thumbnail((MAP_MAX_SIDE, MAP_MAX_SIDE))
    buf = io.BytesIO()
    gray.save(buf, format="PNG")
    path = f"manipulation/{submission_id}.png"
    if default_storage.exists(path):
        default_storage.delete(path)
    return default_storage.save(path, ContentFile(buf.getvalue())), list(gray.size)


def abstain(reason: str, **extra) -> AnalysisOutput:
    evidence = {"status": "abstain", "reason": reason, "manipulation_suspected": False, "regions": [], **extra}
    return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)


class ManipulationMapAnalyzer(BaseAnalyzer):
    name = "manipulation_map"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            with open(file_path, "rb") as fh:
                data = fh.read()
            image = Image.open(io.BytesIO(data))
            size = image.size
            orientation = int(image.getexif().get(ORIENTATION_TAG, 1) or 1)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot open image: {exc}"})
        if size[0] * size[1] > settings.MANIPULATION_MAX_PIXELS:
            return abstain("too_large", image_size=list(size))
        models = _models()
        if models is None:
            return abstain("unavailable", image_size=list(size))
        try:
            is_photo = bool(_photographic_score(image.convert("RGB"))["is_photographic"])
        except Exception:
            is_photo = None
        started = time.perf_counter()
        try:
            result, raw = analyze_bytes(data, models, fusion_config(models.safire is not None), is_photo=is_photo)
        except Exception as exc:
            logger.warning("manipulation_map failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)[:200]})
        summary = result.summary()
        regions = summary["regions"]
        evidence = {
            "status": summary["status"],
            "reason": summary["reason"],
            "manipulation_suspected": any(r["confidence"] == "high" for r in regions),
            "score": round(float(summary["score"]), 4),
            "input_class": summary["input_class"],
            "regions": [
                {
                    **r,
                    "bbox": orient_bbox([int(v) for v in r["bbox"]], size, orientation),
                    "score": round(float(r["score"]), 4),
                    "area_share": round(float(r["area_share"]), 4),
                }
                for r in regions
            ],
            "method_scores": {k: round(float(v), 4) for k, v in summary["method_scores"].items()},
            "image_size": shown_size(size, orientation),
            "calibration": CALIBRATION,
            "timings_s": {k: round(v[0], 2) for k, v in raw.timings.items()},
            "seconds": round(time.perf_counter() - started, 2),
        }
        if summary["status"] == STATUS_REGIONS:
            saved = save_map(result.map, metadata.get("submission_id"), orientation)
            if saved:
                evidence["map_path"], evidence["map_size"] = saved
        return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
