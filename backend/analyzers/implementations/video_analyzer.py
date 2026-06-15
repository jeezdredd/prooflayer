import logging
import os
import tempfile

import torch
from PIL import Image

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

FRAME_INTERVAL = 30
MAX_FRAMES = 8


def _analyze_frame(frame_path: str) -> dict:
    from analyzers.implementations.community_forensics import _load as _load_cf
    model, processor = _load_cf()
    img = Image.open(frame_path).convert("RGB").resize((384, 384))
    inputs = processor(images=img, return_tensors="pt", do_resize=False)
    with torch.no_grad():
        logits = model(**inputs).logits.squeeze()
        if logits.dim() == 0:
            ai_prob = float(torch.sigmoid(logits).item())
        else:
            ai_prob = float(torch.softmax(logits, dim=-1)[-1].item())
    if ai_prob >= 0.65:
        verdict, confidence = "suspicious", 0.65
    elif ai_prob >= 0.85:
        verdict, confidence = "fake", 0.85
    elif ai_prob < 0.35:
        verdict, confidence = "authentic", 0.70
    else:
        verdict, confidence = "inconclusive", 0.40
    return {"ai_probability": round(ai_prob, 4), "verdict": verdict, "confidence": confidence}


class VideoFrameAnalyzer(BaseAnalyzer):
    name = "video_frame"
    version = "1.1.0"

    def supported_mime_types(self) -> list[str]:
        return ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            import cv2
        except ImportError:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "opencv not installed"})

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "could not open video"})

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frame_results = []
        frame_idx = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            while cap.isOpened() and len(frame_results) < MAX_FRAMES:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % FRAME_INTERVAL == 0:
                    frame_path = os.path.join(tmpdir, f"frame_{frame_idx}.jpg")
                    cv2.imwrite(frame_path, frame)
                    try:
                        result = _analyze_frame(frame_path)
                        frame_results.append({
                            "frame": frame_idx,
                            "timestamp": round(frame_idx / fps, 1),
                            **result,
                        })
                    except Exception as exc:
                        logger.warning("Frame %s analysis failed: %s", frame_idx, exc)
                frame_idx += 1

        cap.release()

        if not frame_results:
            return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence={"frames_analyzed": 0})

        suspicious_frames = [r for r in frame_results if r["verdict"] in ("fake", "suspicious")]
        ai_frame_ratio = len(suspicious_frames) / len(frame_results)
        avg_confidence = sum(r["confidence"] for r in frame_results) / len(frame_results)

        if ai_frame_ratio >= 0.6:
            verdict = "fake"
            confidence = min(0.95, avg_confidence + 0.1)
        elif ai_frame_ratio >= 0.3:
            verdict = "suspicious"
            confidence = avg_confidence
        elif ai_frame_ratio >= 0.1:
            verdict = "inconclusive"
            confidence = 0.45
        else:
            verdict = "inconclusive"
            confidence = 0.30

        return AnalysisOutput(
            confidence=confidence,
            verdict=verdict,
            evidence={
                "frames_analyzed": len(frame_results),
                "ai_frame_ratio": round(ai_frame_ratio, 3),
                "frame_results": frame_results,
            },
        )
