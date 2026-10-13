import hashlib
import hmac

from django.conf import settings
from django.core.files.base import ContentFile

from .models import TrainingSample

MEDIA_PREFIX = {"image/": "image", "video/": "video", "audio/": "audio"}


def source_ref(user_id) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"training:{user_id}".encode(), hashlib.sha256).hexdigest()


def media_type_of(mime: str) -> str | None:
    for prefix, kind in MEDIA_PREFIX.items():
        if (mime or "").startswith(prefix):
            return kind
    return None


def snapshot(submission) -> TrainingSample | None:
    if submission.classroom_id is not None or not submission.file:
        return None
    if submission.verified_label not in (TrainingSample.Label.REAL, TrainingSample.Label.FAKE):
        return None
    if not getattr(submission.user, "allow_training", False):
        return None
    kind = media_type_of(submission.mime_type)
    if kind is None:
        return None
    existing = TrainingSample.objects.filter(source_submission=submission.id).first()
    if existing:
        if existing.label != submission.verified_label:
            existing.label = submission.verified_label
            existing.save(update_fields=["label"])
        return existing
    with submission.file.open("rb") as handle:
        payload = handle.read()
    extension = (submission.original_filename.rsplit(".", 1)[-1] if "." in submission.original_filename else "bin")[:8]
    sample = TrainingSample(
        media_type=kind,
        mime_type=submission.mime_type,
        label=submission.verified_label,
        sha256=submission.sha256_hash or hashlib.sha256(payload).hexdigest(),
        source_ref=source_ref(submission.user_id),
        source_submission=submission.id,
    )
    sample.file.save(f"{sample.id}.{extension}", ContentFile(payload), save=False)
    sample.save()
    return sample


def forget(user_id) -> int:
    removed = 0
    for sample in TrainingSample.objects.filter(source_ref=source_ref(user_id)).iterator(chunk_size=200):
        if sample.file:
            sample.file.delete(save=False)
        sample.delete()
        removed += 1
    return removed
