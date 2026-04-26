import mimetypes

import magic
from django.conf import settings
from rest_framework.exceptions import ValidationError

MIME_ALIASES = {
    "audio/mp3": "audio/mpeg",
    "audio/x-mpeg": "audio/mpeg",
    "audio/x-mp3": "audio/mpeg",
    "audio/mpg": "audio/mpeg",
    "video/x-mp4": "video/mp4",
    "image/jpg": "image/jpeg",
}


def validate_mime_type(file):
    mime = magic.from_buffer(file.read(65536), mime=True)
    file.seek(0)

    if mime == "application/octet-stream" and hasattr(file, "name") and file.name:
        guessed, _ = mimetypes.guess_type(file.name)
        if guessed and guessed in settings.ALLOWED_MIME_TYPES:
            mime = guessed

    mime = MIME_ALIASES.get(mime, mime)

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
