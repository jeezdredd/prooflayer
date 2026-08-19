import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from content.models import Submission
from users.tests.factories import UserFactory

from .factories import SubmissionFactory


@pytest.mark.django_db
class TestSubmissionStatusAccess:
    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory(is_verified=True)

    def _url(self, submission):
        return reverse("submission-status", kwargs={"id": submission.id})

    def test_anonymous_cannot_read_private_submission(self):
        submission = SubmissionFactory(user=self.owner, status=Submission.Status.COMPLETED, is_public=False)
        response = self.client.get(self._url(submission))
        assert response.status_code == 404

    def test_other_user_cannot_read_private_submission(self):
        submission = SubmissionFactory(user=self.owner, status=Submission.Status.COMPLETED, is_public=False)
        self.client.force_authenticate(user=UserFactory(is_verified=True))
        response = self.client.get(self._url(submission))
        assert response.status_code == 404

    def test_owner_can_read_own_submission(self):
        submission = SubmissionFactory(user=self.owner, status=Submission.Status.PROCESSING)
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self._url(submission))
        assert response.status_code == 200
        assert response.data["status"] == Submission.Status.PROCESSING

    def test_staff_can_read_any_submission(self):
        submission = SubmissionFactory(user=self.owner, status=Submission.Status.COMPLETED)
        self.client.force_authenticate(user=UserFactory(is_staff=True, is_verified=True))
        response = self.client.get(self._url(submission))
        assert response.status_code == 200

    def test_public_submission_readable_anonymously(self):
        submission = SubmissionFactory(user=self.owner, status=Submission.Status.COMPLETED, is_public=True)
        response = self.client.get(self._url(submission))
        assert response.status_code == 200

    def test_analyze_url_submission_stays_pollable(self):
        submission = SubmissionFactory(
            user=self.owner,
            status=Submission.Status.PROCESSING,
            source_url="https://example.com/cat.jpg",
        )
        response = self.client.get(self._url(submission))
        assert response.status_code == 200
