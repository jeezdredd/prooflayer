import logging
import os
import tempfile

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

FRAME_INTERVAL = 30
MAX_FRAMES = 8


class VideoFrameAnalyzer(BaseAnalyzer):
    name = "video_frame"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            import cv2
        except ImportError:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "opencv not installed"})

        from analyzers.implementations.clip_detector import AIImageDetector

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "could not open video"})

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        detector = AIImageDetector()
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
                        output = detector.analyze(frame_path, {})
                        frame_results.append({
                            "frame": frame_idx,
                            "timestamp": round(frame_idx / fps, 1),
                            "confidence": output.confidence,
                            "verdict": output.verdict,
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
        else:
            verdict = "authentic"
            confidence = max(0.4, 1.0 - avg_confidence)

        return AnalysisOutput(
            confidence=confidence,
            verdict=verdict,
            evidence={
                "frames_analyzed": len(frame_results),
                "ai_frame_ratio": round(ai_frame_ratio, 3),
                "frame_results": frame_results,
            },
        )
