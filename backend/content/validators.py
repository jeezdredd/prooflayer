import magic
from django.conf import settings
from rest_framework.exceptions import ValidationError


def validate_mime_type(file):
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
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
