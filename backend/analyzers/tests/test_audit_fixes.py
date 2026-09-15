import io

import pytest
from PIL import Image

from analyzers.aggregator import _has_manipulation_signal, aggregate
from analyzers.implementations.ela_analyzer import ELAAnalyzer
from analyzers.implementations.metadata_analyzer import MetadataAnalyzer
from analyzers.implementations.video_analyzer import _frame_positions
from analyzers.models import AnalysisResult
from content.services import extract_metadata
from content.tests.factories import SubmissionFactory

from .factories import AnalysisResultFactory, AnalyzerConfigFactory


@pytest.mark.django_db
class TestAggregatorProbabilitySourcing:
    def test_verdict_only_analyzer_still_carries_weight(self):
        vision = AnalyzerConfigFactory(name="llm_vision", weight=2.0)
        sub = SubmissionFactory()
        result = AnalysisResultFactory(
            submission=sub,
            analyzer=vision,
            confidence=0.6,
            verdict=AnalysisResult.Verdict.FAKE,
            evidence={"llm_verdict": "ai_generated", "reasoning": "six fingers on left hand"},
        )
        score, _ = aggregate([result])
        assert score == pytest.approx(1.0)

    def test_average_probability_key_is_used(self):
        detector = AnalyzerConfigFactory(name="ai_detector", weight=1.0)
        sub = SubmissionFactory()
        result = AnalysisResultFactory(
            submission=sub,
            analyzer=detector,
            confidence=0.4,
            verdict=AnalysisResult.Verdict.INCONCLUSIVE,
            evidence={"ai_probability_avg": 0.62},
        )
        score, _ = aggregate([result])
        assert score == pytest.approx(0.62, abs=1e-3)

    def test_non_numeric_probability_falls_back_to_verdict(self):
        detector = AnalyzerConfigFactory(name="custom_detector", weight=1.0)
        sub = SubmissionFactory()
        result = AnalysisResultFactory(
            submission=sub,
            analyzer=detector,
            confidence=0.8,
            verdict=AnalysisResult.Verdict.AUTHENTIC,
            evidence={"ai_probability": "not-a-number"},
        )
        score, verdict = aggregate([result])
        assert score == pytest.approx(0.0)
        assert verdict == "authentic"

    def test_probability_is_clamped_to_unit_range(self):
        detector = AnalyzerConfigFactory(name="community_forensics", weight=1.0)
        sub = SubmissionFactory()
        result = AnalysisResultFactory(
            submission=sub,
            analyzer=detector,
            confidence=0.9,
            verdict=AnalysisResult.Verdict.FAKE,
            evidence={"ai_probability": 1.8},
        )
        score, _ = aggregate([result])
        assert score == pytest.approx(1.0)


class TestVideoFrameSampling:
    def test_samples_spread_across_whole_video(self):
        positions = _frame_positions(3000)
        assert len(positions) == 8
        assert positions[0] == 0
        assert positions[-1] > 2000

    def test_short_video_returns_every_frame(self):
        assert _frame_positions(5) == [0, 1, 2, 3, 4]

    def test_empty_video_returns_nothing(self):
        assert _frame_positions(0) == []


class TestMetadataGenerationSignals:
    def test_comfyui_png_parameters_flag_as_fake(self):
        metadata = {
            "format": "PNG",
            "width": 1024,
            "height": 1024,
            "png_text": {
                "parameters": "a cat, Negative prompt: blurry, Steps: 30, Sampler: DPM++ 2M, CFG scale: 7",
            },
        }
        output = MetadataAnalyzer().analyze("unused.png", metadata)
        assert output.verdict == "fake"
        assert "generation_parameters" in output.evidence["flags"]

    def test_c2pa_trained_algorithmic_media_flags_as_fake(self):
        metadata = {
            "format": "JPEG",
            "width": 800,
            "height": 600,
            "c2pa": '{"assertions":[{"label":"c2pa.actions","data":{"digitalSourceType":'
                    '"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"}}]}',
        }
        output = MetadataAnalyzer().analyze("unused.jpg", metadata)
        assert output.verdict == "fake"
        assert "c2pa_ai_declared" in output.evidence["flags"]

    def test_modern_generator_name_in_exif_detected(self):
        metadata = {"format": "PNG", "width": 512, "height": 512, "exif": {"Software": "FLUX.1-dev"}}
        output = MetadataAnalyzer().analyze("unused.png", metadata)
        assert output.evidence["ai_tool"]["detected"] is True

    def test_camera_exif_alone_is_not_strong_authentic(self):
        metadata = {
            "format": "JPEG",
            "width": 4000,
            "height": 3000,
            "exif": {
                "Make": "Canon",
                "Model": "EOS R6",
                "ExposureTime": 0.004,
                "FNumber": 2.8,
            },
        }
        output = MetadataAnalyzer().analyze("unused.jpg", metadata)
        assert output.verdict == "authentic"
        assert output.confidence <= 0.6

    def test_string_keyed_gps_is_still_parsed(self):
        metadata = {
            "format": "JPEG",
            "width": 100,
            "height": 100,
            "exif": {"GPSInfo": {"1": "N", "2": (200.0, 0.0, 0.0), "3": "E", "4": (10.0, 0.0, 0.0)}},
        }
        output = MetadataAnalyzer().analyze("unused.jpg", metadata)
        assert output.evidence["gps"]["suspicious"] is True


class TestExifSubIfdExtraction:
    def test_capture_fields_from_exif_ifd_are_extracted(self, tmp_path):
        img = Image.new("RGB", (64, 64), (10, 120, 200))
        exif = img.getexif()
        exif[0x010F] = "Canon"
        exif[0x0110] = "EOS R6"
        sub_ifd = exif.get_ifd(0x8769)
        sub_ifd[0x829A] = (1, 250)
        sub_ifd[0x829D] = (28, 10)
        sub_ifd[0x8827] = 400

        path = tmp_path / "camera.jpg"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif.tobytes())
        path.write_bytes(buf.getvalue())

        metadata = extract_metadata(str(path))
        assert metadata["exif"]["Make"] == "Canon"
        assert "ExposureTime" in metadata["exif"]
        assert "FNumber" in metadata["exif"]

        output = MetadataAnalyzer().analyze(str(path), metadata)
        assert output.evidence["camera"]["has_camera_signature"] is True
        assert output.evidence["camera"]["capture_fields_present"] >= 2


def _jpeg(tmp_path, name, builder):
    img = builder()
    path = tmp_path / name
    img.save(path, format="JPEG", quality=92)
    return str(path)


class TestElaDoesNotVoteOnAiAxis:
    """ELA measures recompression locality, not synthesis.

    Measured on 60 flickr photos vs 60 diffusiondb images, the old thresholds called
    38/60 real photos fake-or-suspicious but only 12/60 AI images - anti-correlated with
    the thing it was being weighted for.
    """

    def test_flat_image_is_inconclusive(self, tmp_path):
        import numpy as np

        path = _jpeg(tmp_path, "flat.jpg", lambda: Image.new("RGB", (256, 256), (120, 120, 120)))
        output = ELAAnalyzer().analyze(path, {})
        assert output.verdict == "inconclusive"
        assert np is not None

    def test_noisy_image_is_inconclusive(self, tmp_path):
        import numpy as np

        rng = np.random.default_rng(7)
        arr = rng.integers(0, 255, (256, 256, 3), dtype=np.uint8)
        path = _jpeg(tmp_path, "noise.jpg", lambda: Image.fromarray(arr))
        output = ELAAnalyzer().analyze(path, {})
        assert output.verdict == "inconclusive"

    def test_evidence_exposes_manipulation_channel(self, tmp_path):
        path = _jpeg(tmp_path, "plain.jpg", lambda: Image.new("RGB", (256, 256), (40, 90, 160)))
        output = ELAAnalyzer().analyze(path, {})
        assert "manipulation_suspected" in output.evidence
        assert "block_outlier_ratio" in output.evidence


@pytest.mark.django_db
class TestManipulationSignalSourcing:
    def test_evidence_flag_drives_authentic_edited(self):
        ela = AnalyzerConfigFactory(name="ela", weight=0.75)
        sub = SubmissionFactory()
        result = AnalysisResultFactory(
            submission=sub,
            analyzer=ela,
            confidence=0.5,
            verdict=AnalysisResult.Verdict.INCONCLUSIVE,
            evidence={"manipulation_suspected": True},
        )
        assert _has_manipulation_signal([result]) is True

    def test_clean_ela_raises_no_manipulation_signal(self):
        ela = AnalyzerConfigFactory(name="ela", weight=0.75)
        sub = SubmissionFactory()
        result = AnalysisResultFactory(
            submission=sub,
            analyzer=ela,
            confidence=0.5,
            verdict=AnalysisResult.Verdict.INCONCLUSIVE,
            evidence={"manipulation_suspected": False},
        )
        assert _has_manipulation_signal([result]) is False

    def test_inconclusive_ela_carries_no_weight_in_score(self):
        cf = AnalyzerConfigFactory(name="community_forensics", weight=3.5)
        ela = AnalyzerConfigFactory(name="ela", weight=0.75)
        sub = SubmissionFactory()
        r_cf = AnalysisResultFactory(
            submission=sub, analyzer=cf, confidence=0.85,
            verdict=AnalysisResult.Verdict.FAKE, evidence={"ai_probability": 0.9},
        )
        r_ela = AnalysisResultFactory(
            submission=sub, analyzer=ela, confidence=0.5,
            verdict=AnalysisResult.Verdict.INCONCLUSIVE,
            evidence={"manipulation_suspected": False},
        )
        score, _ = aggregate([r_cf, r_ela])
        assert score == pytest.approx(0.9, abs=1e-3)


@pytest.mark.django_db
class TestWeightedDisagreement:
    def _results(self, spec):
        sub = SubmissionFactory()
        out = []
        for name, weight, verdict, prob in spec:
            cfg = AnalyzerConfigFactory(name=name, weight=weight)
            evidence = {"ai_probability": prob} if prob is not None else {}
            out.append(AnalysisResultFactory(
                submission=sub, analyzer=cfg, confidence=0.85, verdict=verdict, evidence=evidence,
            ))
        return out

    def test_two_light_dissenters_cannot_force_review_against_heavy_consensus(self):
        results = self._results([
            ("community_forensics", 3.5, AnalysisResult.Verdict.FAKE, 0.99),
            ("custom_detector", 1.5, AnalysisResult.Verdict.FAKE, 0.98),
            ("ai_detector", 1.5, AnalysisResult.Verdict.FAKE, 0.97),
            ("npr_detector", 1.0, AnalysisResult.Verdict.AUTHENTIC, 0.001),
            ("face_deepfake_detector", 0.5, AnalysisResult.Verdict.AUTHENTIC, 0.02),
        ])
        score, verdict = aggregate(results)
        assert verdict == "fake"
        assert score > 0.7

    def test_balanced_weight_split_still_flags_review(self):
        results = self._results([
            ("a", 2.0, AnalysisResult.Verdict.FAKE, 0.95),
            ("b", 2.0, AnalysisResult.Verdict.FAKE, 0.95),
            ("c", 2.0, AnalysisResult.Verdict.AUTHENTIC, 0.05),
            ("d", 2.0, AnalysisResult.Verdict.AUTHENTIC, 0.05),
        ])
        _, verdict = aggregate(results)
        assert verdict == "needs_review"

    def test_minority_at_threshold_share_flags_review(self):
        results = self._results([
            ("a", 3.5, AnalysisResult.Verdict.FAKE, 0.95),
            ("b", 1.5, AnalysisResult.Verdict.FAKE, 0.95),
            ("c", 1.5, AnalysisResult.Verdict.AUTHENTIC, 0.05),
            ("d", 1.0, AnalysisResult.Verdict.AUTHENTIC, 0.05),
        ])
        _, verdict = aggregate(results)
        assert verdict == "needs_review"

    def test_single_dissenter_is_never_review(self):
        results = self._results([
            ("a", 1.0, AnalysisResult.Verdict.FAKE, 0.95),
            ("b", 1.0, AnalysisResult.Verdict.FAKE, 0.95),
            ("c", 5.0, AnalysisResult.Verdict.AUTHENTIC, 0.05),
        ])
        _, verdict = aggregate(results)
        assert verdict != "needs_review"


class TestRetrainedProvenance:
    def test_training_meta_is_read_and_trimmed(self, tmp_path):
        import json as _json

        from analyzers.implementations.custom_detector import training_meta

        (tmp_path / "training_meta.json").write_text(_json.dumps({
            "base_model": "buildborderless/CommunityForensics-DeepfakeDet-ViT",
            "trained_at": "2026-09-04T15:54:10+00:00",
            "epochs": 3,
            "train_counts": {"Real": 362, "AI": 660},
            "sources": ["flux.2-klein-9b", "sora-2", "flickr"],
            "eval_accuracy": 1.0,
            "secret_internal_field": "dropped",
        }))
        meta = training_meta(str(tmp_path))
        assert meta["base_model"].endswith("DeepfakeDet-ViT")
        assert meta["sources"] == 3
        assert meta["train_counts"] == {"Real": 362, "AI": 660}
        assert "secret_internal_field" not in meta

    def test_missing_or_corrupt_meta_is_empty(self, tmp_path):
        from analyzers.implementations.custom_detector import training_meta

        assert training_meta(str(tmp_path)) == {}
        (tmp_path / "training_meta.json").write_text("{not json")
        assert training_meta(str(tmp_path)) == {}


@pytest.mark.django_db
class TestSingleDominantVoter:
    def _results(self, spec):
        sub = SubmissionFactory()
        out = []
        for name, weight, verdict, prob in spec:
            cfg = AnalyzerConfigFactory(name=name, weight=weight)
            out.append(AnalysisResultFactory(
                submission=sub, analyzer=cfg, confidence=0.85, verdict=verdict,
                evidence={"ai_probability": prob} if prob is not None else {},
            ))
        return out

    def test_dominant_near_certain_voter_convicts_alone(self):
        results = self._results([
            ("custom_detector", 3.5, AnalysisResult.Verdict.FAKE, 0.98),
            ("community_forensics", 3.0, AnalysisResult.Verdict.INCONCLUSIVE, 0.45),
            ("ai_detector", 1.0, AnalysisResult.Verdict.INCONCLUSIVE, 0.6),
        ])
        score, verdict = aggregate(results)
        assert verdict in ("fake", "likely_fake")
        assert score > 0.6

    def test_dominant_but_not_certain_is_downgraded(self):
        results = self._results([
            ("custom_detector", 3.5, AnalysisResult.Verdict.FAKE, 0.85),
            ("community_forensics", 3.0, AnalysisResult.Verdict.INCONCLUSIVE, 0.45),
            ("ai_detector", 1.0, AnalysisResult.Verdict.INCONCLUSIVE, 0.6),
        ])
        _, verdict = aggregate(results)
        assert verdict not in ("fake", "likely_fake")

    def test_minority_share_cannot_convict_alone(self):
        results = self._results([
            ("custom_detector", 1.5, AnalysisResult.Verdict.FAKE, 0.99),
            ("community_forensics", 3.5, AnalysisResult.Verdict.AUTHENTIC, 0.1),
            ("ai_detector", 1.5, AnalysisResult.Verdict.INCONCLUSIVE, 0.6),
        ])
        _, verdict = aggregate(results)
        assert verdict not in ("fake", "likely_fake")

    def test_exact_half_share_counts_as_dominant(self):
        results = self._results([
            ("custom_detector", 3.5, AnalysisResult.Verdict.FAKE, 0.95),
            ("community_forensics", 3.5, AnalysisResult.Verdict.AUTHENTIC, 0.2),
        ])
        score, verdict = aggregate(results)
        assert (verdict in ("fake", "likely_fake")) == (score >= 0.6)

    def test_two_voters_path_unchanged(self):
        results = self._results([
            ("a", 1.0, AnalysisResult.Verdict.FAKE, 0.95),
            ("b", 1.0, AnalysisResult.Verdict.FAKE, 0.95),
        ])
        _, verdict = aggregate(results)
        assert verdict == "fake"


class TestCustomDetectorCalibration:
    def test_missing_file_means_raw(self, tmp_path):
        from analyzers.implementations.custom_detector import apply_calibration, load_calibration

        assert load_calibration(str(tmp_path)) is None
        assert apply_calibration(0.42, None) == 0.42

    def test_knots_are_loaded_and_applied(self, tmp_path):
        import json as _json

        from analyzers.implementations.custom_detector import apply_calibration, load_calibration

        (tmp_path / "calibration.json").write_text(_json.dumps({"knots": [[0, 0], [0.5, 0.2], [1, 1]]}))
        knots = load_calibration(str(tmp_path))
        assert knots == [(0.0, 0.0), (0.5, 0.2), (1.0, 1.0)]
        assert apply_calibration(0.5, knots) == pytest.approx(0.2)
        assert apply_calibration(0.75, knots) == pytest.approx(0.6)
        assert apply_calibration(0.0, knots) == 0.0 and apply_calibration(1.0, knots) == 1.0

    @pytest.mark.parametrize("bad", ['{"knots": [[0.1, 0], [1, 1]]}', '{"knots": [[0, 0], [0.9, 0.5], [0.5, 0.6], [1, 1]]}', '{"knots": [[0, 0]]}', "{not json", '{"nope": 1}'])
    def test_invalid_knots_are_rejected(self, tmp_path, bad):
        from analyzers.implementations.custom_detector import load_calibration

        (tmp_path / "calibration.json").write_text(bad)
        assert load_calibration(str(tmp_path)) is None
