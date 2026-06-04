import tempfile
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from analyzers.implementations.siglip_detector import SigLIPDetector, _ai_probability


@pytest.fixture
def analyzer():
    return SigLIPDetector()


@pytest.fixture
def jpeg_path():
    img = Image.new("RGB", (64, 64), color=(200, 100, 50))
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


def _fake_load(logits_2d):
    model = MagicMock()
    model.config.id2label = {0: "Real", 1: "Fake"}
    model.return_value = MagicMock(logits=logits_2d)
    processor = MagicMock()
    processor.return_value = {"pixel_values": torch.zeros(1, 3, 224, 224)}
    return model, processor


class TestAiProbability:
    def test_fake_label_detected(self):
        model = MagicMock()
        model.config.id2label = {0: "Real", 1: "Fake"}
        probs = torch.tensor([0.1, 0.9])
        ai_prob, per_label = _ai_probability(model, probs)
        assert ai_prob == pytest.approx(0.9, abs=0.01)

    def test_real_label_detected(self):
        model = MagicMock()
        model.config.id2label = {0: "Real", 1: "Fake"}
        probs = torch.tensor([0.9, 0.1])
        ai_prob, per_label = _ai_probability(model, probs)
        assert ai_prob == pytest.approx(0.1, abs=0.01)

    def test_unknown_labels_return_half(self):
        model = MagicMock()
        model.config.id2label = {0: "classA", 1: "classB"}
        probs = torch.tensor([0.6, 0.4])
        ai_prob, _ = _ai_probability(model, probs)
        assert ai_prob == pytest.approx(0.5, abs=0.01)

    def test_per_label_dict_returned(self):
        model = MagicMock()
        model.config.id2label = {0: "Real", 1: "Fake"}
        probs = torch.tensor([0.3, 0.7])
        _, per_label = _ai_probability(model, probs)
        assert "Real" in per_label
        assert "Fake" in per_label


class TestSigLIPDetector:
    def test_supported_mime_types(self, analyzer):
        types = analyzer.supported_mime_types()
        assert "image/jpeg" in types
        assert "image/png" in types

    def test_invalid_path_returns_error(self, analyzer):
        output = analyzer.analyze("/nonexistent/image.jpg", {})
        assert output.verdict == "error"
        assert "error" in output.evidence

    def test_high_ai_prob_returns_fake(self, analyzer, jpeg_path):
        logits = torch.tensor([[0.05, 3.5]])
        with patch("analyzers.implementations.siglip_detector._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict in ("fake", "suspicious")

    def test_low_ai_prob_returns_authentic(self, analyzer, jpeg_path):
        logits = torch.tensor([[3.5, 0.05]])
        with patch("analyzers.implementations.siglip_detector._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict in ("authentic", "inconclusive")

    def test_evidence_has_required_keys(self, analyzer, jpeg_path):
        logits = torch.tensor([[1.0, 1.0]])
        with patch("analyzers.implementations.siglip_detector._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert "ai_probability" in output.evidence
        assert "per_label" in output.evidence
        assert "model" in output.evidence

    def test_inference_error_returns_error_verdict(self, analyzer, jpeg_path):
        with patch("analyzers.implementations.siglip_detector._load", side_effect=RuntimeError("oom")):
            output = analyzer.analyze(jpeg_path, {})
        assert output.verdict == "error"

    def test_ai_probability_in_range(self, analyzer, jpeg_path):
        logits = torch.tensor([[0.8, 1.2]])
        with patch("analyzers.implementations.siglip_detector._load", return_value=_fake_load(logits)):
            output = analyzer.analyze(jpeg_path, {})
        assert 0.0 <= output.evidence["ai_probability"] <= 1.0
