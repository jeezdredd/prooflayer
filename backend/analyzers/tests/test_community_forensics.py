import io
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from analyzers.implementations.community_forensics import CommunityForensicsDetector


@pytest.fixture
def analyzer():
    return CommunityForensicsDetector()


@pytest.fixture
def jpeg_path():
    img = Image.new("RGB", (64, 64), color=(128, 64, 32))
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


def _fake_load(logits_tensor):
    model = MagicMock()
    processor = MagicMock()
    model.return_value = MagicMock(logits=logits_tensor)
    processor.return_value = {"pixel_values": torch.zeros(1, 3, 384, 384)}
    return model, processor


class TestCommunityForensicsDetector:
    def test_supported_mime_types(self, analyzer):
        types = analyzer.supported_mime_types()
        assert "image/jpeg" in types
        assert "image/png" in types
        assert "image/webp" in types

    def test_invalid_path_returns_error(self, analyzer):
        output = analyzer.analyze("/nonexistent/image.jpg", {})
        assert output.verdict == "error"
        assert "error" in output.evidence

    def test_high_ai_prob_returns_fake(self, analyzer, jpeg_path):
        logits = torch.tensor([[0.1, 3.0]])
        with patch("analyzers.implementations.community_forensics._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict in ("fake", "suspicious", "inconclusive", "authentic")
        assert "ai_probability" in output.evidence

    def test_low_ai_prob_returns_authentic(self, analyzer, jpeg_path):
        logits = torch.tensor([[3.0, -2.0]])
        with patch("analyzers.implementations.community_forensics._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict in ("authentic", "inconclusive")
        assert output.evidence["ai_probability"] < 0.5

    def test_scalar_logit_path(self, analyzer, jpeg_path):
        logits = torch.tensor([2.0])
        with patch("analyzers.implementations.community_forensics._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict in ("fake", "suspicious", "inconclusive", "authentic")

    def test_binary_logits_path(self, analyzer, jpeg_path):
        logits = torch.tensor([[0.2, 2.5]])
        with patch("analyzers.implementations.community_forensics._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert 0.0 <= output.evidence["ai_probability"] <= 1.0

    def test_inference_exception_returns_error(self, analyzer, jpeg_path):
        def bad_load():
            raise RuntimeError("CUDA out of memory")
        with patch("analyzers.implementations.community_forensics._load", side_effect=bad_load):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "error"

    def test_output_confidence_in_range(self, analyzer, jpeg_path):
        logits = torch.tensor([[1.0, 1.5]])
        with patch("analyzers.implementations.community_forensics._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert 0.0 <= output.confidence <= 1.0

    def test_evidence_contains_model_name(self, analyzer, jpeg_path):
        logits = torch.tensor([[0.5, 0.5]])
        with patch("analyzers.implementations.community_forensics._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert "model" in output.evidence


from analyzers.implementations.community_forensics import CALIBRATION_KNOTS, calibrate


class TestCalibration:
    def test_endpoints_are_fixed(self):
        assert calibrate(0.0) == 0.0
        assert calibrate(1.0) == 1.0

    def test_knots_are_hit_exactly(self):
        for x, y in CALIBRATION_KNOTS:
            assert calibrate(x) == pytest.approx(y)

    def test_monotone_non_decreasing(self):
        xs = [i / 1000 for i in range(1001)]
        ys = [calibrate(x) for x in xs]
        assert all(b >= a for a, b in zip(ys, ys[1:]))

    def test_real_photo_tail_stays_below_suspicious(self):
        assert calibrate(0.0045) < 0.20
        assert calibrate(0.0009) < 0.05

    def test_fit_anchor_ai_median_maps_to_likely_fake(self):
        assert calibrate(0.50) == pytest.approx(0.75)

    def test_openfake_median_lands_in_suspicious_band(self):
        assert 0.65 <= calibrate(0.32) < 0.85

    def test_inputs_outside_unit_range_are_clamped(self):
        assert calibrate(-3.0) == 0.0
        assert calibrate(7.0) == 1.0

    def test_analyzer_reports_raw_and_calibrated(self, tmp_path):
        from unittest.mock import patch
        from analyzers.implementations import community_forensics as cf
        from PIL import Image

        path = tmp_path / "x.jpg"
        Image.new("RGB", (64, 64), (10, 20, 30)).save(path, format="JPEG")
        with (
            patch.object(cf, "_load", return_value=(object(), object())),
            patch.object(cf, "_score", return_value=0.32),
        ):
            out = cf.CommunityForensicsDetector().analyze(str(path), {})
        assert out.evidence["raw_probability"] == pytest.approx(0.32)
        assert out.evidence["ai_probability"] == pytest.approx(calibrate(0.32), abs=1e-4)
        assert out.verdict == "suspicious"
