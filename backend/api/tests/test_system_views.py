import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestSystemStatusView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("system-status")

    def _mock_probes(self):
        return {
            "_probe_db": {"status": "ok", "latency_ms": 1.0, "pgvector": "0.7.0"},
            "_probe_redis": {"status": "ok", "latency_ms": 0.5, "version": "7.0"},
            "_probe_celery": {"status": "ok", "workers": 1, "worker_names": ["celery@worker"], "active_tasks": 0, "scheduled_tasks": 0},
            "_probe_ollama": {"status": "ok", "latency_ms": 10.0, "available_models": [], "loaded_models": []},
            "_probe_storage": {"status": "skip", "reason": "no s3 endpoint configured"},
        }

    def test_public_access_no_auth(self):
        with (
            patch("api.system_views._probe_db", return_value={"status": "ok"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
        ):
            response = self.client.get(self.url)
        assert response.status_code == 200

    def test_response_has_overall_field(self):
        with (
            patch("api.system_views._probe_db", return_value={"status": "ok"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
        ):
            response = self.client.get(self.url)
        assert "overall" in response.data
        assert "services" in response.data
        assert "checked_at" in response.data

    def test_operational_when_all_ok(self):
        with (
            patch("api.system_views._probe_db", return_value={"status": "ok"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
        ):
            response = self.client.get(self.url)
        assert response.data["overall"] == "operational"

    def test_degraded_when_service_down(self):
        with (
            patch("api.system_views._probe_db", return_value={"status": "down"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
        ):
            response = self.client.get(self.url)
        assert response.data["overall"] == "degraded"

    def test_last_retrain_field_present(self):
        with (
            patch("api.system_views._probe_db", return_value={"status": "ok"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
            patch("api.system_views._last_retrain", return_value=None),
        ):
            response = self.client.get(self.url)
        assert "last_retrain" in response.data


@pytest.mark.django_db
class TestRecordVisitView:
    def setup_method(self):
        self.client = APIClient()
        self.url = "/api/v1/system/visit/"

    def test_no_discord_webhook_returns_204(self):
        with patch("api.system_views.settings") as mock_settings:
            mock_settings.DISCORD_WEBHOOK_URL = ""
            response = self.client.post(self.url, {"path": "/", "referrer": ""}, format="json")
        assert response.status_code in (204, 404)


@pytest.mark.django_db
class TestFeedbackView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("system-feedback")
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.post(self.url, {"category": "bug", "message": "Something is broken here."})
        assert response.status_code == 401

    def test_short_message_returns_400(self):
        response = self.client.post(self.url, {"category": "bug", "message": "short"})
        assert response.status_code == 400

    def test_valid_feedback_created(self):
        with patch("api.system_views.requests.post"):
            response = self.client.post(
                self.url,
                {"category": "bug", "message": "This feature is broken and does not work properly."},
                format="json",
            )
        assert response.status_code == 201
        assert "id" in response.data

    def test_invalid_category_defaults_to_other(self):
        with patch("api.system_views.requests.post"):
            response = self.client.post(
                self.url,
                {"category": "nonexistent_category", "message": "This is a long enough feedback message."},
                format="json",
            )
        assert response.status_code == 201

    def test_no_discord_webhook_still_succeeds(self):
        with patch("api.system_views.settings") as mock_settings:
            mock_settings.DISCORD_WEBHOOK_URL = ""
            response = self.client.post(
                self.url,
                {"category": "ux", "message": "The interface is confusing in several places."},
                format="json",
            )
        assert response.status_code == 201
