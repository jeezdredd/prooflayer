import pytest
from rest_framework.test import APIClient

from content.models import Submission, VerdictOverride
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestReviewQueue:
    def setup_method(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.user = UserFactory()

    def test_queue_lists_needs_review_and_inconclusive(self):
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="needs_review")
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="inconclusive")
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="fake")
        self.client.force_authenticate(self.staff)
        resp = self.client.get("/api/v1/content/review/queue/")
        assert resp.status_code == 200
        results = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        assert len(results) == 2

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get("/api/v1/content/review/queue/")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestVerdictOverride:
    def setup_method(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.sub = SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="needs_review")

    def test_override_updates_verdict_and_creates_audit(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(
            f"/api/v1/content/review/{self.sub.id}/override/",
            {"verdict": "fake", "reason": "obvious deepfake"},
            format="json",
        )
        assert resp.status_code == 201
        self.sub.refresh_from_db()
        assert self.sub.final_verdict == "fake"
        assert VerdictOverride.objects.filter(submission=self.sub).count() == 1
        ov = VerdictOverride.objects.get(submission=self.sub)
        assert ov.previous_verdict == "needs_review"
        assert ov.new_verdict == "fake"
        assert ov.reviewer == self.staff

    def test_invalid_verdict_rejected(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(
            f"/api/v1/content/review/{self.sub.id}/override/",
            {"verdict": "bogus", "reason": ""},
            format="json",
        )
        assert resp.status_code == 400

    def test_non_staff_cannot_override(self):
        user = UserFactory()
        self.client.force_authenticate(user)
        resp = self.client.post(
            f"/api/v1/content/review/{self.sub.id}/override/",
            {"verdict": "fake", "reason": ""},
            format="json",
        )
        assert resp.status_code == 403
