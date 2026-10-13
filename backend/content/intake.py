import os
import zipfile
from dataclasses import dataclass, field

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from billing.models import get_or_create_subscription, uploads_this_month
from content.models import Submission
from content.tasks import process_submission
from content.validators import validate_file_size, validate_mime_type

BATCH_MAX_FILES = 100
ZIP_MAX_MEMBERS = 500
ZIP_MAX_MEMBER_BYTES = 50 * 1024 * 1024
ZIP_MAX_TOTAL_BYTES = 512 * 1024 * 1024
ZIP_MAX_RATIO = 200
ZIP_MIME = {"application/zip", "application/x-zip-compressed"}
IGNORED_NAME_PREFIXES = ("__MACOSX/", "._", ".DS_Store")


class QuotaExceeded(Exception):
    def __init__(self, limit: int, used: int, requested: int, tier: str):
        super().__init__(f"{requested} uploads would exceed {limit}/month (used {used})")
        self.limit, self.used, self.requested, self.tier = limit, used, requested, tier

    def as_response_data(self) -> dict:
        return {
            "detail": f"Monthly upload limit reached ({self.limit} uploads). Upgrade for more.",
            "code": "upload_limit_reached",
            "limit": self.limit,
            "used": self.used,
            "requested": self.requested,
            "tier": self.tier,
        }


def check_quota(quota_user, requested: int = 1) -> None:
    if quota_user.is_staff or quota_user.is_superuser:
        return
    sub = get_or_create_subscription(quota_user)
    used = uploads_this_month(quota_user)
    if used + requested > sub.uploads_per_month:
        raise QuotaExceeded(sub.uploads_per_month, used, requested, sub.tier)


def create_submission(user, upload, mime_type: str, **extra) -> Submission:
    submission = Submission.objects.create(
        user=user,
        file=upload,
        original_filename=os.path.basename(upload.name)[:255],
        mime_type=mime_type,
        file_size=upload.size,
        **extra,
    )
    process_submission.delay(str(submission.id))
    return submission


@dataclass
class Intake:
    accepted: list = field(default_factory=list)
    skipped: list = field(default_factory=list)

    def skip(self, name: str, reason: str):
        self.skipped.append({"name": name[:255], "reason": reason})


def _is_zip(upload) -> bool:
    if upload.name.lower().endswith(".zip"):
        return True
    return getattr(upload, "content_type", "") in ZIP_MIME


def _safe_member_name(name: str) -> str | None:
    if name.endswith("/") or name.startswith(IGNORED_NAME_PREFIXES) or "/__MACOSX/" in name:
        return None
    base = os.path.basename(name)
    if not base or base.startswith(".") or base.startswith("._"):
        return None
    return base


def expand_zip(upload, intake: Intake) -> None:
    """Unpack a ZIP into in-memory uploads with zip-bomb and path-traversal guards.

    Only the basename of each member is kept, so `../../etc/passwd` becomes `passwd` and is then
    dropped by the MIME check like any other unsupported file.
    """
    try:
        archive = zipfile.ZipFile(upload)
    except zipfile.BadZipFile:
        intake.skip(upload.name, "not a valid ZIP archive")
        return
    with archive:
        members = archive.infolist()
        if len(members) > ZIP_MAX_MEMBERS:
            raise ValidationError({"files": [f"ZIP has {len(members)} entries; limit is {ZIP_MAX_MEMBERS}."]})
        declared_total = sum(m.file_size for m in members)
        if declared_total > ZIP_MAX_TOTAL_BYTES:
            raise ValidationError({"files": ["ZIP expands beyond the size limit."]})
        for member in members:
            name = _safe_member_name(member.filename)
            if name is None:
                continue
            if member.file_size > ZIP_MAX_MEMBER_BYTES:
                intake.skip(name, "file inside ZIP is larger than 50 MB")
                continue
            if member.compress_size and member.file_size / member.compress_size > ZIP_MAX_RATIO:
                intake.skip(name, "suspicious compression ratio")
                continue
            with archive.open(member) as fh:
                data = fh.read(ZIP_MAX_MEMBER_BYTES + 1)
            if len(data) > ZIP_MAX_MEMBER_BYTES:
                intake.skip(name, "file inside ZIP is larger than 50 MB")
                continue
            add_upload(SimpleUploadedFile(name, data), intake)


def add_upload(upload, intake: Intake) -> None:
    try:
        validate_file_size(upload)
        mime_type = validate_mime_type(upload)
    except ValidationError as exc:
        detail = exc.detail[0] if isinstance(exc.detail, list) else exc.detail
        intake.skip(upload.name, str(detail)[:200])
        return
    intake.accepted.append((upload, mime_type))


def collect_uploads(files) -> Intake:
    intake = Intake()
    for upload in files:
        if _is_zip(upload):
            expand_zip(upload, intake)
        else:
            add_upload(upload, intake)
    if len(intake.accepted) > BATCH_MAX_FILES:
        raise ValidationError({"files": [f"{len(intake.accepted)} files; a batch holds at most {BATCH_MAX_FILES}."]})
    return intake

