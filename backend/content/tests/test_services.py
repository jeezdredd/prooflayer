import io
import hashlib
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from content.services import compute_sha256, extract_metadata, generate_thumbnail, check_known_fake
from content.models import KnownFakeHash


class TestComputeSha256:
    def test_correct_hash(self):
        data = b"test data for hashing"
        f = SimpleUploadedFile("test.bin", data)
        result = compute_sha256(f)
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected

    def test_file_rewound(self):
        f = SimpleUploadedFile("test.bin", b"data")
        compute_sha256(f)
        assert f.tell() == 0


class TestExtractMetadata:
    def test_jpeg_metadata(self, tmp_path):
        img = Image.new("RGB", (200, 150))
        path = tmp_path / "test.jpg"
        img.save(str(path), format="JPEG")
        meta = extract_metadata(str(path))
        assert meta["format"] == "JPEG"
        assert meta["width"] == 200
        assert meta["height"] == 150

    def test_invalid_file(self, tmp_path):
        path = tmp_path / "bad.txt"
        path.write_text("not an image")
        meta = extract_metadata(str(path))
        assert meta == {}


class TestGenerateThumbnail:
    def test_thumbnail_created(self, tmp_path):
        img = Image.new("RGB", (1000, 800))
        path = tmp_path / "big.jpg"
        img.save(str(path), format="JPEG")
        result = generate_thumbnail(str(path))
        assert result is not None
        thumb = Image.open(result)
        assert thumb.size[0] <= 300
        assert thumb.size[1] <= 300

    def test_invalid_file_returns_none(self, tmp_path):
        path = tmp_path / "bad.txt"
        path.write_text("not an image")
        assert generate_thumbnail(str(path)) is None


@pytest.mark.django_db
class TestCheckKnownFake:
    def test_known_fake_found(self):
        KnownFakeHash.objects.create(sha256_hash="a" * 64, source="test")
        assert check_known_fake("a" * 64) is True

    def test_unknown_hash(self):
        assert check_known_fake("b" * 64) is False
