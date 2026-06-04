import tempfile
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from analyzers.implementations.npr_detector import NPRDetector, _fake_index


@pytest.fixture
def analyzer():
    return NPRDetector()


@pytest.fixture
def jpeg_path():
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


def _fake_load_logits(real_logit, fake_logit):
    model = MagicMock()
    model.config.label2id = {"REAL": 0, "FAKE": 1}
    logits = torch.tensor([[real_logit, fake_logit]])
    model.return_value = MagicMock(logits=logits)
    processor = MagicMock()
    processor.return_value = {"pixel_values": torch.zeros(1, 3, 224, 224)}
    return model, processor


class TestFakeIndex:
    def test_finds_fake_label(self):
        assert _fake_index({"REAL": 0, "FAKE": 1}) == 1

    def test_finds_ai_label(self):
        assert _fake_index({"real": 0, "ai": 1}) == 1

    def test_defaults_to_1_when_unknown(self):
        assert _fake_index({"classA": 0, "classB": 1}) == 1


class TestNPRDetector:
    def test_supported_mime_types(self, analyzer):
        types = analyzer.supported_mime_types()
        assert "image/jpeg" in types
        assert "image/png" in types

    def test_invalid_path_returns_error(self, analyzer):
        output = analyzer.analyze("/nonexistent/path.jpg", {})
        assert output.verdict == "error"
        assert "error" in output.evidence

    def test_high_fake_prob_returns_fake(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.npr_detector._load", return_value=_fake_load_logits(0.0, 4.0)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "fake"
        assert output.evidence["ai_probability"] >= 0.85

    def test_low_fake_prob_returns_authentic(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.npr_detector._load", return_value=_fake_load_logits(4.0, 0.0)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "authentic"

    def test_mid_prob_returns_inconclusive(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.npr_detector._load", return_value=_fake_load_logits(0.0, 0.0)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "inconclusive"

    def test_suspicious_range(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.npr_detector._load", return_value=_fake_load_logits(0.0, 1.5)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "suspicious"

    def test_evidence_contains_ai_probability(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.npr_detector._load", return_value=_fake_load_logits(1.0, 0.0)):
            output = analyzer.analyze(jpeg_path, {})
        assert "ai_probability" in output.evidence
        assert 0.0 <= output.evidence["ai_probability"] <= 1.0

    def test_inference_error_returns_error_verdict(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.npr_detector._load", side_effect=RuntimeError("model error")):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "error"
