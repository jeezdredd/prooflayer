import hashlib
import io

import imagehash
from PIL import Image, ExifTags


def compute_sha256(file):
    sha256 = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(65536), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


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
            try:
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                str(value)
                exif[tag_name] = value
            except Exception:
                exif[tag_name] = str(value)
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


def compute_perceptual_hashes(file_path):
    try:
        img = Image.open(file_path)
        ph = int(str(imagehash.phash(img)), 16)
        dh = int(str(imagehash.dhash(img)), 16)
        if ph > 2**63 - 1:
            ph -= 2**64
        if dh > 2**63 - 1:
            dh -= 2**64
        return ph, dh
    except Exception:
        return None, None


def find_cached_result(sha256_hash, exclude_id):
    from .models import Submission
    return Submission.objects.filter(
        sha256_hash=sha256_hash,
        status=Submission.Status.COMPLETED,
    ).exclude(id=exclude_id).order_by("-created_at").first()


def clone_analysis_results(source_submission, target_submission):
    from analyzers.models import AnalysisResult
    for result in source_submission.analysis_results.all():
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
