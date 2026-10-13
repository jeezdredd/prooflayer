import mimetypes
import zipfile

import magic
from django.conf import settings
from rest_framework.exceptions import ValidationError

from common.documents import DOCX_MIME

DOCX_MARKER = "word/document.xml"

MIME_ALIASES = {
    "audio/mp3": "audio/mpeg",
    "audio/x-mpeg": "audio/mpeg",
    "audio/x-mp3": "audio/mpeg",
    "audio/mpg": "audio/mpeg",
    "video/x-mp4": "video/mp4",
    "image/jpg": "image/jpeg",
}


def _is_docx(file) -> bool:
    """libmagic often reports DOCX as plain ZIP; accept it only if it really is a Word package."""
    if not (getattr(file, "name", "") or "").lower().endswith(".docx"):
        return False
    try:
        with zipfile.ZipFile(file) as archive:
            return DOCX_MARKER in archive.namelist()
    except zipfile.BadZipFile:
        return False
    finally:
        file.seek(0)


def validate_mime_type(file):
    mime = magic.from_buffer(file.read(65536), mime=True)
    file.seek(0)

    if mime == "application/octet-stream" and hasattr(file, "name") and file.name:
        guessed, _ = mimetypes.guess_type(file.name)
        if guessed and guessed in settings.ALLOWED_MIME_TYPES:
            mime = guessed

    mime = MIME_ALIASES.get(mime, mime)
    if mime == "application/zip" and _is_docx(file):
        mime = DOCX_MIME

    if mime not in settings.ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"Unsupported file type: {mime}. "
            f"Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
        )
    return mime


def validate_file_size(file):
    if file.size > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise ValidationError(f"File too large. Maximum size is {max_mb}MB.")
