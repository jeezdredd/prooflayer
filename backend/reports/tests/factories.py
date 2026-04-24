import factory

from reports.models import Report
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Report

    reporter = factory.SubFactory(UserFactory)
    submission = factory.SubFactory(SubmissionFactory)
    reason = Report.Reason.FAKE_CONTENT
    description = "Test report"
