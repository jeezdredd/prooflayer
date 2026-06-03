import io

import numpy as np
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
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
        original = Image.open(file_path)
        source_format = (original.format or "").upper()
        original = original.convert("RGB")
        is_lossless_source = source_format in ("PNG", "WEBP", "BMP", "TIFF", "GIF")

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

        heatmap_url = self._save_heatmap(diff, metadata)

        evidence = {
            "mean_error": round(mean_error, 3),
            "max_error": round(max_error, 3),
            "std_error": round(std_error, 3),
            "block_std": round(block_std, 3),
            "block_mean": round(block_mean, 3),
            "uniformity_ratio": round(uniformity_ratio, 4),
            "source_format": source_format,
        }
        if heatmap_url:
            evidence["heatmap_url"] = heatmap_url

        if is_lossless_source:
            evidence["note"] = "lossless source (PNG/WebP/etc) - ELA heuristics unreliable"
            return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence=evidence)

        if uniformity_ratio < 0.3 and mean_error < 5.0:
            confidence = 0.85
            verdict = "fake"
        elif uniformity_ratio < 0.5 and mean_error < 8.0:
            confidence = 0.6
            verdict = "suspicious"
        elif uniformity_ratio > 1.0 or mean_error > 15.0:
            confidence = 0.75
            verdict = "authentic"
        else:
            confidence = 0.5
            verdict = "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)

    def _save_heatmap(self, diff: np.ndarray, metadata: dict) -> str | None:
        submission_id = metadata.get("submission_id")
        if not submission_id:
            return None
        try:
            gray = np.mean(diff, axis=2)
            max_val = gray.max()
            normalized = (gray / max_val * 255).astype(np.uint8) if max_val > 0 else gray.astype(np.uint8)
            red = np.zeros((*normalized.shape, 3), dtype=np.uint8)
            red[:, :, 0] = normalized
            red[:, :, 1] = (normalized * 0.3).astype(np.uint8)
            heatmap_img = Image.fromarray(red, "RGB")
            buf = io.BytesIO()
            heatmap_img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            storage_path = f"ela/{submission_id}.jpg"
            if default_storage.exists(storage_path):
                default_storage.delete(storage_path)
            saved_path = default_storage.save(storage_path, ContentFile(buf.read()))
            return default_storage.url(saved_path)
        except Exception:
            return None
