from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from analyzers import auto_retrain
from analyzers.models import RetrainRun
from api.models import Feedback
from billing.models import Subscription
from common.dashboard import build_dashboard, dashboard_callback
from content.models import Submission
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory

DASHBOARD_KEYS = {
    "submissions", "verdicts", "queue", "tribunal", "retrain", "training", "classroom", "users", "billing", "feedback",
    "links",
}


@pytest.fixture
def retrain_dirs(tmp_path, monkeypatch):
    for name, value in {
        "POOL": tmp_path / "auto" / "pool",
        "CALIBRATION": tmp_path / "auto" / "calibration",
        "HOLDOUT": tmp_path / "auto" / "holdout",
        "PREVIOUS": tmp_path / "image.previous",
    }.items():
        monkeypatch.setattr(auto_retrain, name, value)
    return tmp_path


def _request(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


@pytest.mark.django_db
class TestDashboardCallback:
    def test_empty_database_returns_every_section(self, retrain_dirs):
        context = dashboard_callback(_request(UserFactory(is_staff=True, is_superuser=True)), {})
        dashboard = context["dashboard"]
        assert set(dashboard) == DASHBOARD_KEYS
        assert dashboard["submissions"] == {"today": 0, "week": 0, "total": 0}
        assert dashboard["verdicts"]["total"] == 0
        assert dashboard["queue"]["stuck"] == 0
        assert dashboard["queue"]["review"] == 0
        assert dashboard["queue"]["objections_open"] == 0
        assert dashboard["retrain"] is None
        assert dashboard["training"]["pool"] == 0
        assert dashboard["training"]["holdout"] == 0
        assert dashboard["training"]["rollback_available"] is False
        assert dashboard["classroom"] == {"organizations": 0, "classrooms": 0, "students": 0}
        assert dashboard["billing"]["paid"] == 0
        assert dashboard["feedback"] == []
        assert dashboard["tribunal"]["version"]

    def test_staff_without_superuser_gets_no_dashboard(self, retrain_dirs):
        context = dashboard_callback(_request(UserFactory(is_staff=True)), {"title": "x"})
        assert "dashboard" not in context

    def test_counts_queue_verdicts_and_billing(self, retrain_dirs):
        stuck = SubmissionFactory(status=Submission.Status.PROCESSING)
        Submission.objects.filter(pk=stuck.pk).update(updated_at=timezone.now() - timedelta(minutes=30))
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="needs_review")
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="fake")
        paid = UserFactory()
        Subscription.objects.update_or_create(user=paid, defaults={"tier": Subscription.Tier.PRO})
        Feedback.objects.create(message="x" * 300)
        (retrain_dirs / "auto" / "pool" / "real").mkdir(parents=True)
        (retrain_dirs / "auto" / "pool" / "real" / "a.jpg").write_bytes(b"jpg")

        dashboard = build_dashboard()

        assert dashboard["queue"]["stuck"] == 1
        assert dashboard["queue"]["review"] == 1
        assert dashboard["verdicts"]["total"] == 2
        assert {row["key"]: row["count"] for row in dashboard["verdicts"]["rows"]}["fake"] == 1
        assert {row["tier"]: row["count"] for row in dashboard["billing"]["tiers"]}["pro"] == 1
        assert dashboard["feedback"][0]["message"].endswith("...")
        assert dashboard["training"]["pool"] == 1

    def test_latest_retrain_carries_holdout_rows(self, retrain_dirs):
        RetrainRun.objects.create(
            status=RetrainRun.Status.REJECTED,
            error="candidate calls 1 real photos AI",
            metrics={"live": {"ai_caught": 10, "real_fake": 0}, "candidate": {"ai_caught": 12, "real_fake": 1}},
        )
        retrain = build_dashboard()["retrain"]
        rows = {row["key"]: row for row in retrain["holdout"]}
        assert retrain["status"] == "rejected"
        assert retrain["variant"] == "warning"
        assert retrain["reason"] == "candidate calls 1 real photos AI"
        assert rows["ai_caught"]["delta"] == 2
        assert rows["ai_caught"]["variant"] == "success"
        assert rows["real_fake"]["variant"] == "danger"


@pytest.mark.django_db
class TestAdminIndex:
    def test_superuser_sees_dashboard(self, client, retrain_dirs):
        client.force_login(UserFactory(is_staff=True, is_superuser=True))
        response = client.get(reverse("admin:index"))
        assert response.status_code == 200
        assert b"Latest retrain" in response.content

    def test_staff_sees_app_list(self, client, retrain_dirs):
        client.force_login(UserFactory(is_staff=True))
        response = client.get(reverse("admin:index"))
        assert response.status_code == 200
        assert b"Latest retrain" not in response.content
