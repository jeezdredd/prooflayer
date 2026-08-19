import logging
import os
import tempfile

import torch
from PIL import Image

from analyzers._device import inputs_to_device
from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

MAX_FRAMES = 8
MIN_FRAME_STRIDE = 5


def _analyze_frame(frame_path: str) -> dict:
    from analyzers.implementations.community_forensics import _load as _load_cf
    model, processor = _load_cf()
    img = Image.open(frame_path).convert("RGB")
    inputs = inputs_to_device(processor(images=img, return_tensors="pt"))
    with torch.no_grad():
        logits = model(**inputs).logits.squeeze().cpu()
        if logits.dim() == 0:
            ai_prob = float(torch.sigmoid(logits).item())
        else:
            ai_prob = float(torch.softmax(logits, dim=-1)[-1].item())
    if ai_prob >= 0.85:
        verdict, confidence = "fake", 0.85
    elif ai_prob >= 0.65:
        verdict, confidence = "suspicious", 0.65
    elif ai_prob < 0.35:
        verdict, confidence = "authentic", 0.70
    else:
        verdict, confidence = "inconclusive", 0.40
    return {"ai_probability": round(ai_prob, 4), "verdict": verdict, "confidence": confidence}


def _frame_positions(total_frames: int) -> list[int]:
    if total_frames <= 0:
        return []
    if total_frames <= MAX_FRAMES:
        return list(range(total_frames))
    stride = max(total_frames // MAX_FRAMES, MIN_FRAME_STRIDE)
    return [min(i * stride, total_frames - 1) for i in range(MAX_FRAMES)]


class VideoFrameAnalyzer(BaseAnalyzer):
    name = "video_frame"
    version = "1.2.0"

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
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        positions = _frame_positions(total_frames)
        frame_results = []
        frame_errors = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            if positions:
                for pos in positions:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    frame_errors += self._score_frame(cv2, tmpdir, frame, pos, fps, frame_results)
            else:
                idx = 0
                while cap.isOpened() and len(frame_results) < MAX_FRAMES:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if idx % 30 == 0:
                        frame_errors += self._score_frame(cv2, tmpdir, frame, idx, fps, frame_results)
                    idx += 1

        cap.release()

        if not frame_results:
            return AnalysisOutput(
                confidence=0.0 if frame_errors else 0.5,
                verdict="error" if frame_errors else "inconclusive",
                evidence={"frames_analyzed": 0, "frame_errors": frame_errors},
            )

        probs = [r["ai_probability"] for r in frame_results]
        probs_sorted = sorted(probs)
        mid = len(probs_sorted) // 2
        median_prob = (
            probs_sorted[mid]
            if len(probs_sorted) % 2
            else (probs_sorted[mid - 1] + probs_sorted[mid]) / 2
        )
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
            verdict = "authentic" if median_prob < 0.35 else "inconclusive"
            confidence = 0.6 if verdict == "authentic" else 0.30

        return AnalysisOutput(
            confidence=confidence,
            verdict=verdict,
            evidence={
                "frames_analyzed": len(frame_results),
                "frame_errors": frame_errors,
                "ai_probability": round(median_prob, 4),
                "ai_frame_ratio": round(ai_frame_ratio, 3),
                "frame_results": frame_results,
            },
        )

    def _score_frame(self, cv2, tmpdir, frame, idx, fps, frame_results) -> int:
        frame_path = os.path.join(tmpdir, f"frame_{idx}.jpg")
        cv2.imwrite(frame_path, frame)
        try:
            result = _analyze_frame(frame_path)
        except Exception as exc:
            logger.warning("Frame %s analysis failed: %s", idx, exc)
            return 1
        frame_results.append({"frame": idx, "timestamp": round(idx / fps, 1), **result})
        return 0
