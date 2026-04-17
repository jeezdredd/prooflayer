import pytest

from analyzers.aggregator import aggregate
from analyzers.models import AnalysisResult
from .factories import AnalysisResultFactory, AnalyzerConfigFactory


@pytest.mark.django_db
class TestAggregate:
    def test_single_authentic(self):
        result = AnalysisResultFactory(confidence=0.8, verdict=AnalysisResult.Verdict.AUTHENTIC)
        score, verdict = aggregate([result])
        assert score < 0.3
        assert verdict == "authentic"

    def test_single_fake(self):
        result = AnalysisResultFactory(confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        score, verdict = aggregate([result])
        assert score > 0.7
        assert verdict == "fake"

    def test_all_errors_returns_inconclusive(self):
        result = AnalysisResultFactory(confidence=0.0, verdict=AnalysisResult.Verdict.ERROR)
        score, verdict = aggregate([result])
        assert verdict == "inconclusive"

    def test_empty_results(self):
        score, verdict = aggregate([])
        assert verdict == "inconclusive"

    def test_disagreement_flags_review(self):
        config1 = AnalyzerConfigFactory(name="analyzer_a")
        config2 = AnalyzerConfigFactory(name="analyzer_b")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(
            submission=sub, analyzer=config1,
            confidence=0.9, verdict=AnalysisResult.Verdict.AUTHENTIC
        )
        r2 = AnalysisResultFactory(
            submission=sub, analyzer=config2,
            confidence=0.9, verdict=AnalysisResult.Verdict.FAKE
        )
        score, verdict = aggregate([r1, r2])
        assert verdict == "needs_review"

    def test_weighted_scoring(self):
        config_heavy = AnalyzerConfigFactory(name="heavy", weight=3.0)
        config_light = AnalyzerConfigFactory(name="light", weight=1.0)
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(
            submission=sub, analyzer=config_heavy,
            confidence=0.8, verdict=AnalysisResult.Verdict.AUTHENTIC
        )
        r2 = AnalysisResultFactory(
            submission=sub, analyzer=config_light,
            confidence=0.8, verdict=AnalysisResult.Verdict.SUSPICIOUS
        )
        score, _ = aggregate([r1, r2])
        assert score < 0.4
