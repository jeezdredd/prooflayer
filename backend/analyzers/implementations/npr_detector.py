import gc
import logging

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

MODEL_NAME = "Wvolf/ViT_Deepfake_Detection"

_state = {"model": None, "processor": None}


def _load():
    if _state["model"] is None:
        _state["model"] = AutoModelForImageClassification.from_pretrained(MODEL_NAME, use_safetensors=True).eval()
        try:
            _state["processor"] = AutoImageProcessor.from_pretrained(MODEL_NAME)
        except Exception:
            from transformers import ViTImageProcessor
            _state["processor"] = ViTImageProcessor(
                size={"height": 224, "width": 224},
                do_normalize=True,
                image_mean=[0.5, 0.5, 0.5],
                image_std=[0.5, 0.5, 0.5],
            )
        logger.info("npr_detector loaded %s", MODEL_NAME)
    return _state["model"], _state["processor"]


def _fake_index(label2id: dict) -> int:
    for k, v in label2id.items():
        if k.lower() in ("fake", "ai", "deepfake", "synthetic", "1"):
            return v
    return 1


class NPRDetector(BaseAnalyzer):
    name = "npr_detector"
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
                probs = torch.softmax(outputs.logits, dim=-1).squeeze()
                label2id = getattr(model.config, "label2id", {"REAL": 0, "FAKE": 1})
                fake_idx = _fake_index(label2id)
                ai_prob = float(probs[fake_idx].item())
        except Exception as exc:
            logger.warning("npr_detector inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        evidence = {
            "model": "vit-deepfake-detector",
            "ai_probability": round(ai_prob, 4),
            "training_corpus": "ViT fine-tuned for deepfake detection",
        }

        if ai_prob >= 0.85:
            confidence = 0.8
            verdict = "fake"
        elif ai_prob >= 0.65:
            confidence = 0.6
            verdict = "suspicious"
        elif ai_prob < 0.15:
            confidence = 0.8
            verdict = "authentic"
        elif ai_prob < 0.35:
            confidence = 0.6
            verdict = "authentic"
        else:
            confidence = 0.4
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
