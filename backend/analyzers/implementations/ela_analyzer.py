import io

import numpy as np
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

from analyzers.base import AnalysisOutput, BaseAnalyzer

ELA_QUALITY = 95
BLOCK_SIZE = 16
OUTLIER_SIGMA = 4.0
OUTLIER_RATIO_SUSPECT = 0.02
MIN_BLOCKS_FOR_OUTLIERS = 64


class ELAAnalyzer(BaseAnalyzer):
    name = "ela"
    version = "2.0.0"

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

        outlier_ratio = 0.0
        if len(block_means) >= MIN_BLOCKS_FOR_OUTLIERS and block_std > 0:
            threshold = block_mean + OUTLIER_SIGMA * block_std
            outlier_ratio = sum(1 for b in block_means if b > threshold) / len(block_means)

        heatmap_path = self._save_heatmap(diff, metadata)

        manipulation_suspected = (
            not is_lossless_source
            and len(block_means) >= MIN_BLOCKS_FOR_OUTLIERS
            and outlier_ratio >= OUTLIER_RATIO_SUSPECT
        )

        evidence = {
            "mean_error": round(mean_error, 3),
            "max_error": round(max_error, 3),
            "std_error": round(std_error, 3),
            "block_std": round(block_std, 3),
            "block_mean": round(block_mean, 3),
            "uniformity_ratio": round(uniformity_ratio, 4),
            "block_outlier_ratio": round(outlier_ratio, 4),
            "manipulation_suspected": manipulation_suspected,
            "source_format": source_format,
            "note": (
                "ELA localises recompression inconsistency (splicing). It does not separate "
                "AI-generated from camera imagery, so it does not vote on that axis."
            ),
        }
        if heatmap_path:
            evidence["heatmap_path"] = heatmap_path
            evidence["heatmap_url"] = default_storage.url(heatmap_path)

        if is_lossless_source:
            evidence["note"] = "lossless source (PNG/WebP/etc) - ELA heuristics unreliable"

        return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence=evidence)

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
            return default_storage.save(storage_path, ContentFile(buf.read()))
        except Exception:
            return None
