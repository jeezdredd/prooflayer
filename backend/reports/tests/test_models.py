import pytest
from django.db import IntegrityError

from reports.models import Report
from .factories import ReportFactory


@pytest.mark.django_db
class TestReportModel:
    def test_create_report(self):
        report = ReportFactory()
        assert report.status == Report.Status.PENDING
        assert report.pk is not None

    def test_unique_reporter_submission(self):
        report = ReportFactory()
        with pytest.raises(IntegrityError):
            ReportFactory(reporter=report.reporter, submission=report.submission)

    def test_reason_choices(self):
        reasons = {c.value for c in Report.Reason}
        assert reasons == {"fake_content", "misleading", "copyright", "spam", "other"}
