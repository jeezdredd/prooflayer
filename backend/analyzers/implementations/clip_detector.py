import gc
import logging

import numpy as np
import torch
from PIL import Image
from transformers import AutoFeatureExtractor, AutoModelForImageClassification

from analyzers._device import get_device, inputs_to_device, to_device
from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

ENSEMBLE_MODELS = [
    "dima806/ai_vs_real_image_detection",
    "umm-maybe/AI-image-detector",
]

_model_cache: dict[str, tuple] = {}
_MAX_CACHED = 1


def _load_model(name: str):
    if name not in _model_cache:
        if len(_model_cache) >= _MAX_CACHED:
            evict_key = next(iter(_model_cache))
            del _model_cache[evict_key]
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("AI detector evicted cached model: %s", evict_key)
        model = AutoModelForImageClassification.from_pretrained(name, use_safetensors=True)
        extractor = AutoFeatureExtractor.from_pretrained(name)
        model.eval()
        model = to_device(model)
        _model_cache[name] = (model, extractor)
        logger.info("AI detector model loaded: %s on %s", name, get_device())
    return _model_cache[name]


def _ai_prob_from_outputs(model, probs) -> float:
    id2label = model.config.id2label
    label_probs = {id2label[i].lower().strip(): float(probs[i]) for i in range(len(probs))}
    ai_keys = ("ai", "artificial", "fake", "synthetic", "generated", "ai-generated", "ai_generated")
    real_keys = ("real", "human", "authentic", "natural", "genuine")
    ai_total = sum(v for k, v in label_probs.items() if any(s in k for s in ai_keys))
    real_total = sum(v for k, v in label_probs.items() if any(s in k for s in real_keys))
    if ai_total + real_total == 0:
        return 0.5
    return ai_total / (ai_total + real_total)


def _photographic_score(image: Image.Image) -> dict:
    img_small = image.resize((256, 256))
    arr = np.array(img_small).reshape(-1, 3)
    unique_colors = len(np.unique(arr // 4, axis=0))

    gray = np.array(img_small.convert("L"), dtype=np.float32)
    hist, _ = np.histogram(gray, bins=64, range=(0, 256))
    p = hist / max(hist.sum(), 1)
    entropy = float(-np.sum(p * np.log2(p + 1e-10)))

    flat_score = float(np.mean(np.abs(np.diff(gray, axis=0))) + np.mean(np.abs(np.diff(gray, axis=1))))

    is_photo = unique_colors > 4000 and entropy > 5.2 and flat_score > 5.0

    return {
        "unique_colors_q4": int(unique_colors),
        "entropy": round(entropy, 3),
        "edge_density": round(flat_score, 3),
        "is_photographic": bool(is_photo),
    }


def _run_one(name: str, idx: int, image: Image.Image) -> dict:
    label = f"classifier_{idx + 1}"
    try:
        model, extractor = _load_model(name)
        inputs = inputs_to_device(extractor(images=image, return_tensors="pt"))
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1).squeeze(0).cpu()
        ai_prob = _ai_prob_from_outputs(model, probs)
        id2label = model.config.id2label
        return {
            "classifier": label,
            "ai_probability": round(ai_prob, 4),
            "per_label": {id2label[i]: round(float(probs[i]), 4) for i in range(len(probs))},
            "ok": True,
        }
    except Exception as exc:
        logger.warning("AI detector model %s failed: %s", name, exc)
        return {"classifier": label, "ok": False, "error": str(exc)}


class AIImageDetector(BaseAnalyzer):
    name = "ai_detector"
    version = "2.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        image = Image.open(file_path).convert("RGB")
        skip_photo_check = bool(metadata.get("skip_photo_check"))

        photo_check = _photographic_score(image)
        if not skip_photo_check and not photo_check["is_photographic"]:
            return AnalysisOutput(
                confidence=0.5,
                verdict="inconclusive",
                evidence={
                    "note": "image looks like a screenshot/diagram/UI - AI photo detectors unreliable on non-photographic content",
                    "content_check": photo_check,
                },
            )

        per_model = [_run_one(name, idx, image) for idx, name in enumerate(ENSEMBLE_MODELS)]
        ok_results = [r for r in per_model if r.get("ok")]

        if not ok_results:
            return AnalysisOutput(
                confidence=0.0,
                verdict="error",
                evidence={"error": "all ensemble models failed", "classifiers": per_model},
            )

        ai_probs = [r["ai_probability"] for r in ok_results]
        ai_avg = sum(ai_probs) / len(ai_probs)
        ai_max = max(ai_probs)
        agreement = sum(1 for p in ai_probs if p > 0.5)

        evidence = {
            "ensemble_size": len(ok_results),
            "ai_probability_avg": round(ai_avg, 4),
            "ai_probability_max": round(ai_max, 4),
            "ai_models_voting_fake": agreement,
            "content_check": photo_check,
            "classifiers": per_model,
        }

        unanimous_fake = agreement == len(ok_results)
        unanimous_real = all(p < 0.4 for p in ai_probs)

        if ai_avg >= 0.85 and unanimous_fake:
            confidence = 0.85
            verdict = "fake"
        elif ai_avg >= 0.7 and unanimous_fake:
            confidence = 0.65
            verdict = "suspicious"
        elif unanimous_real and ai_avg < 0.2:
            confidence = 0.8
            verdict = "authentic"
        elif unanimous_real and ai_avg < 0.35:
            confidence = 0.6
            verdict = "authentic"
        else:
            confidence = 0.4
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
