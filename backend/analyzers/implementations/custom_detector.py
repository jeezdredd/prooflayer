import gc
import logging
import os

import torch
from PIL import Image
from transformers import AutoFeatureExtractor, AutoModelForImageClassification

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

RETRAIN_MODEL_DIR = os.environ.get(
    "RETRAIN_MODEL_DIR",
    "/root/.cache/huggingface/prooflayer-retrained",
)
FALLBACK_MODEL = "Nahrawy/AIorNot"

_state = {"model": None, "processor": None, "loaded_path": None}


def _model_path() -> str:
    candidate = os.path.join(RETRAIN_MODEL_DIR, "image")
    if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "config.json")):
        return candidate
    return FALLBACK_MODEL


def _load():
    path = _model_path()
    if _state["model"] is None or _state["loaded_path"] != path:
        logger.info("custom_detector loading from %s", path)
        _state["model"] = AutoModelForImageClassification.from_pretrained(path).eval()
        _state["processor"] = AutoFeatureExtractor.from_pretrained(path)
        _state["loaded_path"] = path
    return _state["model"], _state["processor"]


class CustomDetector(BaseAnalyzer):
    name = "custom_detector"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            image = Image.open(file_path).convert("RGB")
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot open image: {exc}"})

        try:
            model, processor = _load()
            inputs = processor(images=image, return_tensors="pt")
            with torch.no_grad():
                logits = model(**inputs).logits.squeeze()
                if logits.dim() == 0:
                    ai_prob = float(torch.sigmoid(logits).item())
                else:
                    probs = torch.softmax(logits, dim=-1)
                    ai_prob = float(probs[-1].item())
        except Exception as exc:
            logger.warning("custom_detector inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        source = _state["loaded_path"] or FALLBACK_MODEL
        retrained = source != FALLBACK_MODEL
        evidence = {
            "model": "prooflayer-retrained" if retrained else FALLBACK_MODEL,
            "ai_probability": round(ai_prob, 4),
            "retrained": retrained,
        }

        if ai_prob >= 0.85:
            return AnalysisOutput(confidence=0.85, verdict="fake", evidence=evidence)
        if ai_prob >= 0.65:
            return AnalysisOutput(confidence=0.65, verdict="suspicious", evidence=evidence)
        if ai_prob < 0.15:
            return AnalysisOutput(confidence=0.85, verdict="authentic", evidence=evidence)
        if ai_prob < 0.35:
            return AnalysisOutput(confidence=0.65, verdict="authentic", evidence=evidence)
        return AnalysisOutput(confidence=0.4, verdict="inconclusive", evidence=evidence)
