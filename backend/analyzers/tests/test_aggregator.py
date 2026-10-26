import pytest

from analyzers.aggregator import aggregate
from analyzers.models import AnalysisResult
from content.tests.factories import SubmissionFactory

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

    def test_probabilistic_voter_uses_raw_ai_prob(self):
        cf_config = AnalyzerConfigFactory(name="community_forensics", weight=1.0)
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r = AnalysisResultFactory(
            submission=sub, analyzer=cf_config,
            confidence=0.85, verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 0.7},
        )
        score, _ = aggregate([r])
        assert abs(score - 0.7) < 0.001

    def test_mixed_voters_weighted_correctly(self):
        cf_config = AnalyzerConfigFactory(name="community_forensics", weight=3.0)
        ela_config = AnalyzerConfigFactory(name="ela", weight=1.0)
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r_cf = AnalysisResultFactory(
            submission=sub, analyzer=cf_config,
            confidence=0.85, verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 0.8},
        )
        r_ela = AnalysisResultFactory(
            submission=sub, analyzer=ela_config,
            confidence=0.7, verdict=AnalysisResult.Verdict.AUTHENTIC,
            evidence={},
        )
        score, _ = aggregate([r_cf, r_ela])
        expected = (0.8 * 3.0 + 0.0 * 1.0 * 0.7) / (3.0 + 1.0 * 0.7)
        assert abs(score - expected) < 0.005

    def test_priority_override_still_fires_after_refactor(self):
        cf_config = AnalyzerConfigFactory(name="community_forensics", weight=3.0)
        siglip_config = AnalyzerConfigFactory(name="siglip_detector", weight=1.5)
        from content.tests.factories import SubmissionFactory
        sub = SubmissionFactory()
        r_cf = AnalysisResultFactory(
            submission=sub, analyzer=cf_config,
            confidence=0.85, verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 0.94},
        )
        r_siglip = AnalysisResultFactory(
            submission=sub, analyzer=siglip_config,
            confidence=0.65, verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 0.78},
        )
        score, verdict = aggregate([r_cf, r_siglip])
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


def _member(sub, name, weight, verdict, confidence, evidence=None):
    return AnalysisResultFactory(
        submission=sub,
        analyzer=AnalyzerConfigFactory(name=name, weight=weight),
        verdict=verdict,
        confidence=confidence,
        evidence=evidence or {},
    )


@pytest.mark.django_db
class TestRealPhotoRegression:
    def _press_photo(self, metadata_verdict, metadata_confidence):
        sub = SubmissionFactory()
        v = AnalysisResult.Verdict
        return [
            _member(sub, "community_forensics", 3.5, v.AUTHENTIC, 0.65, {"ai_probability": 0.2}),
            _member(sub, "clip_probe", 2.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.3823}),
            _member(sub, "custom_detector", 3.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.4664}),
            _member(sub, "ai_detector", 1.0, v.INCONCLUSIVE, 0.5),
            _member(sub, "ela", 0.75, v.INCONCLUSIVE, 0.5),
            _member(sub, "llm_vision", 1.5, v.INCONCLUSIVE, 0.5),
            _member(sub, "metadata", 1.5, metadata_verdict, metadata_confidence),
        ]

    def test_reported_case_scored_suspicious_before(self):
        _, verdict = aggregate(self._press_photo(AnalysisResult.Verdict.SUSPICIOUS, 0.6))
        assert verdict == "suspicious"

    def test_camera_photo_with_fixed_metadata_is_not_suspicious(self):
        score, verdict = aggregate(self._press_photo(AnalysisResult.Verdict.INCONCLUSIVE, 0.5))
        assert verdict in ("authentic", "inconclusive")
        assert score < 0.4

    def test_lukewarm_scores_without_a_confident_fake_voter_are_not_suspicious(self):
        sub = SubmissionFactory()
        v = AnalysisResult.Verdict
        results = [
            _member(sub, "custom_detector", 3.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.45}),
            _member(sub, "clip_probe", 2.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.42}),
            _member(sub, "community_forensics", 3.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.4}),
        ]
        score, verdict = aggregate(results)
        assert 0.35 <= score < 0.5
        assert verdict == "inconclusive"

    def test_ai_image_still_flagged(self):
        sub = SubmissionFactory()
        v = AnalysisResult.Verdict
        results = [
            _member(sub, "community_forensics", 3.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.55}),
            _member(sub, "custom_detector", 3.5, v.FAKE, 0.8, {"ai_probability": 0.93}),
            _member(sub, "clip_probe", 2.5, v.FAKE, 0.7, {"ai_probability": 0.88}),
            _member(sub, "metadata", 1.5, v.INCONCLUSIVE, 0.4),
        ]
        _, verdict = aggregate(results)
        assert verdict in ("fake", "likely_fake")

    def test_one_confident_fake_voter_keeps_suspicion(self):
        sub = SubmissionFactory()
        v = AnalysisResult.Verdict
        results = [
            _member(sub, "custom_detector", 3.5, v.FAKE, 0.8, {"ai_probability": 0.8}),
            _member(sub, "clip_probe", 2.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.3}),
            _member(sub, "community_forensics", 3.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.3}),
        ]
        _, verdict = aggregate(results)
        assert verdict == "suspicious"


@pytest.mark.django_db
class TestCameraFileVote:
    def _phone(self, level, custom_prob=0.93, extra=(), flags=("camera_signature",), cf_prob=0.0):
        sub = SubmissionFactory()
        v = AnalysisResult.Verdict
        meta = {"camera_file": {"level": level}, "flags": list(flags)}
        return [
            _member(sub, "custom_detector", 3.5, v.FAKE, 0.85, {"ai_probability": custom_prob}),
            _member(sub, "community_forensics", 3.5, v.AUTHENTIC, 0.85, {"ai_probability": cf_prob}),
            _member(sub, "clip_probe", 2.5, v.INCONCLUSIVE, 0.4, {"ai_probability": 0.32}),
            _member(sub, "ai_detector", 1.0, v.INCONCLUSIVE, 0.5, {"ai_probability_avg": 0.46}),
            _member(sub, "metadata", 1.5, v.AUTHENTIC, 0.55, meta),
            *[_member(sub, name, 2.5, v.FAKE, 0.85, {"ai_probability": p}) for name, p in extra],
        ]

    def test_real_iphone_file_with_one_overconfident_detector_is_not_ai(self):
        _, verdict = aggregate(self._phone(3, custom_prob=0.99))
        assert verdict not in ("fake", "likely_fake", "suspicious")

    def test_two_confident_detectors_against_a_camera_file_go_to_review(self):
        _, verdict = aggregate(self._phone(3, extra=(("npr_detector", 0.97), ("siglip_detector", 0.96))))
        assert verdict == "needs_review"

    def test_camera_file_below_level_three_keeps_the_old_rules(self):
        results = self._phone(3, custom_prob=0.99, extra=(("npr_detector", 0.97),), cf_prob=0.6)
        with_vote = aggregate(results)
        results[4].evidence["camera_file"]["level"] = 2
        without_vote = aggregate(results)
        assert without_vote[0] > with_vote[0]
        assert with_vote[1] == "needs_review"
        assert without_vote[1] in ("fake", "likely_fake")

    def test_ai_mark_in_the_file_disables_the_camera_vote(self):
        results = self._phone(3, extra=(("npr_detector", 0.97),), flags=("camera_signature", "damaged_watermark"))
        marked = aggregate(results)
        results[4].evidence["camera_file"]["level"] = 0
        assert aggregate(results) == marked
