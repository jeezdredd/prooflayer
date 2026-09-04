import gc
import logging

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from analyzers._device import get_device, inputs_to_device, to_device
from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

MODEL_NAME = "buildborderless/CommunityForensics-DeepfakeDet-ViT"
INPUT_SIZE = 384

CALIBRATION_KNOTS = (
    (0.0, 0.0),
    (0.005, 0.20),
    (0.10, 0.55),
    (0.50, 0.75),
    (1.0, 1.0),
)


def calibrate(raw: float) -> float:
    """Monotone piecewise-linear map from the model's sigmoid output to a probability
    whose bands mean the same thing on 2026 generators as they did on 2022 ones.

    Fitted 2026-09-04 on 210 real photos (flickr + LAION via OpenFake) and 296 AI images
    across 21 generators. The model ranks modern output well (AUC 0.977) but its raw
    scores sit far lower than on diffusiondb (median 0.32 vs 0.99), so the fixed bands
    read most of it as authentic. Real photos never exceed 0.147 raw (p99 = 0.0045), so
    the map can lift the low range without creating false positives. Validated by
    fitting on half the generators and testing on the other half.
    """
    raw = min(max(float(raw), 0.0), 1.0)
    for (x0, y0), (x1, y1) in zip(CALIBRATION_KNOTS, CALIBRATION_KNOTS[1:]):
        if raw <= x1:
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (raw - x0) / (x1 - x0)
    return 1.0

_state = {"model": None, "processor": None}


def _load():
    if _state["model"] is None:
        model = AutoModelForImageClassification.from_pretrained(MODEL_NAME, use_safetensors=True).eval()
        _state["model"] = to_device(model)
        try:
            _state["processor"] = AutoImageProcessor.from_pretrained(MODEL_NAME)
        except Exception:
            from transformers import ViTImageProcessor
            _state["processor"] = ViTImageProcessor(size={"height": INPUT_SIZE, "width": INPUT_SIZE}, do_normalize=True, image_mean=[0.5, 0.5, 0.5], image_std=[0.5, 0.5, 0.5])
        logger.info("community_forensics loaded %s on %s", MODEL_NAME, get_device())
    return _state["model"], _state["processor"]


def _center_crop(image: Image.Image) -> Image.Image | None:
    w, h = image.size
    if w < INPUT_SIZE or h < INPUT_SIZE:
        return None
    left = (w - INPUT_SIZE) // 2
    top = (h - INPUT_SIZE) // 2
    return image.crop((left, top, left + INPUT_SIZE, top + INPUT_SIZE))


def _fit_resize(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (INPUT_SIZE, INPUT_SIZE), (128, 128, 128))
    scaled = image.copy()
    scaled.thumbnail((INPUT_SIZE, INPUT_SIZE), Image.Resampling.BICUBIC)
    canvas.paste(scaled, ((INPUT_SIZE - scaled.width) // 2, (INPUT_SIZE - scaled.height) // 2))
    return canvas


def _views(image: Image.Image) -> list[tuple[str, Image.Image]]:
    views = [("global", _fit_resize(image))]
    crop = _center_crop(image)
    if crop is not None:
        views.append(("native_crop", crop))
    return views


def _score(model, processor, view: Image.Image) -> float:
    inputs = inputs_to_device(processor(images=view, return_tensors="pt", do_resize=False, do_center_crop=False))
    with torch.no_grad():
        logits = model(**inputs).logits.squeeze().cpu()
        if logits.dim() == 0:
            return float(torch.sigmoid(logits).item())
        probs = torch.softmax(logits, dim=-1)
        return float(probs[-1].item())


class CommunityForensicsDetector(BaseAnalyzer):
    name = "community_forensics"
    version = "1.5.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            image = Image.open(file_path).convert("RGB")
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot open image: {exc}"})

        try:
            model, processor = _load()
            per_view = {name: _score(model, processor, view) for name, view in _views(image)}
        except Exception as exc:
            logger.warning("community_forensics inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        raw_prob = sum(per_view.values()) / len(per_view)
        ai_prob = calibrate(raw_prob)

        evidence = {
            "model": "community-forensics-vit-s16-384",
            "ai_probability": round(ai_prob, 4),
            "raw_probability": round(raw_prob, 4),
            "calibration": "piecewise-linear 2026-09-04 (real p99 -> 0.20, AI p25 -> 0.55, AI median -> 0.75)",
            "per_view": {k: round(v, 4) for k, v in per_view.items()},
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
