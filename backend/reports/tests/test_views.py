import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from reports.models import Report
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory
from .factories import ReportFactory


@pytest.mark.django_db
class TestReportCreate:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("report-create")

    def test_report_success(self):
        sub = SubmissionFactory()
        response = self.client.post(self.url, {
            "submission": str(sub.id),
            "reason": "fake_content",
            "description": "Looks AI-generated",
        })
        assert response.status_code == 201
        assert Report.objects.filter(reporter=self.user, submission=sub).exists()

    def test_report_duplicate(self):
        sub = SubmissionFactory()
        self.client.post(self.url, {"submission": str(sub.id), "reason": "fake_content"})
        response = self.client.post(self.url, {"submission": str(sub.id), "reason": "spam"})
        assert response.status_code == 400

    def test_report_unauthenticated(self):
        sub = SubmissionFactory()
        response = APIClient().post(self.url, {"submission": str(sub.id), "reason": "fake_content"})
        assert response.status_code == 401


@pytest.mark.django_db
class TestReportList:
    def setup_method(self):
        self.url = reverse("report-list")

    def test_admin_can_list(self):
        admin = UserFactory(is_staff=True)
        client = APIClient()
        client.force_authenticate(user=admin)
        ReportFactory()
        ReportFactory()
        response = client.get(self.url)
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_non_admin_forbidden(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(self.url)
        assert response.status_code == 403

    def test_filter_by_status(self):
        admin = UserFactory(is_staff=True)
        client = APIClient()
        client.force_authenticate(user=admin)
        ReportFactory(status=Report.Status.PENDING)
        ReportFactory(status=Report.Status.RESOLVED)
        response = client.get(self.url, {"status": "pending"})
        assert response.data["count"] == 1
