import io
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from content.validators import validate_file_size, validate_mime_type


@pytest.mark.django_db
class TestValidateMimeType:
    def test_valid_jpeg(self):
        img = Image.new("RGB", (10, 10))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        f = SimpleUploadedFile("test.jpg", buf.read(), content_type="image/jpeg")
        mime = validate_mime_type(f)
        assert mime == "image/jpeg"

    def test_valid_png(self):
        img = Image.new("RGB", (10, 10))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        f = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")
        mime = validate_mime_type(f)
        assert mime == "image/png"

    def test_invalid_type_rejected(self):
        f = SimpleUploadedFile("test.exe", b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200, content_type="application/x-msdownload")
        with pytest.raises(ValidationError, match="Unsupported file type"):
            validate_mime_type(f)

    def test_disguised_file_rejected(self):
        f = SimpleUploadedFile("fake.jpg", b"MZ\x90\x00" + b"\x00" * 100, content_type="image/jpeg")
        with pytest.raises(ValidationError):
            validate_mime_type(f)


class TestValidateFileSize:
    def test_within_limit(self):
        f = SimpleUploadedFile("test.jpg", b"\x00" * 100)
        f.size = 100
        validate_file_size(f)

    def test_exceeds_limit(self, settings):
        settings.MAX_UPLOAD_SIZE = 10
        f = SimpleUploadedFile("test.jpg", b"\x00" * 100)
        f.size = 100
        with pytest.raises(ValidationError, match="File too large"):
            validate_file_size(f)
