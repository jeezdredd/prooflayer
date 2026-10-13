from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from plagiarism.models import SentenceVector, TextFingerprint

from .models import Submission

CHUNK = 500


def expired_personal_files(now=None):
    cutoff = (now or timezone.now()) - timedelta(days=settings.PERSONAL_FILE_RETENTION_DAYS)
    return (
        Submission.objects.filter(classroom__isnull=True, created_at__lt=cutoff)
        .exclude(file="")
        .order_by("created_at")
    )


def purge_file(submission, now=None) -> None:
    stamp = (now or timezone.now()).isoformat()
    if submission.file:
        submission.file.delete(save=False)
    if submission.thumbnail:
        submission.thumbnail.delete(save=False)
    submission.file = ""
    submission.thumbnail = ""
    submission.metadata = {**(submission.metadata or {}), "file_purged_at": stamp}
    submission.save(update_fields=["file", "thumbnail", "metadata", "updated_at"])
    TextFingerprint.objects.filter(submission=submission).delete()
    SentenceVector.objects.filter(submission=submission).delete()


def purge_expired_files(now=None) -> int:
    purged = 0
    for submission in expired_personal_files(now).iterator(chunk_size=CHUNK):
        purge_file(submission, now)
        purged += 1
    return purged
