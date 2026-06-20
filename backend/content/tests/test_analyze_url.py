import requests
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from users.tests.factories import UserFactory


class AnalyzeUrlViewTest(TestCase):
    URL = "/api/v1/content/analyze-url/"

    def setUp(self):
        self.client = APIClient()
        self.staff_user = UserFactory(is_staff=True, is_verified=True)
        self.regular_user = UserFactory(is_verified=True)

    def test_invalid_url_no_url_field(self):
        response = self.client.post(self.URL, {}, format="json")
        assert response.status_code == 400
        assert "detail" in response.data

    def test_invalid_scheme_ftp(self):
        response = self.client.post(self.URL, {"url": "ftp://example.com/img.jpg"}, format="json")
        assert response.status_code == 400
        assert "detail" in response.data

    @patch("common.url_safety.socket.gethostbyname", return_value="127.0.0.1")
    def test_ssrf_private_ip_loopback(self, mock_dns):
        response = self.client.post(self.URL, {"url": "http://127.0.0.1/img.jpg"}, format="json")
        assert response.status_code == 400
        assert response.data["detail"] == "URL not allowed"

    @patch("common.url_safety.socket.gethostbyname", return_value="169.254.169.254")
    def test_ssrf_link_local(self, mock_dns):
        response = self.client.post(self.URL, {"url": "http://metadata.internal/img.jpg"}, format="json")
        assert response.status_code == 400
        assert response.data["detail"] == "URL not allowed"

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.uploads_this_month", return_value=0)
    @patch("content.views.get_or_create_subscription")
    def test_auth_user_billing_limit_reached(self, mock_sub, mock_uploads, mock_dns):
        mock_subscription = MagicMock()
        mock_subscription.uploads_per_month = 0
        mock_sub.return_value = mock_subscription
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.URL, {"url": "http://example.com/img.jpg"}, format="json")
        assert response.status_code == 402
        assert response.data["code"] == "upload_limit_reached"

    @patch("content.views.process_submission.delay")
    @patch("content.views.validate_mime_type", return_value="image/jpeg")
    @patch("content.views.safe_get")
    @patch("content.views.uploads_this_month", return_value=0)
    @patch("content.views.get_or_create_subscription")
    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.Submission.objects.create")
    def test_auth_user_success(self, mock_create, mock_dns, mock_sub, mock_uploads, mock_get, mock_mime, mock_delay):
        mock_submission = MagicMock()
        mock_submission.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        mock_create.return_value = mock_submission
        mock_subscription = MagicMock()
        mock_subscription.uploads_per_month = 10
        mock_sub.return_value = mock_subscription
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_content.return_value = [b'\xff\xd8\xff' + b'x' * 100]
        mock_get.return_value = mock_resp
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.URL, {"url": "http://example.com/photo.jpg"}, format="json")
        assert response.status_code == 201
        assert "submission_id" in response.data
        mock_delay.assert_called_once()

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.AnonymousQuota.check_and_increment", return_value=(False, 0))
    def test_anonymous_quota_exceeded(self, mock_quota, mock_dns):
        response = self.client.post(self.URL, {"url": "http://example.com/img.jpg"}, format="json")
        assert response.status_code == 429
        assert response.data["code"] == "anonymous_limit_reached"
        assert "resets_in" in response.data

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.AnonymousQuota.check_and_increment", return_value=(True, 4))
    def test_anonymous_no_staff_user(self, mock_quota, mock_dns):
        with patch("content.views.User.objects") as mock_user_mgr:
            mock_filter = MagicMock()
            mock_filter.first.return_value = None
            mock_user_mgr.filter.return_value = mock_filter
            response = self.client.post(self.URL, {"url": "http://example.com/img.jpg"}, format="json")
        assert response.status_code == 503
        assert "detail" in response.data

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.AnonymousQuota.check_and_increment", return_value=(True, 4))
    @patch("content.views.safe_get")
    def test_anonymous_url_fetch_fails(self, mock_get, mock_quota, mock_dns):
        mock_get.side_effect = requests.RequestException("connection refused")
        with patch("content.views.User.objects") as mock_user_mgr:
            mock_filter = MagicMock()
            mock_filter.first.return_value = self.staff_user
            mock_user_mgr.filter.return_value = mock_filter
            response = self.client.post(self.URL, {"url": "http://example.com/img.jpg"}, format="json")
        assert response.status_code == 400
        assert "detail" in response.data

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.AnonymousQuota.check_and_increment", return_value=(True, 4))
    @patch("content.views.safe_get")
    def test_anonymous_file_too_large(self, mock_get, mock_quota, mock_dns):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        chunk_size = 21 * 1024 * 1024
        mock_resp.iter_content.return_value = [b'x' * chunk_size]
        mock_get.return_value = mock_resp
        with patch("content.views.User.objects") as mock_user_mgr:
            mock_filter = MagicMock()
            mock_filter.first.return_value = self.staff_user
            mock_user_mgr.filter.return_value = mock_filter
            response = self.client.post(self.URL, {"url": "http://example.com/img.jpg"}, format="json")
        assert response.status_code == 400
        assert "too large" in response.data["detail"].lower()

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.AnonymousQuota.check_and_increment", return_value=(True, 4))
    @patch("content.views.validate_mime_type")
    @patch("content.views.safe_get")
    def test_anonymous_unsupported_mime(self, mock_get, mock_mime, mock_quota, mock_dns):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_content.return_value = [b'\xff\xd8\xff' + b'x' * 100]
        mock_get.return_value = mock_resp
        mock_mime.side_effect = Exception("unsupported type")
        with patch("content.views.User.objects") as mock_user_mgr:
            mock_filter = MagicMock()
            mock_filter.first.return_value = self.staff_user
            mock_user_mgr.filter.return_value = mock_filter
            response = self.client.post(self.URL, {"url": "http://example.com/file.bmp"}, format="json")
        assert response.status_code == 400
        assert "unsupported" in response.data["detail"].lower()

    @patch("content.views.process_submission.delay")
    @patch("content.views.validate_mime_type", return_value="image/jpeg")
    @patch("content.views.safe_get")
    @patch("content.views.AnonymousQuota.check_and_increment", return_value=(True, 4))
    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    @patch("content.views.Submission.objects.create")
    def test_anonymous_full_success(self, mock_create, mock_dns, mock_quota, mock_get, mock_mime, mock_delay):
        mock_submission = MagicMock()
        mock_submission.id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        mock_create.return_value = mock_submission
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_content.return_value = [b'\xff\xd8\xff' + b'x' * 100]
        mock_get.return_value = mock_resp
        with patch("content.views.User.objects") as mock_user_mgr:
            mock_filter = MagicMock()
            mock_filter.first.return_value = self.staff_user
            mock_user_mgr.filter.return_value = mock_filter
            response = self.client.post(self.URL, {"url": "http://example.com/photo.jpg"}, format="json")
        assert response.status_code == 201
        assert "submission_id" in response.data
        mock_delay.assert_called_once()
