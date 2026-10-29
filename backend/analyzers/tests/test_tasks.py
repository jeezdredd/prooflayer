import pytest
from unittest.mock import patch, MagicMock

from analyzers.tasks import aggregate_verdicts, dispatch_analysis, queue_follow_ups, refresh_verdict, run_analyzer
from analyzers.models import AnalysisResult
from content.models import Submission
from content.tests.factories import SubmissionFactory
from .factories import AnalyzerConfigFactory, AnalysisResultFactory


@pytest.mark.django_db
class TestRunAnalyzer:
    @patch("analyzers.tasks.load_analyzer_class")
    def test_success(self, mock_load):
        from analyzers.base import AnalysisOutput
        mock_analyzer = MagicMock()
        mock_analyzer.return_value.supported_mime_types.return_value = ["image/jpeg"]
        mock_analyzer.return_value.analyze.return_value = AnalysisOutput(
            confidence=0.7, verdict="suspicious", evidence={"test": True}
        )
        mock_load.return_value = mock_analyzer

        sub = SubmissionFactory(mime_type="image/jpeg")
        config = AnalyzerConfigFactory()

        result_id = run_analyzer(str(sub.id), config.id)
        assert result_id is not None

        ar = AnalysisResult.objects.get(id=result_id)
        assert ar.confidence == 0.7
        assert ar.verdict == "suspicious"

    @patch("analyzers.tasks.load_analyzer_class")
    def test_unsupported_mime_skipped(self, mock_load):
        mock_analyzer = MagicMock()
        mock_analyzer.return_value.supported_mime_types.return_value = ["image/png"]
        mock_load.return_value = mock_analyzer

        sub = SubmissionFactory(mime_type="image/jpeg")
        config = AnalyzerConfigFactory()

        result_id = run_analyzer(str(sub.id), config.id)
        assert result_id is None

    @patch("analyzers.tasks.load_analyzer_class")
    def test_error_saved(self, mock_load):
        mock_load.side_effect = Exception("boom")

        sub = SubmissionFactory(mime_type="image/jpeg")
        config = AnalyzerConfigFactory()

        result_id = run_analyzer(str(sub.id), config.id)
        assert result_id is None

        ar = AnalysisResult.objects.get(submission=sub, analyzer=config)
        assert ar.verdict == "error"
        assert "boom" in ar.error_message


@pytest.mark.django_db
class TestAggregateVerdicts:
    def test_marks_completed(self):
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        config = AnalyzerConfigFactory()
        AnalysisResultFactory(
            submission=sub, analyzer=config,
            confidence=0.8, verdict=AnalysisResult.Verdict.AUTHENTIC
        )
        aggregate_verdicts([], str(sub.id))
        sub.refresh_from_db()
        assert sub.status == Submission.Status.COMPLETED
        assert sub.final_score is not None
        assert sub.final_verdict != ""

    def test_no_results_inconclusive(self):
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        aggregate_verdicts([], str(sub.id))
        sub.refresh_from_db()
        assert sub.final_verdict == "inconclusive"


@pytest.mark.django_db
class TestDispatchAnalysis:
    def test_no_active_analyzers(self):
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        dispatch_analysis(str(sub.id))
        sub.refresh_from_db()
        assert sub.status == Submission.Status.COMPLETED
        assert sub.final_verdict == "inconclusive"


@pytest.mark.django_db
class TestFollowUpAnalyzers:
    def test_slow_map_is_not_part_of_the_verdict_chord(self):
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        AnalyzerConfigFactory(name="community_forensics", is_active=True)
        AnalyzerConfigFactory(name="manipulation_map", is_active=True)
        with patch("analyzers.tasks.chord") as chord, patch("analyzers.tasks.group") as group:
            dispatch_analysis(str(sub.id))
        signatures = group.call_args.args[0]
        assert len(signatures) == 1
        chord.assert_called_once()

    def test_map_is_queued_after_the_verdict_once(self):
        sub = SubmissionFactory(status=Submission.Status.COMPLETED)
        config = AnalyzerConfigFactory(name="manipulation_map", is_active=True)
        with patch("analyzers.tasks.chain") as chain:
            assert queue_follow_ups(sub) == 1
        chain.return_value.apply_async.assert_called_once()
        AnalysisResultFactory(submission=sub, analyzer=config, confidence=0.0, verdict=AnalysisResult.Verdict.INCONCLUSIVE)
        with patch("analyzers.tasks.chain") as chain:
            assert queue_follow_ups(sub) == 0
        chain.assert_not_called()

    def test_verdict_is_refreshed_when_the_map_finds_an_edit(self):
        sub = SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="authentic", final_score=0.1)
        AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="community_forensics", weight=3.5),
            confidence=0.85, verdict=AnalysisResult.Verdict.AUTHENTIC, evidence={"ai_probability": 0.05},
        )
        AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="manipulation_map", weight=0.0),
            confidence=0.0, verdict=AnalysisResult.Verdict.INCONCLUSIVE, evidence={"manipulation_suspected": True},
        )
        refresh_verdict(str(sub.id))
        sub.refresh_from_db()
        assert sub.final_verdict == "authentic_edited"
