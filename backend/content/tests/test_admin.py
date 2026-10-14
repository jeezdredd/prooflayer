from unittest.mock import patch

import pytest
from django.contrib.admin import helpers
from django.urls import reverse

from analyzers.tests.factories import AnalysisResultFactory
from content.models import Submission
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory

CHANGELIST = "admin:content_submission_changelist"


@pytest.fixture
def superuser_client(client):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    return client


def _run_action(client, action, submissions):
    return client.post(
        reverse(CHANGELIST),
        {"action": action, helpers.ACTION_CHECKBOX_NAME: [str(s.id) for s in submissions]},
    )


@pytest.mark.django_db
class TestSubmissionAdmin:
    def test_changelist_renders(self, superuser_client):
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="needs_review", final_score=0.5)
        response = superuser_client.get(reverse(CHANGELIST))
        assert response.status_code == 200
        assert b"NEEDS REVIEW" in response.content
        assert b"50%" in response.content

    @patch("content.reanalysis.dispatch_analysis.delay")
    def test_reanalyze_restarts_finished_submissions(self, mock_delay, superuser_client):
        done = SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="fake", final_score=0.9)
        AnalysisResultFactory(submission=done)
        busy = SubmissionFactory(status=Submission.Status.PROCESSING)

        response = _run_action(superuser_client, "reanalyze", [done, busy])

        assert response.status_code == 302
        done.refresh_from_db()
        assert done.status == Submission.Status.PROCESSING
        assert done.final_verdict == ""
        assert done.final_score is None
        assert not done.analysis_results.exists()
        mock_delay.assert_called_once_with(str(done.id))

    def test_mark_verified_ai_sets_label(self, superuser_client):
        submission = SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="fake")
        with patch("content.admin.snapshot") as snapshot:
            _run_action(superuser_client, "approve_as_fake", [submission])
        submission.refresh_from_db()
        assert submission.approved_for_training is True
        assert submission.verified_label == "fake"
        snapshot.assert_called_once()

    def test_review_queue_link_filters(self, superuser_client):
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="needs_review")
        SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="fake")
        url = reverse(CHANGELIST) + "?status__exact=completed&final_verdict__in=needs_review,inconclusive"
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert response.context["cl"].result_count == 1


@pytest.mark.django_db
class TestOversightAdmins:
    @pytest.mark.parametrize(
        "name",
        [
            "admin:content_verdictobjection_changelist",
            "admin:content_verdictoverride_changelist",
            "admin:billing_subscription_changelist",
            "admin:classroom_classroom_changelist",
            "admin:classroom_organization_changelist",
            "admin:classroom_shadowset_changelist",
            "admin:analyzers_trainingsample_changelist",
            "admin:api_feedback_changelist",
        ],
    )
    def test_changelists_render(self, superuser_client, name):
        assert superuser_client.get(reverse(name)).status_code == 200
