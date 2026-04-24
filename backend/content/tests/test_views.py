import io
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from content.models import Submission
from users.tests.factories import UserFactory
from .factories import SubmissionFactory


@pytest.mark.django_db
class TestSubmissionCreate:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("submission-list")

    def _make_jpeg(self):
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return SimpleUploadedFile("test.jpg", buf.read(), content_type="image/jpeg")

    @patch("content.tasks.process_submission.delay")
    def test_upload_success(self, mock_task):
        response = self.client.post(self.url, {"file": self._make_jpeg()}, format="multipart")
        assert response.status_code == 201
        assert response.data["status"] == "pending"
        mock_task.assert_called_once()

    def test_upload_no_file(self):
        response = self.client.post(self.url, {}, format="multipart")
        assert response.status_code == 400

    def test_upload_invalid_mime(self):
        f = SimpleUploadedFile("test.txt", b"hello world", content_type="text/plain")
        response = self.client.post(self.url, {"file": f}, format="multipart")
        assert response.status_code == 400

    def test_upload_unauthenticated(self):
        client = APIClient()
        response = client.post(self.url, {"file": self._make_jpeg()}, format="multipart")
        assert response.status_code == 401


@pytest.mark.django_db
class TestSubmissionList:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("submission-list")

    def test_list_own_submissions(self):
        SubmissionFactory(user=self.user)
        SubmissionFactory(user=self.user)
        SubmissionFactory()
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_cannot_see_other_user_submissions(self):
        SubmissionFactory()
        response = self.client.get(self.url)
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestSubmissionDetail:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_own(self):
        sub = SubmissionFactory(user=self.user)
        url = reverse("submission-detail", kwargs={"id": sub.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == str(sub.id)

    def test_cannot_retrieve_other(self):
        sub = SubmissionFactory()
        url = reverse("submission-detail", kwargs={"id": sub.id})
        response = self.client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestSubmissionListFilters:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("submission-list")

    def test_filter_by_status(self):
        SubmissionFactory(user=self.user, status="completed")
        SubmissionFactory(user=self.user, status="pending")
        response = self.client.get(self.url, {"status": "completed"})
        assert response.data["count"] == 1

    def test_filter_by_verdict(self):
        SubmissionFactory(user=self.user, final_verdict="fake")
        SubmissionFactory(user=self.user, final_verdict="authentic")
        response = self.client.get(self.url, {"final_verdict": "fake"})
        assert response.data["count"] == 1

    def test_search_by_filename(self):
        SubmissionFactory(user=self.user, original_filename="photo.jpg")
        SubmissionFactory(user=self.user, original_filename="document.png")
        response = self.client.get(self.url, {"search": "photo"})
        assert response.data["count"] == 1

    def test_ordering_by_file_size(self):
        SubmissionFactory(user=self.user, file_size=100)
        SubmissionFactory(user=self.user, file_size=500)
        response = self.client.get(self.url, {"ordering": "file_size"})
        assert response.data["results"][0]["file_size"] == 100


@pytest.mark.django_db
class TestSubmissionDelete:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_delete_own(self):
        sub = SubmissionFactory(user=self.user)
        url = reverse("submission-detail", kwargs={"id": sub.id})
        response = self.client.delete(url)
        assert response.status_code == 204
        assert not Submission.objects.filter(id=sub.id).exists()

    def test_cannot_delete_other(self):
        sub = SubmissionFactory()
        url = reverse("submission-detail", kwargs={"id": sub.id})
        response = self.client.delete(url)
        assert response.status_code == 404
