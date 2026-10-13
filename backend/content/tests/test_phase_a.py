from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from analyzers.ensemble import ensemble_info
from analyzers.models import AnalysisResult
from analyzers.tasks import AGGREGATION_LOCK_KEY, aggregate_verdicts
from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from billing.models import Subscription, get_or_create_subscription
from billing.permissions import tier_allows
from content.models import Submission
from users.tests.factories import UserFactory

from .factories import SubmissionFactory


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _set_tier(user, tier):
    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.save(update_fields=["tier"])


@pytest.mark.django_db
class TestTierGates:
    def test_free_user_gets_402_on_compare(self):
        user = UserFactory(is_verified=True)
        a, b = SubmissionFactory(user=user), SubmissionFactory(user=user)
        response = _client(user).get(reverse("submission-compare"), {"ids": f"{a.id},{b.id}"})
        assert response.status_code == 402
        assert response.data["code"] == "upgrade_required"

    def test_pro_user_can_compare(self):
        user = UserFactory(is_verified=True)
        _set_tier(user, Subscription.Tier.PRO)
        a, b = SubmissionFactory(user=user), SubmissionFactory(user=user)
        response = _client(user).get(reverse("submission-compare"), {"ids": f"{a.id},{b.id}"})
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_staff_bypasses_tier(self):
        staff = UserFactory(is_staff=True, is_verified=True)
        assert tier_allows(staff, "can_api") is True

    def test_inactive_subscription_loses_feature(self):
        user = UserFactory(is_verified=True)
        _set_tier(user, Subscription.Tier.PRO)
        sub = get_or_create_subscription(user)
        sub.status = Subscription.Status.CANCELLED
        sub.save(update_fields=["status"])
        assert tier_allows(user, "can_compare") is False

    def test_anonymous_never_allowed(self):
        assert tier_allows(None, "can_compare") is False


@pytest.mark.django_db
class TestTribunalStamp:
    def test_aggregation_stamps_current_tribunal(self):
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="cf_stamp"),
            verdict="fake", confidence=0.9, evidence={"ai_probability": 0.95},
        )
        aggregate_verdicts([], str(sub.id))
        sub.refresh_from_db()
        info = ensemble_info()
        assert sub.tribunal_version == info["version"]
        assert sub.tribunal_fingerprint == info["fingerprint"]

    def test_detail_reports_stored_stamp_not_current(self):
        user = UserFactory(is_verified=True)
        sub = SubmissionFactory(
            user=user, status=Submission.Status.COMPLETED,
            tribunal_version="0.9", tribunal_fingerprint="deadbeef0000",
        )
        response = _client(user).get(reverse("submission-detail", kwargs={"id": sub.id}))
        ensemble = response.data["ensemble"]
        assert ensemble["version"] == "0.9"
        assert ensemble["fingerprint"] == "deadbeef0000"
        assert ensemble["current_version"] == ensemble_info()["version"]
        assert ensemble["is_current"] is False

    def test_current_stamp_is_current(self):
        user = UserFactory(is_verified=True)
        info = ensemble_info()
        sub = SubmissionFactory(
            user=user, status=Submission.Status.COMPLETED,
            tribunal_version=info["version"], tribunal_fingerprint=info["fingerprint"],
        )
        response = _client(user).get(reverse("submission-detail", kwargs={"id": sub.id}))
        assert response.data["ensemble"]["is_current"] is True

    def test_unstamped_legacy_submission_has_no_ensemble(self):
        user = UserFactory(is_verified=True)
        sub = SubmissionFactory(user=user, status=Submission.Status.COMPLETED)
        response = _client(user).get(reverse("submission-detail", kwargs={"id": sub.id}))
        assert response.data["ensemble"] is None


@pytest.mark.django_db
class TestReanalyze:
    def _completed(self, user):
        sub = SubmissionFactory(
            user=user, status=Submission.Status.COMPLETED,
            final_verdict="fake", final_score=0.9, tribunal_version="1.0",
        )
        AnalysisResultFactory(submission=sub, analyzer=AnalyzerConfigFactory(name="old_member"))
        return sub

    @patch("content.views.dispatch_analysis.delay")
    def test_resets_results_and_redispatches(self, mock_delay):
        user = UserFactory(is_verified=True)
        sub = self._completed(user)
        cache.set(AGGREGATION_LOCK_KEY.format(submission_id=sub.id), 1, 600)
        response = _client(user).post(reverse("submission-reanalyze", kwargs={"id": sub.id}))
        assert response.status_code == 202
        sub.refresh_from_db()
        assert sub.status == Submission.Status.PROCESSING
        assert sub.final_verdict == ""
        assert sub.final_score is None
        assert AnalysisResult.objects.filter(submission=sub).count() == 0
        assert cache.get(AGGREGATION_LOCK_KEY.format(submission_id=sub.id)) is None
        mock_delay.assert_called_once_with(str(sub.id))

    @patch("content.views.dispatch_analysis.delay")
    def test_refuses_while_processing(self, mock_delay):
        user = UserFactory(is_verified=True)
        sub = SubmissionFactory(user=user, status=Submission.Status.PROCESSING)
        response = _client(user).post(reverse("submission-reanalyze", kwargs={"id": sub.id}))
        assert response.status_code == 409
        mock_delay.assert_not_called()

    @patch("content.views.dispatch_analysis.delay")
    def test_other_user_cannot_reanalyze(self, mock_delay):
        owner = UserFactory(is_verified=True)
        sub = self._completed(owner)
        response = _client(UserFactory(is_verified=True)).post(reverse("submission-reanalyze", kwargs={"id": sub.id}))
        assert response.status_code == 404
        mock_delay.assert_not_called()

    @patch("content.views.uploads_this_month", return_value=10_000)
    @patch("content.views.dispatch_analysis.delay")
    def test_quota_exhausted_blocks(self, mock_delay, mock_uploads):
        user = UserFactory(is_verified=True)
        sub = self._completed(user)
        response = _client(user).post(reverse("submission-reanalyze", kwargs={"id": sub.id}))
        assert response.status_code == 402
        mock_delay.assert_not_called()
