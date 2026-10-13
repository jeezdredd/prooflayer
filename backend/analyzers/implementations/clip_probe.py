import logging
import os

import numpy as np
from PIL import Image

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.clip_probe_core import DEFAULT_BACKBONE, embed_images, load_head, predict
from analyzers.implementations.custom_detector import RETRAIN_MODEL_DIR, apply_calibration, load_calibration
from content.models import Submission

logger = logging.getLogger(__name__)

PROBE_SUBDIR = "clip_probe"

_state = {"head": None, "calibration": None, "dir": None}


def probe_dir() -> str:
    return os.path.join(RETRAIN_MODEL_DIR, PROBE_SUBDIR)


def _load():
    directory = probe_dir()
    if _state["head"] is None or _state["dir"] != directory:
        _state["head"] = load_head(directory)
        _state["calibration"] = load_calibration(directory)
        _state["dir"] = directory
    return _state["head"], _state["calibration"]


def _stored_embedding(submission_id) -> np.ndarray | None:
    if not submission_id:
        return None
    vector = Submission.objects.filter(id=submission_id).values_list("clip_embedding", flat=True).first()
    if vector is None:
        return None
    return np.asarray(vector, dtype=np.float32)


class CLIPProbeDetector(BaseAnalyzer):
    """Logistic-regression probe over frozen CLIP image features.

    A different backbone from community_forensics and the retrained detector (both ViT
    fine-tunes of the same weights), so its mistakes are not the same mistakes.
    """

    name = "clip_probe"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        head, knots = _load()
        if head is None:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"no probe head in {probe_dir()}"})
        backbone = head.get("backbone", DEFAULT_BACKBONE)
        try:
            features = None
            if backbone == DEFAULT_BACKBONE:
                features = _stored_embedding(metadata.get("submission_id"))
            source = "stored" if features is not None else "computed"
            if features is None:
                with Image.open(file_path) as img:
                    features = embed_images([img.convert("RGB")], backbone)[0]
            if features.shape[0] != head["weights"].shape[0]:
                return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "embedding size does not match probe head"})
            raw = float(predict(features[None, :], head["weights"], head["bias"])[0])
        except Exception as exc:
            logger.warning("clip_probe failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})

        ai_prob = apply_calibration(raw, knots)
        evidence = {
            "model": f"CLIP probe ({backbone})",
            "ai_probability": round(ai_prob, 4),
            "raw_probability": round(raw, 4),
            "calibrated": bool(knots),
            "features": source,
        }
        if ai_prob >= 0.85:
            return AnalysisOutput(confidence=0.8, verdict="fake", evidence=evidence)
        if ai_prob >= 0.65:
            return AnalysisOutput(confidence=0.6, verdict="suspicious", evidence=evidence)
        if ai_prob < 0.15:
            return AnalysisOutput(confidence=0.8, verdict="authentic", evidence=evidence)
        if ai_prob < 0.35:
            return AnalysisOutput(confidence=0.6, verdict="authentic", evidence=evidence)
        return AnalysisOutput(confidence=0.4, verdict="inconclusive", evidence=evidence)
