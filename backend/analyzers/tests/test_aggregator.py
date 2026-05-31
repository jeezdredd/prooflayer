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

    def test_single_fake_downgraded_to_suspicious(self):
        result = AnalysisResultFactory(confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        score, verdict = aggregate([result])
        assert score > 0.7
        assert verdict == "suspicious"

    def test_two_fake_voters_confirms_fake(self):
        config1 = AnalyzerConfigFactory(name="fake_a")
        config2 = AnalyzerConfigFactory(name="fake_b")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=config1, confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        r2 = AnalysisResultFactory(submission=sub, analyzer=config2, confidence=0.85, verdict=AnalysisResult.Verdict.FAKE)
        score, verdict = aggregate([r1, r2])
        assert verdict == "fake"
        assert score > 0.9

    def test_fake_plus_suspicious_corroborates(self):
        config1 = AnalyzerConfigFactory(name="strong_fake")
        config2 = AnalyzerConfigFactory(name="weak_susp")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=config1, confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        r2 = AnalysisResultFactory(submission=sub, analyzer=config2, confidence=0.7, verdict=AnalysisResult.Verdict.SUSPICIOUS)
        score, verdict = aggregate([r1, r2])
        assert verdict in ("fake", "likely_fake")

    def test_low_conf_fake_not_counted_as_corroborator(self):
        config1 = AnalyzerConfigFactory(name="hi_conf_fake")
        config2 = AnalyzerConfigFactory(name="lo_conf_fake")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=config1, confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        r2 = AnalysisResultFactory(submission=sub, analyzer=config2, confidence=0.4, verdict=AnalysisResult.Verdict.FAKE)
        score, verdict = aggregate([r1, r2])
        assert verdict == "suspicious"

    def test_three_way_split_needs_review(self):
        c1 = AnalyzerConfigFactory(name="rev_a")
        c2 = AnalyzerConfigFactory(name="rev_b")
        c3 = AnalyzerConfigFactory(name="rev_c")
        c4 = AnalyzerConfigFactory(name="rev_d")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=c1, confidence=0.85, verdict=AnalysisResult.Verdict.FAKE)
        r2 = AnalysisResultFactory(submission=sub, analyzer=c2, confidence=0.85, verdict=AnalysisResult.Verdict.FAKE)
        r3 = AnalysisResultFactory(submission=sub, analyzer=c3, confidence=0.85, verdict=AnalysisResult.Verdict.AUTHENTIC)
        r4 = AnalysisResultFactory(submission=sub, analyzer=c4, confidence=0.85, verdict=AnalysisResult.Verdict.AUTHENTIC)
        score, verdict = aggregate([r1, r2, r3, r4])
        assert verdict == "needs_review"

    def test_authentic_requires_one_voter(self):
        result = AnalysisResultFactory(confidence=0.3, verdict=AnalysisResult.Verdict.AUTHENTIC)
        score, verdict = aggregate([result])
        assert verdict == "inconclusive"

    def test_errors_filtered_out(self):
        config1 = AnalyzerConfigFactory(name="err_a")
        config2 = AnalyzerConfigFactory(name="ok_b")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=config1, confidence=0.0, verdict=AnalysisResult.Verdict.ERROR)
        r2 = AnalysisResultFactory(submission=sub, analyzer=config2, confidence=0.9, verdict=AnalysisResult.Verdict.AUTHENTIC)
        score, verdict = aggregate([r1, r2])
        assert verdict == "authentic"

    def test_all_errors_returns_inconclusive(self):
        result = AnalysisResultFactory(confidence=0.0, verdict=AnalysisResult.Verdict.ERROR)
        score, verdict = aggregate([result])
        assert verdict == "inconclusive"

    def test_empty_results(self):
        score, verdict = aggregate([])
        assert verdict == "inconclusive"

    def test_disagreement_flags_review(self):
        c1 = AnalyzerConfigFactory(name="dis_a")
        c2 = AnalyzerConfigFactory(name="dis_b")
        c3 = AnalyzerConfigFactory(name="dis_c")
        c4 = AnalyzerConfigFactory(name="dis_d")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=c1, confidence=0.9, verdict=AnalysisResult.Verdict.AUTHENTIC)
        r2 = AnalysisResultFactory(submission=sub, analyzer=c2, confidence=0.9, verdict=AnalysisResult.Verdict.AUTHENTIC)
        r3 = AnalysisResultFactory(submission=sub, analyzer=c3, confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        r4 = AnalysisResultFactory(submission=sub, analyzer=c4, confidence=0.9, verdict=AnalysisResult.Verdict.FAKE)
        score, verdict = aggregate([r1, r2, r3, r4])
        assert verdict == "needs_review"

    def test_all_inconclusive_returns_inconclusive(self):
        config1 = AnalyzerConfigFactory(name="ana_a")
        config2 = AnalyzerConfigFactory(name="ana_b")
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r1 = AnalysisResultFactory(submission=sub, analyzer=config1, confidence=0.5, verdict=AnalysisResult.Verdict.INCONCLUSIVE)
        r2 = AnalysisResultFactory(submission=sub, analyzer=config2, confidence=0.5, verdict=AnalysisResult.Verdict.INCONCLUSIVE)
        score, verdict = aggregate([r1, r2])
        assert verdict == "inconclusive"
        assert score == 0.5

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

    def test_community_forensics_priority_override(self):
        cf_config = AnalyzerConfigFactory(name="community_forensics", weight=3.0)
        npr_config = AnalyzerConfigFactory(name="npr_detector", weight=2.5)
        meta_config = AnalyzerConfigFactory(name="metadata", weight=2.5)
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r_cf = AnalysisResultFactory(
            submission=sub, analyzer=cf_config,
            confidence=0.85, verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 0.95},
        )
        r_npr = AnalysisResultFactory(
            submission=sub, analyzer=npr_config,
            confidence=0.65, verdict=AnalysisResult.Verdict.SUSPICIOUS,
        )
        r_meta = AnalysisResultFactory(
            submission=sub, analyzer=meta_config,
            confidence=0.6, verdict=AnalysisResult.Verdict.AUTHENTIC,
        )
        score, verdict = aggregate([r_cf, r_npr, r_meta])
        assert verdict == "fake"
        assert score >= 0.85

    def test_cf_priority_requires_peer_agreement(self):
        cf_config = AnalyzerConfigFactory(name="community_forensics", weight=3.0)
        meta_config = AnalyzerConfigFactory(name="metadata", weight=2.5)
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r_cf = AnalysisResultFactory(
            submission=sub, analyzer=cf_config,
            confidence=0.85, verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 0.96},
        )
        r_meta = AnalysisResultFactory(
            submission=sub, analyzer=meta_config,
            confidence=0.8, verdict=AnalysisResult.Verdict.AUTHENTIC,
        )
        score, verdict = aggregate([r_cf, r_meta])
        assert verdict != "fake"
