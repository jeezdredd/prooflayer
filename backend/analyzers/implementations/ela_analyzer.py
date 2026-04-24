import io

import numpy as np
from PIL import Image

from analyzers.base import AnalysisOutput, BaseAnalyzer

ELA_QUALITY = 95
BLOCK_SIZE = 16


class ELAAnalyzer(BaseAnalyzer):
    name = "ela"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        original = Image.open(file_path).convert("RGB")

        buf = io.BytesIO()
        original.save(buf, format="JPEG", quality=ELA_QUALITY)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        orig_arr = np.array(original, dtype=np.float32)
        resaved_arr = np.array(resaved, dtype=np.float32)
        diff = np.abs(orig_arr - resaved_arr)

        mean_error = float(np.mean(diff))
        max_error = float(np.max(diff))
        std_error = float(np.std(diff))

        h, w = diff.shape[:2]
        block_means = []
        for y in range(0, h - BLOCK_SIZE + 1, BLOCK_SIZE):
            for x in range(0, w - BLOCK_SIZE + 1, BLOCK_SIZE):
                block = diff[y : y + BLOCK_SIZE, x : x + BLOCK_SIZE]
                block_means.append(float(np.mean(block)))

        if block_means:
            block_std = float(np.std(block_means))
            block_mean = float(np.mean(block_means))
            uniformity_ratio = block_std / block_mean if block_mean > 0 else 0.0
        else:
            block_std = 0.0
            block_mean = mean_error
            uniformity_ratio = 0.0

        evidence = {
            "mean_error": round(mean_error, 3),
            "max_error": round(max_error, 3),
            "std_error": round(std_error, 3),
            "block_std": round(block_std, 3),
            "block_mean": round(block_mean, 3),
            "uniformity_ratio": round(uniformity_ratio, 4),
        }

        if uniformity_ratio < 0.3 and mean_error < 5.0:
            confidence = 0.85
            verdict = "fake"
        elif uniformity_ratio < 0.5 and mean_error < 8.0:
            confidence = 0.65
            verdict = "suspicious"
        elif uniformity_ratio > 1.0 or mean_error > 15.0:
            confidence = 0.75
            verdict = "authentic"
        else:
            confidence = 0.5
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
