import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from content.tests.factories import SubmissionFactory
from provenance.models import ProvenanceResult
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestProvenanceListView:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def _url(self, submission_id):
        return reverse("provenance-list", kwargs={"submission_id": submission_id})

    def test_unauthenticated_returns_401(self):
        submission = SubmissionFactory(user=self.user)
        client = APIClient()
        response = client.get(self._url(submission.id))
        assert response.status_code == 401

    def test_empty_list_when_no_results(self):
        submission = SubmissionFactory(user=self.user)
        response = self.client.get(self._url(submission.id))
        assert response.status_code == 200
        assert response.data == []

    def test_returns_own_provenance_results(self):
        submission = SubmissionFactory(user=self.user)
        ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.PHASH_MATCH,
            title="match.jpg",
            similarity_score=0.95,
        )
        response = self.client.get(self._url(submission.id))
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["title"] == "match.jpg"

    def test_cannot_see_other_users_results(self):
        other_user = UserFactory()
        submission = SubmissionFactory(user=other_user)
        ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.TINEYE,
            title="secret.jpg",
        )
        response = self.client.get(self._url(submission.id))
        assert response.status_code == 200
        assert response.data == []

    def test_result_fields_present(self):
        submission = SubmissionFactory(user=self.user)
        ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.CLIP_NEIGHBOUR,
            title="neighbor.jpg",
            similarity_score=0.88,
            source_url="",
        )
        response = self.client.get(self._url(submission.id))
        assert response.status_code == 200
        item = response.data[0]
        assert "id" in item
        assert "source_type" in item
        assert "similarity_score" in item
        assert "found_at" in item
