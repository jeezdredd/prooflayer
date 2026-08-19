import pytest
from django.core.cache import cache

from analyzers.tasks import aggregate_verdicts
from content.models import Submission
from content.tests.factories import SubmissionFactory

from .factories import AnalysisResultFactory, AnalyzerConfigFactory


@pytest.mark.django_db
class TestAggregateVerdictsIdempotency:
    def test_second_call_is_skipped(self):
        config = AnalyzerConfigFactory(name="cf_idem", weight=1.0)
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        AnalysisResultFactory(
            submission=sub,
            analyzer=config,
            confidence=0.9,
            verdict="fake",
            evidence={"ai_probability": 0.97},
        )

        aggregate_verdicts([], str(sub.id))
        sub.refresh_from_db()
        first_score = sub.final_score
        assert sub.status == Submission.Status.COMPLETED

        sub.final_score = 0.123
        sub.save(update_fields=["final_score"])

        aggregate_verdicts([], str(sub.id))
        sub.refresh_from_db()
        assert sub.final_score == 0.123
        assert first_score != 0.123

    def test_runs_again_once_lock_expires(self):
        config = AnalyzerConfigFactory(name="cf_idem2", weight=1.0)
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        AnalysisResultFactory(
            submission=sub,
            analyzer=config,
            confidence=0.9,
            verdict="fake",
            evidence={"ai_probability": 0.97},
        )

        aggregate_verdicts([], str(sub.id))
        cache.delete(f"aggregating:{sub.id}")

        sub.final_score = 0.123
        sub.save(update_fields=["final_score"])
        aggregate_verdicts([], str(sub.id))
        sub.refresh_from_db()
        assert sub.final_score != 0.123
