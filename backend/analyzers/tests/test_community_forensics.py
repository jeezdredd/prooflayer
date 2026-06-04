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
