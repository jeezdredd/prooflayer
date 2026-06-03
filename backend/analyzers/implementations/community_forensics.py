import gc
import logging

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

MODEL_NAME = "buildborderless/CommunityForensics-DeepfakeDet-ViT"

_state = {"model": None, "processor": None}


def _load():
    if _state["model"] is None:
        _state["model"] = AutoModelForImageClassification.from_pretrained(MODEL_NAME, use_safetensors=True).eval()
        try:
            _state["processor"] = AutoImageProcessor.from_pretrained(MODEL_NAME)
        except Exception:
            from transformers import ViTImageProcessor
            _state["processor"] = ViTImageProcessor(size={"height": 384, "width": 384}, do_normalize=True, image_mean=[0.5, 0.5, 0.5], image_std=[0.5, 0.5, 0.5])
        logger.info("community_forensics loaded %s", MODEL_NAME)
    return _state["model"], _state["processor"]


class CommunityForensicsDetector(BaseAnalyzer):
    name = "community_forensics"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            image = Image.open(file_path).convert("RGB").resize((384, 384))
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot open image: {exc}"})

        try:
            model, processor = _load()
            inputs = processor(images=image, return_tensors="pt", do_resize=False)
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits.squeeze()
                if logits.dim() == 0:
                    ai_prob = float(torch.sigmoid(logits).item())
                else:
                    probs = torch.softmax(logits, dim=-1)
                    ai_prob = float(probs[-1].item())
        except Exception as exc:
            logger.warning("community_forensics inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        evidence = {
            "model": "community-forensics-vit-s16-384",
            "ai_probability": round(ai_prob, 4),
            "training_corpus": "2.7M images from 4803 generators (NeurIPS 2024)",
        }

        if ai_prob >= 0.85:
            confidence = 0.85
            verdict = "fake"
        elif ai_prob >= 0.65:
            confidence = 0.65
            verdict = "suspicious"
        elif ai_prob < 0.15:
            confidence = 0.85
            verdict = "authentic"
        elif ai_prob < 0.35:
            confidence = 0.65
            verdict = "authentic"
        else:
            confidence = 0.4
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
