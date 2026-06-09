import gc
import logging

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

MODEL_NAME = "prithivMLmods/Deep-Fake-Detector-v2-Model"

_state = {"model": None, "processor": None}


def _load():
    if _state["model"] is None:
        _state["model"] = AutoModelForImageClassification.from_pretrained(
            MODEL_NAME, local_files_only=False
        ).eval()
        _state["processor"] = AutoImageProcessor.from_pretrained(MODEL_NAME)
        logger.info("siglip_detector loaded %s", MODEL_NAME)
    return _state["model"], _state["processor"]


def _ai_probability(model, probs) -> tuple[float, dict[str, float]]:
    id2label = model.config.id2label
    per_label = {id2label[i]: float(probs[i]) for i in range(len(probs))}
    fake_total = 0.0
    real_total = 0.0
    fake_keys = ("fake", "ai", "artificial", "synthetic", "generated", "deepfake")
    real_keys = ("real", "human", "authentic", "natural", "genuine")
    for label, prob in per_label.items():
        l = label.lower().strip()
        if any(k in l for k in fake_keys):
            fake_total += prob
        elif any(k in l for k in real_keys):
            real_total += prob
    if fake_total + real_total == 0:
        return 0.5, per_label
    return fake_total / (fake_total + real_total), per_label


class SigLIPDetector(BaseAnalyzer):
    name = "siglip_detector"
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
                outputs = model(**inputs)
                probs = torch.softmax(outputs.logits, dim=1).squeeze(0)
            ai_prob, per_label = _ai_probability(model, probs)
        except Exception as exc:
            logger.warning("siglip_detector inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        per_label_rounded = {k: round(v, 4) for k, v in per_label.items()}
        evidence = {
            "model": "siglip-deepfake-v2",
            "ai_probability": round(ai_prob, 4),
            "per_label": per_label_rounded,
        }

        if ai_prob >= 0.88:
            confidence = 0.85
            verdict = "fake"
        elif ai_prob >= 0.70:
            confidence = 0.65
            verdict = "suspicious"
        elif ai_prob < 0.15:
            confidence = 0.85
            verdict = "authentic"
        elif ai_prob < 0.30:
            confidence = 0.65
            verdict = "authentic"
        else:
            confidence = 0.4
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
