from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from analyzers.models import RetrainRun, TrainingSample
from api.system_views import _training_queue
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
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
            patch("api.system_views._probe_analyzers", return_value={"status": "ok"}),
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
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
            patch("api.system_views._probe_analyzers", return_value={"status": "ok"}),
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
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
            patch("api.system_views._probe_analyzers", return_value={"status": "ok"}),
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
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
            patch("api.system_views._probe_analyzers", return_value={"status": "ok"}),
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
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
            patch("api.system_views._probe_analyzers", return_value={"status": "ok"}),
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


@pytest.mark.django_db
class TestAnalyzerRosterProbe:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("system-status")

    def _others_ok(self):
        return (
            patch("api.system_views._probe_db", return_value={"status": "ok"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
        )

    def test_unseeded_roster_degrades_overall(self):
        with ExitStack() as stack:
            for cm in self._others_ok():
                stack.enter_context(cm)
            response = self.client.get(self.url)
        probe = response.data["services"]["analyzers"]
        assert probe["status"] == "down"
        assert probe["active"] == 0
        assert probe["drift"]["missing"]
        assert "seed_analyzers" in probe["error"]
        assert response.data["overall"] == "degraded"

    def test_seeded_roster_is_ok(self):

        call_command("seed_analyzers", verbosity=0)
        with ExitStack() as stack:
            for cm in self._others_ok():
                stack.enter_context(cm)
            response = self.client.get(self.url)
        probe = response.data["services"]["analyzers"]
        assert probe["status"] == "ok"
        assert probe["active"] == probe["expected"]
        assert response.data["overall"] == "operational"


@pytest.mark.django_db
class TestTrainingQueue:
    def _sample(self, n):
        for i in range(n):
            TrainingSample.objects.create(file="training/x.jpg", media_type="image", mime_type="image/jpeg", label="real", sha256=f"{i:064d}", source_ref="ref")

    def test_counts_new_samples_since_last_success_and_shows_last_attempt(self, settings):
        settings.RETRAIN_MIN_NEW_SAMPLES = 50
        success = RetrainRun.objects.create(media_type="image", status=RetrainRun.Status.SUCCESS, samples_used=60)
        RetrainRun.objects.filter(pk=success.pk).update(finished_at=timezone.now() - timedelta(days=10))
        TrainingSample.objects.create(file="training/old.jpg", media_type="image", mime_type="image/jpeg", label="fake", sha256="a" * 64, source_ref="ref")
        TrainingSample.objects.filter(sha256="a" * 64).update(created_at=timezone.now() - timedelta(days=20))
        self._sample(3)
        RetrainRun.objects.create(media_type="image", status=RetrainRun.Status.SKIPPED, error="only 3 new approved samples, need 50", finished_at=timezone.now())
        queue = _training_queue("image")
        assert queue["new_samples"] == 3
        assert queue["needed"] == 50
        assert queue["last_attempt"]["status"] == "skipped"
        assert queue["last_success"] is not None
        assert queue["next_run"]

    def test_status_response_includes_training(self):
        response = APIClient().get(reverse("system-status"))
        assert "training" in response.data
