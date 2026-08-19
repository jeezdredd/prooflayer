import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from content.models import Submission
from users.tests.factories import UserFactory

from .factories import SubmissionFactory


@pytest.mark.django_db
class TestWidgetEmbedAccess:
    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory(is_verified=True)

    def _url(self, sha):
        return reverse("widget-embed", kwargs={"sha256": sha})

    def test_private_submission_is_not_disclosed(self):
        SubmissionFactory(
            user=self.owner,
            status=Submission.Status.COMPLETED,
            is_public=False,
            sha256_hash="a" * 64,
            final_verdict="fake",
        )
        response = self.client.get(self._url("a" * 64))
        assert response.status_code == 200
        assert response.data["found"] is False
        assert response.data["verdict"] == "unknown"

    def test_public_submission_is_disclosed(self):
        SubmissionFactory(
            user=self.owner,
            status=Submission.Status.COMPLETED,
            is_public=True,
            sha256_hash="b" * 64,
            final_verdict="authentic",
        )
        response = self.client.get(self._url("b" * 64))
        assert response.status_code == 200
        assert response.data["found"] is True
        assert response.data["verdict"] == "authentic"

    def test_widget_is_throttled(self):
        from content.throttles import WidgetRateThrottle

        assert WidgetRateThrottle.scope == "widget"
        from content.views import WidgetEmbedView

        assert WidgetEmbedView.throttle_classes == [WidgetRateThrottle]
