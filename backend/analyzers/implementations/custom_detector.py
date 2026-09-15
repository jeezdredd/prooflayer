import gc
import json
import logging
import os

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from analyzers._device import get_device, inputs_to_device, to_device
from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

RETRAIN_MODEL_DIR = os.environ.get(
    "RETRAIN_MODEL_DIR",
    "/root/.cache/huggingface/prooflayer-retrained",
)
FALLBACK_MODEL = "Nahrawy/AIorNot"

_state = {"model": None, "processor": None, "loaded_path": None, "calibration": None}
CALIBRATION_FILENAME = "calibration.json"


def load_calibration(path: str) -> list[tuple[float, float]] | None:
    """Monotone knots shipped next to a retrained model, or None for the raw score."""
    cal_path = os.path.join(path, CALIBRATION_FILENAME)
    if not os.path.isfile(cal_path):
        return None
    try:
        with open(cal_path) as fh:
            knots = json.load(fh)["knots"]
        knots = [(float(x), float(y)) for x, y in knots]
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("custom_detector: unreadable %s, using raw scores", cal_path)
        return None
    if len(knots) < 2 or knots != sorted(knots) or knots[0] != (0.0, 0.0) or knots[-1] != (1.0, 1.0):
        logger.warning("custom_detector: rejected calibration knots %s", knots)
        return None
    return knots


def apply_calibration(raw: float, knots) -> float:
    raw = min(max(float(raw), 0.0), 1.0)
    if not knots:
        return raw
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if raw <= x1:
            return y1 if x1 == x0 else y0 + (y1 - y0) * (raw - x0) / (x1 - x0)
    return 1.0


def _model_path() -> str:
    candidate = os.path.join(RETRAIN_MODEL_DIR, "image")
    if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "config.json")):
        return candidate
    return FALLBACK_MODEL


def training_meta(path: str) -> dict:
    """Provenance written by retrain_detector next to the weights, if any."""
    meta_path = os.path.join(path, "training_meta.json")
    if not os.path.isfile(meta_path):
        return {}
    try:
        with open(meta_path) as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {
        "base_model": meta.get("base_model"),
        "trained_at": meta.get("trained_at"),
        "epochs": meta.get("epochs"),
        "train_counts": meta.get("train_counts"),
        "sources": len(meta.get("sources") or []),
        "eval_accuracy": meta.get("eval_accuracy"),
    }


AI_LABEL_KEYS = ("ai", "fake", "artificial", "synthetic", "generated", "deepfake")
REAL_LABEL_KEYS = ("real", "human", "authentic", "natural", "genuine", "realism")


def _load():
    path = _model_path()
    if _state["model"] is None or _state["loaded_path"] != path:
        logger.info("custom_detector loading from %s", path)
        try:
            model = AutoModelForImageClassification.from_pretrained(path, use_safetensors=True).eval()
        except Exception:
            model = AutoModelForImageClassification.from_pretrained(path).eval()
        _state["model"] = to_device(model)
        _state["processor"] = AutoImageProcessor.from_pretrained(path)
        _state["loaded_path"] = path
        _state["calibration"] = load_calibration(path) if os.path.isdir(path) else None
        logger.info("custom_detector loaded %s on %s", path, get_device())
    return _state["model"], _state["processor"]


def _ai_probability(model, probs) -> float:
    id2label = getattr(model.config, "id2label", None) or {}
    ai_total = 0.0
    real_total = 0.0
    for idx in range(len(probs)):
        label = str(id2label.get(idx, id2label.get(str(idx), ""))).lower().strip()
        value = float(probs[idx])
        if any(k in label for k in REAL_LABEL_KEYS):
            real_total += value
        elif any(k in label for k in AI_LABEL_KEYS):
            ai_total += value
    if ai_total + real_total == 0:
        logger.warning("custom_detector: unrecognised labels %s, falling back to last index", id2label)
        return float(probs[-1])
    return ai_total / (ai_total + real_total)


class CustomDetector(BaseAnalyzer):
    name = "custom_detector"
    version = "1.3.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            image = Image.open(file_path).convert("RGB")
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot open image: {exc}"})

        try:
            model, processor = _load()
            inputs = inputs_to_device(processor(images=image, return_tensors="pt"))
            with torch.no_grad():
                logits = model(**inputs).logits.squeeze().cpu()
                if logits.dim() == 0:
                    ai_prob = float(torch.sigmoid(logits).item())
                else:
                    ai_prob = _ai_probability(model, torch.softmax(logits, dim=-1))
        except Exception as exc:
            logger.warning("custom_detector inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        source = _state["loaded_path"] or FALLBACK_MODEL
        retrained = source != FALLBACK_MODEL
        raw_prob = ai_prob
        knots = _state["calibration"]
        ai_prob = apply_calibration(raw_prob, knots)
        evidence = {
            "model": "prooflayer-retrained" if retrained else FALLBACK_MODEL,
            "ai_probability": round(ai_prob, 4),
            "raw_probability": round(raw_prob, 4),
            "calibrated": bool(knots),
            "retrained": retrained,
        }
        if retrained:
            evidence["training"] = training_meta(source)

        if ai_prob >= 0.85:
            return AnalysisOutput(confidence=0.85, verdict="fake", evidence=evidence)
        if ai_prob >= 0.65:
            return AnalysisOutput(confidence=0.65, verdict="suspicious", evidence=evidence)
        if ai_prob < 0.15:
            return AnalysisOutput(confidence=0.85, verdict="authentic", evidence=evidence)
        if ai_prob < 0.35:
            return AnalysisOutput(confidence=0.65, verdict="authentic", evidence=evidence)
        return AnalysisOutput(confidence=0.4, verdict="inconclusive", evidence=evidence)
