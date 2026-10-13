import csv
import io
import zipfile
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from content.batch_views import csv_safe
from content.intake import ZIP_MAX_MEMBERS, Intake, expand_zip
from content.models import Batch, Submission
from users.tests.factories import UserFactory


def _jpeg_bytes(color=(200, 10, 10)):
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, format="JPEG")
    return buf.getvalue()


def _jpeg(name="a.jpg", color=(200, 10, 10)):
    return SimpleUploadedFile(name, _jpeg_bytes(color), content_type="image/jpeg")


def _zip(entries, name="batch.zip"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for member_name, data in entries:
            zf.writestr(member_name, data)
    return SimpleUploadedFile(name, buf.getvalue(), content_type="application/zip")


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
@patch("content.intake.process_submission.delay")
class TestBatchCreate:
    def test_multiple_files_make_one_batch(self, _delay):
        user = UserFactory(is_verified=True)
        response = _client(user).post(
            reverse("batch-list"), {"files": [_jpeg("a.jpg"), _jpeg("b.jpg", (0, 0, 200))], "name": "set 1"}, format="multipart"
        )
        assert response.status_code == 201
        batch = Batch.objects.get(id=response.data["id"])
        assert batch.submissions.count() == 2
        assert response.data["summary"]["total"] == 2
        assert _delay.call_count == 2

    def test_zip_is_expanded_and_junk_skipped(self, _delay):
        user = UserFactory(is_verified=True)
        archive = _zip([
            ("photos/one.jpg", _jpeg_bytes()),
            ("__MACOSX/photos/._one.jpg", b"junk"),
            ("notes.exe", b"MZ\x90\x00binary"),
            ("two.jpg", _jpeg_bytes((1, 2, 3))),
        ])
        response = _client(user).post(reverse("batch-list"), {"files": [archive]}, format="multipart")
        assert response.status_code == 201
        names = sorted(Submission.objects.filter(batch_id=response.data["id"]).values_list("original_filename", flat=True))
        assert names == ["one.jpg", "two.jpg"]
        assert [s["name"] for s in response.data["skipped"]] == ["notes.exe"]

    def test_path_traversal_keeps_only_basename(self, _delay):
        user = UserFactory(is_verified=True)
        archive = _zip([("../../etc/evil.jpg", _jpeg_bytes())])
        response = _client(user).post(reverse("batch-list"), {"files": [archive]}, format="multipart")
        assert response.status_code == 201
        sub = Submission.objects.get(batch_id=response.data["id"])
        assert sub.original_filename == "evil.jpg"
        assert ".." not in sub.file.name

    def test_quota_checked_for_whole_batch(self, _delay):
        user = UserFactory(is_verified=True)
        with patch("content.intake.uploads_this_month", return_value=49):
            response = _client(user).post(
                reverse("batch-list"), {"files": [_jpeg("a.jpg"), _jpeg("b.jpg", (0, 0, 9))]}, format="multipart"
            )
        assert response.status_code == 402
        assert response.data["requested"] == 2
        assert Submission.objects.filter(user=user).count() == 0
        _delay.assert_not_called()

    def test_nothing_supported_is_400(self, _delay):
        user = UserFactory(is_verified=True)
        bad = SimpleUploadedFile("x.exe", b"MZ\x90\x00", content_type="application/octet-stream")
        response = _client(user).post(reverse("batch-list"), {"files": [bad]}, format="multipart")
        assert response.status_code == 400
        assert response.data["skipped"][0]["name"] == "x.exe"

    def test_unverified_user_rejected(self, _delay):
        user = UserFactory(is_verified=False)
        response = _client(user).post(reverse("batch-list"), {"files": [_jpeg()]}, format="multipart")
        assert response.status_code == 403


class TestZipGuards:
    def test_too_many_members_rejected(self):
        archive = _zip([(f"f{i}.txt", b"x") for i in range(ZIP_MAX_MEMBERS + 1)])
        with pytest.raises(Exception, match="entries"):
            expand_zip(archive, Intake())

    def test_compression_bomb_member_skipped(self):
        archive = _zip([("bomb.txt", b"\x00" * (5 * 1024 * 1024))])
        intake = Intake()
        expand_zip(archive, intake)
        assert intake.accepted == []
        assert intake.skipped[0]["reason"] == "suspicious compression ratio"

    def test_corrupt_zip_is_skipped_not_crashing(self):
        intake = Intake()
        expand_zip(SimpleUploadedFile("broken.zip", b"PK\x03\x04garbage"), intake)
        assert intake.skipped[0]["name"] == "broken.zip"


@pytest.mark.django_db
class TestBatchReadAndExport:
    def _batch(self, user, filename="=HYPERLINK(1).jpg"):
        batch = Batch.objects.create(user=user, name="b")
        Submission.objects.create(
            user=user, batch=batch, file=_jpeg(), original_filename=filename, mime_type="image/jpeg",
            status=Submission.Status.COMPLETED, final_verdict="fake", final_score=0.9, tribunal_version="1.2",
        )
        return batch

    def test_owner_reads_summary(self):
        user = UserFactory(is_verified=True)
        batch = self._batch(user, "a.jpg")
        response = _client(user).get(reverse("batch-detail", kwargs={"id": batch.id}))
        assert response.status_code == 200
        assert response.data["summary"] == {"total": 1, "done": 1, "by_status": {"completed": 1}, "by_verdict": {"fake": 1}}

    def test_other_user_gets_404(self):
        batch = self._batch(UserFactory(is_verified=True), "a.jpg")
        response = _client(UserFactory(is_verified=True)).get(reverse("batch-detail", kwargs={"id": batch.id}))
        assert response.status_code == 404

    def test_csv_export_neutralises_formulas(self):
        user = UserFactory(is_verified=True)
        batch = self._batch(user)
        response = _client(user).get(reverse("batch-export-csv", kwargs={"id": batch.id}))
        assert response.status_code == 200
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        assert rows[0][1] == "original_filename"
        assert rows[1][1] == "'=HYPERLINK(1).jpg"
        assert rows[1][3] == "fake"

    @pytest.mark.parametrize("value,expected", [("=1+1", "'=1+1"), ("+x", "'+x"), ("@a", "'@a"), ("ok.jpg", "ok.jpg"), (None, "")])
    def test_csv_safe(self, value, expected):
        assert csv_safe(value) == expected
