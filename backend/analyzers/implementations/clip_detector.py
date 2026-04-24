import logging

import torch
from PIL import Image
from transformers import AutoFeatureExtractor, AutoModelForImageClassification

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

MODEL_NAME = "Nahrawy/AIorNot"

_model_cache = {}


def _get_model():
    if "model" not in _model_cache:
        model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)
        feature_extractor = AutoFeatureExtractor.from_pretrained(MODEL_NAME)
        model.eval()
        _model_cache["model"] = model
        _model_cache["feature_extractor"] = feature_extractor
        logger.info("AI image detector model loaded: %s", MODEL_NAME)
    return _model_cache["model"], _model_cache["feature_extractor"]


class AIImageDetector(BaseAnalyzer):
    name = "ai_detector"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        model, feature_extractor = _get_model()

        image = Image.open(file_path).convert("RGB")
        inputs = feature_extractor(images=image, return_tensors="pt")

        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1).squeeze(0)

        id2label = model.config.id2label
        label_probs = {id2label[i]: float(probs[i]) for i in range(len(probs))}

        ai_prob = label_probs.get("AI", label_probs.get("artificial", 0.0))
        human_prob = label_probs.get("Real", label_probs.get("human", 0.0))

        evidence = {
            "ai_probability": round(ai_prob, 4),
            "human_probability": round(human_prob, 4),
            "per_label_scores": {k: round(v, 4) for k, v in label_probs.items()},
            "model": MODEL_NAME,
        }

        if ai_prob > 0.75:
            confidence = 0.9
            verdict = "fake"
        elif ai_prob > 0.55:
            confidence = 0.7
            verdict = "suspicious"
        elif human_prob > 0.75:
            confidence = 0.8
            verdict = "authentic"
        else:
            confidence = 0.5
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
