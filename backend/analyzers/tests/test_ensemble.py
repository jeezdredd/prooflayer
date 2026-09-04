import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from analyzers.ensemble import ENSEMBLE_NAME, ENSEMBLE_VERSION, ensemble_info, ensemble_label, roster_fingerprint
from analyzers.management.commands.seed_analyzers import ANALYZERS
from content.models import Submission
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


class TestEnsembleIdentity:
    def test_label_joins_name_and_version(self):
        assert ensemble_label() == f"{ENSEMBLE_NAME} {ENSEMBLE_VERSION}"

    def test_info_lists_every_seeded_member(self):
        info = ensemble_info()
        assert [m["name"] for m in info["members"]] == [e["name"] for e in ANALYZERS]
        assert info["fingerprint"] == roster_fingerprint(ANALYZERS)
        assert len(info["fingerprint"]) == 12

    def test_fingerprint_is_order_independent(self):
        assert roster_fingerprint(ANALYZERS) == roster_fingerprint(list(reversed(ANALYZERS)))

    def test_fingerprint_changes_with_weight(self):
        tweaked = [dict(e) for e in ANALYZERS]
        tweaked[0]["weight"] = float(tweaked[0]["weight"]) + 1.0
        assert roster_fingerprint(tweaked) != roster_fingerprint(ANALYZERS)

    def test_fingerprint_changes_with_membership(self):
        assert roster_fingerprint(ANALYZERS[1:]) != roster_fingerprint(ANALYZERS)


@pytest.mark.django_db
class TestEnsembleExposure:
    def test_submission_detail_carries_ensemble(self):
        user = UserFactory(is_verified=True)
        sub = SubmissionFactory(user=user, status=Submission.Status.COMPLETED)
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(reverse("submission-detail", kwargs={"id": sub.id}))
        assert response.status_code == 200
        assert response.data["ensemble"]["label"] == ensemble_label()
        assert response.data["ensemble"]["fingerprint"] == roster_fingerprint(ANALYZERS)

    def test_status_probe_names_the_ensemble(self):
        from unittest.mock import patch
        from contextlib import ExitStack

        client = APIClient()
        patches = [
            patch("api.system_views._probe_db", return_value={"status": "ok"}),
            patch("api.system_views._probe_redis", return_value={"status": "ok"}),
            patch("api.system_views._probe_celery", return_value={"status": "ok"}),
            patch("api.system_views._probe_ollama", return_value={"status": "ok"}),
            patch("api.system_views._probe_storage", return_value={"status": "skip"}),
            patch("api.system_views._probe_email", return_value={"status": "ok"}),
        ]
        with ExitStack() as stack:
            for cm in patches:
                stack.enter_context(cm)
            response = client.get(reverse("system-status"))
        assert response.data["services"]["analyzers"]["ensemble"] == ensemble_label()
