import hashlib
import io
import logging

import imagehash
import numpy as np
from PIL import ExifTags, Image

logger = logging.getLogger(__name__)


def compute_sha256(file):
    sha256 = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(65536), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


def _clean_str(s: str) -> str:
    return s.replace("\x00", "")


def _json_safe(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clean_str(value)
    if isinstance(value, bytes):
        try:
            return _clean_str(value.decode("utf-8", errors="replace"))
        except Exception:
            return value.hex()
    if isinstance(value, dict):
        return {_clean_str(str(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    return _clean_str(str(value))


def extract_metadata(file_path):
    try:
        img = Image.open(file_path)
    except Exception:
        return {}

    metadata = {
        "format": img.format,
        "mode": img.mode,
        "width": img.width,
        "height": img.height,
    }

    exif_data = img.getexif()
    if exif_data:
        exif = {}
        for tag_id, value in exif_data.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            exif[tag_name] = _json_safe(value)

        try:
            gps_ifd = exif_data.get_ifd(0x8825)
            if gps_ifd:
                exif["GPSInfo"] = {str(k): _json_safe(v) for k, v in gps_ifd.items()}
        except Exception:
            pass

        metadata["exif"] = exif

    return metadata


def generate_thumbnail(file_path, size=(300, 300)):
    try:
        img = Image.open(file_path)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return buffer
    except Exception:
        return None


def check_known_fake(sha256_hash):
    from .models import KnownFakeHash
    return KnownFakeHash.objects.filter(sha256_hash=sha256_hash).exists()


def _phash_to_signed(h: imagehash.ImageHash) -> int:
    v = int(str(h), 16)
    if v > 2**63 - 1:
        v -= 2**64
    return v


def compute_perceptual_hashes(file_path):
    """Return dict with phash, dhash, pdq_hash, pdq_quality, clip_embedding."""
    out = {
        "phash": None,
        "dhash": None,
        "pdq_hash": "",
        "pdq_quality": None,
        "clip_embedding": None,
    }
    try:
        img = Image.open(file_path).convert("RGB")
        out["phash"] = _phash_to_signed(imagehash.phash(img))
        out["dhash"] = _phash_to_signed(imagehash.dhash(img))
    except Exception as e:
        logger.warning("phash/dhash failed: %s", e)
        return out

    try:
        import pdqhash

        arr = np.array(img)
        bits, quality = pdqhash.compute(arr)
        out["pdq_hash"] = _bits_to_hex(bits)
        out["pdq_quality"] = int(quality)
    except Exception as e:
        logger.warning("pdq compute failed: %s", e)

    try:
        out["clip_embedding"] = compute_clip_embedding(img)
    except Exception as e:
        logger.warning("clip embed failed: %s", e)

    return out


def _bits_to_hex(bits) -> str:
    bit_str = "".join("1" if b else "0" for b in bits)
    pad = (-len(bit_str)) % 4
    bit_str += "0" * pad
    return f"{int(bit_str, 2):0{len(bit_str)//4}x}"


_CLIP_STATE = {"processor": None, "model": None, "device": "cpu"}


def _load_clip():
    if _CLIP_STATE["model"] is not None:
        return _CLIP_STATE
    from transformers import CLIPModel, CLIPProcessor

    name = "openai/clip-vit-base-patch32"
    _CLIP_STATE["processor"] = CLIPProcessor.from_pretrained(name)
    try:
        _CLIP_STATE["model"] = CLIPModel.from_pretrained(name, use_safetensors=True).eval()
    except Exception:
        _CLIP_STATE["model"] = CLIPModel.from_pretrained(name).eval()
    return _CLIP_STATE


def compute_clip_embedding(img: Image.Image):
    import torch

    state = _load_clip()
    inputs = state["processor"](images=img, return_tensors="pt")
    with torch.no_grad():
        feats = state["model"].get_image_features(**inputs)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
    return feats[0].cpu().numpy().tolist()


CACHE_TTL_DAYS = 14


def find_cached_result(sha256_hash, exclude_id):
    from datetime import timedelta

    from django.utils import timezone

    from .models import Submission
    cutoff = timezone.now() - timedelta(days=CACHE_TTL_DAYS)
    return (
        Submission.objects
        .filter(
            sha256_hash=sha256_hash,
            status=Submission.Status.COMPLETED,
            updated_at__gte=cutoff,
        )
        .exclude(id=exclude_id)
        .order_by("-created_at")
        .first()
    )


def clone_analysis_results(source_submission, target_submission):
    from analyzers.models import AnalysisResult, AnalyzerConfig
    active_analyzer_ids = set(
        AnalyzerConfig.objects.filter(is_active=True).values_list("id", flat=True)
    )
    for result in source_submission.analysis_results.all():
        if result.analyzer_id not in active_analyzer_ids:
            continue
        AnalysisResult.objects.create(
            submission=target_submission,
            analyzer=result.analyzer,
            confidence=result.confidence,
            verdict=result.verdict,
            evidence=result.evidence,
            execution_time=0.0,
        )


def find_similar_submissions(submission, threshold=10):
    from .models import Submission
    if submission.phash is None:
        return []
    results = Submission.objects.raw(
        """
        SELECT *, bit_count((phash # %s)::bit(64)) AS distance
        FROM submissions
        WHERE id != %s AND phash IS NOT NULL
        AND bit_count((phash # %s)::bit(64)) < %s
        ORDER BY bit_count((phash # %s)::bit(64))
        LIMIT 10
        """,
        [submission.phash, submission.id, submission.phash, threshold, submission.phash],
    )
    return [
        {"id": str(r.id), "distance": r.distance, "filename": r.original_filename}
        for r in results
    ]
