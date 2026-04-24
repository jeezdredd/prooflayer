import io
import hashlib
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from analyzers.tests.factories import AnalysisResultFactory
from content.models import KnownFakeHash, Submission
from content.services import (
    check_known_fake,
    clone_analysis_results,
    compute_sha256,
    extract_metadata,
    find_cached_result,
    generate_thumbnail,
)
from content.tests.factories import SubmissionFactory


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


@pytest.mark.django_db
class TestFindCachedResult:
    def test_returns_completed_match(self):
        sub = SubmissionFactory(sha256_hash="a" * 64, status=Submission.Status.COMPLETED)
        other = SubmissionFactory(sha256_hash="a" * 64, status=Submission.Status.PENDING)
        result = find_cached_result("a" * 64, other.id)
        assert result == sub

    def test_excludes_self(self):
        sub = SubmissionFactory(sha256_hash="a" * 64, status=Submission.Status.COMPLETED)
        result = find_cached_result("a" * 64, sub.id)
        assert result is None

    def test_ignores_non_completed(self):
        SubmissionFactory(sha256_hash="a" * 64, status=Submission.Status.PROCESSING)
        other = SubmissionFactory(sha256_hash="a" * 64)
        result = find_cached_result("a" * 64, other.id)
        assert result is None


@pytest.mark.django_db
class TestCloneAnalysisResults:
    def test_clones_results(self):
        source = SubmissionFactory(status=Submission.Status.COMPLETED)
        target = SubmissionFactory()
        AnalysisResultFactory(submission=source)
        AnalysisResultFactory(submission=source)
        clone_analysis_results(source, target)
        assert target.analysis_results.count() == 2

    def test_cloned_execution_time_zero(self):
        source = SubmissionFactory(status=Submission.Status.COMPLETED)
        target = SubmissionFactory()
        AnalysisResultFactory(submission=source, execution_time=5.5)
        clone_analysis_results(source, target)
        cloned = target.analysis_results.first()
        assert cloned.execution_time == 0.0
