import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestFactCheckView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("factcheck")

    def _verified_user(self):
        user = UserFactory()
        user.is_verified = True
        user.save()
        return user

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, {"text": "Some claim here."})
        assert response.status_code == 401

    def test_unverified_user_returns_403(self):
        user = UserFactory(is_verified=False)
        self.client.force_authenticate(user=user)
        response = self.client.post(self.url, {"text": "Some claim here."})
        assert response.status_code == 403

    def test_missing_text_returns_400(self):
        self.client.force_authenticate(user=self._verified_user())
        response = self.client.post(self.url, {})
        assert response.status_code == 400
        assert "text" in response.data["error"].lower()

    def test_empty_text_returns_400(self):
        self.client.force_authenticate(user=self._verified_user())
        response = self.client.post(self.url, {"text": "   "})
        assert response.status_code == 400

    def test_too_long_text_returns_400(self):
        self.client.force_authenticate(user=self._verified_user())
        response = self.client.post(self.url, {"text": "x" * 10001})
        assert response.status_code == 400
        assert "long" in response.data["error"].lower()

    @patch("factcheck.views.analyze_text")
    def test_valid_text_returns_200(self, mock_analyze):
        mock_analyze.return_value = {
            "claims_count": 1,
            "overall_verdict": "mostly_accurate",
            "claims": [{"claim": "Paris is in France.", "assessment": "likely_true", "explanation": "yes", "fact_checks": []}],
            "entities": [],
        }
        self.client.force_authenticate(user=self._verified_user())
        response = self.client.post(self.url, {"text": "Paris is in France."})
        assert response.status_code == 200
        assert response.data["overall_verdict"] == "mostly_accurate"
        mock_analyze.assert_called_once_with("Paris is in France.")

    @patch("factcheck.views.analyze_text")
    def test_response_has_required_fields(self, mock_analyze):
        mock_analyze.return_value = {
            "claims_count": 0,
            "overall_verdict": "no_claims",
            "claims": [],
            "entities": [],
        }
        self.client.force_authenticate(user=self._verified_user())
        response = self.client.post(self.url, {"text": "Hello world test sentence."})
        assert response.status_code == 200
        assert "claims_count" in response.data
        assert "overall_verdict" in response.data
        assert "claims" in response.data
