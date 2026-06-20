import io

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from common.url_safety import UnsafeUrlError
from users.tests.factories import UserFactory


def _verified_user():
    user = UserFactory()
    user.is_verified = True
    user.save()
    return user


@pytest.mark.django_db
class TestFactCheckView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("factcheck")

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, {"text": "Some claim here."})
        assert response.status_code == 401

    def test_unverified_user_returns_403(self):
        user = UserFactory(is_verified=False)
        self.client.force_authenticate(user=user)
        response = self.client.post(self.url, {"text": "Some claim here."})
        assert response.status_code == 403

    def test_missing_text_returns_400(self):
        self.client.force_authenticate(user=_verified_user())
        response = self.client.post(self.url, {})
        assert response.status_code == 400
        assert "text" in response.data["error"].lower()

    def test_too_long_text_returns_400(self):
        self.client.force_authenticate(user=_verified_user())
        response = self.client.post(self.url, {"text": "x" * 10001})
        assert response.status_code == 400
        assert "long" in response.data["error"].lower()

    @patch("factcheck.views.run_factcheck.delay")
    def test_valid_text_dispatches_task_202(self, mock_delay):
        task = MagicMock()
        task.id = "task-abc-123"
        mock_delay.return_value = task
        self.client.force_authenticate(user=_verified_user())
        response = self.client.post(self.url, {"text": "Paris is in France."})
        assert response.status_code == 202
        assert response.data["task_id"] == "task-abc-123"
        mock_delay.assert_called_once_with("Paris is in France.")


@pytest.mark.django_db
class TestFactCheckExportView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("factcheck-export")
        self.client.force_authenticate(user=_verified_user())

    def test_missing_result_returns_400(self):
        response = self.client.post(self.url, {"text": "x"}, format="json")
        assert response.status_code == 400

    @patch("factcheck.views.render_factcheck_pdf", return_value=b"%PDF-1.4 fake")
    def test_valid_result_returns_pdf(self, mock_pdf):
        result = {"overall_verdict": "mostly_accurate", "claims_count": 0, "claims": [], "entities": []}
        response = self.client.post(self.url, {"result": result, "text": "src"}, format="json")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        mock_pdf.assert_called_once()

    @patch("factcheck.views.render_factcheck_pdf", side_effect=RuntimeError("weasyprint boom"))
    def test_render_failure_returns_generic_500(self, mock_pdf):
        result = {"overall_verdict": "mixed", "claims": []}
        response = self.client.post(self.url, {"result": result}, format="json")
        assert response.status_code == 500
        assert "weasyprint" not in str(response.data).lower()


@pytest.mark.django_db
class TestFactCheckFetchUrlView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("factcheck-fetch-url")
        self.client.force_authenticate(user=_verified_user())

    @patch("factcheck.views.safe_get", side_effect=UnsafeUrlError("URL not allowed"))
    def test_private_url_blocked_400(self, mock_get):
        response = self.client.post(self.url, {"url": "http://127.0.0.1/"}, format="json")
        assert response.status_code == 400

    @patch("factcheck.views.safe_get")
    def test_non_html_content_type_415(self, mock_get):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.headers = {"Content-Type": "application/pdf"}
        mock_get.return_value = resp
        response = self.client.post(self.url, {"url": "https://example.com/x.pdf"}, format="json")
        assert response.status_code == 415

    @patch("factcheck.views.trafilatura")
    @patch("factcheck.views.safe_get")
    def test_html_extracts_text(self, mock_get, mock_traf):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp.iter_content.return_value = [b"<html><body>Article body here.</body></html>"]
        mock_get.return_value = resp
        mock_traf.extract.return_value = "Article body here."
        mock_traf.extract_metadata.return_value = MagicMock(title="Title")
        response = self.client.post(self.url, {"url": "https://example.com/a"}, format="json")
        assert response.status_code == 200
        assert response.data["text"] == "Article body here."


@pytest.mark.django_db
class TestFactCheckExtractDocView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("factcheck-extract-doc")
        self.client.force_authenticate(user=_verified_user())

    def test_no_file_returns_400(self):
        response = self.client.post(self.url, {}, format="multipart")
        assert response.status_code == 400

    def test_oversize_returns_413(self):
        big = io.BytesIO(b"x" * (11 * 1024 * 1024))
        big.name = "big.pdf"
        response = self.client.post(self.url, {"file": big}, format="multipart")
        assert response.status_code == 413

    def test_unsupported_type_returns_415(self):
        f = io.BytesIO(b"plain text")
        f.name = "note.txt"
        response = self.client.post(self.url, {"file": f}, format="multipart")
        assert response.status_code == 415

    @patch("factcheck.views._extract_pdf", return_value="extracted pdf text")
    def test_pdf_returns_text(self, mock_pdf):
        f = io.BytesIO(b"%PDF-1.4 minimal")
        f.name = "doc.pdf"
        response = self.client.post(self.url, {"file": f}, format="multipart")
        assert response.status_code == 200
        assert response.data["text"] == "extracted pdf text"
