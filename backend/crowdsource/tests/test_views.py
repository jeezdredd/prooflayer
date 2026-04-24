import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from crowdsource.models import Vote
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestVoteCreate:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("vote-create")

    def test_vote_success(self):
        sub = SubmissionFactory()
        response = self.client.post(self.url, {"submission": str(sub.id), "value": "fake"})
        assert response.status_code == 201
        assert Vote.objects.filter(user=self.user, submission=sub).exists()

    def test_vote_update(self):
        sub = SubmissionFactory()
        self.client.post(self.url, {"submission": str(sub.id), "value": "fake"})
        response = self.client.post(self.url, {"submission": str(sub.id), "value": "real"})
        assert response.status_code == 200
        assert Vote.objects.get(user=self.user, submission=sub).value == "real"

    def test_vote_invalid_value(self):
        sub = SubmissionFactory()
        response = self.client.post(self.url, {"submission": str(sub.id), "value": "invalid"})
        assert response.status_code == 400

    def test_vote_unauthenticated(self):
        sub = SubmissionFactory()
        response = APIClient().post(self.url, {"submission": str(sub.id), "value": "fake"})
        assert response.status_code == 401


@pytest.mark.django_db
class TestVoteStats:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_stats_correct_counts(self):
        sub = SubmissionFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        Vote.objects.create(user=self.user, submission=sub, value="fake")
        Vote.objects.create(user=user2, submission=sub, value="fake")
        Vote.objects.create(user=user3, submission=sub, value="real")
        url = reverse("vote-stats", kwargs={"submission_id": sub.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data["fake_count"] == 2
        assert response.data["real_count"] == 1
        assert response.data["total"] == 3
        assert response.data["user_vote"] == "fake"

    def test_stats_no_votes(self):
        sub = SubmissionFactory()
        url = reverse("vote-stats", kwargs={"submission_id": sub.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data["total"] == 0
        assert response.data["user_vote"] is None
