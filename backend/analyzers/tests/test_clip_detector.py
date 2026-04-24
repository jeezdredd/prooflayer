import tempfile
from unittest.mock import patch, MagicMock

import pytest
import torch
from PIL import Image

from analyzers.implementations.clip_detector import AIImageDetector, _model_cache


@pytest.fixture(autouse=True)
def clear_model_cache():
    _model_cache.clear()
    yield
    _model_cache.clear()


@pytest.fixture
def test_image_path():
    img = Image.new("RGB", (224, 224), color="blue")
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


def _make_mock_model(ai_score_high=True):
    mock_model = MagicMock()
    mock_feature_extractor = MagicMock()

    if ai_score_high:
        logits = torch.tensor([[-2.0, 2.0]])
    else:
        logits = torch.tensor([[2.0, -2.0]])

    mock_outputs = MagicMock()
    mock_outputs.logits = logits
    mock_model.return_value = mock_outputs
    mock_model.eval = MagicMock()
    mock_model.config = MagicMock()
    mock_model.config.id2label = {0: "Real", 1: "AI"}

    mock_feature_extractor.return_value = {"pixel_values": torch.randn(1, 3, 224, 224)}

    return mock_model, mock_feature_extractor


@patch("analyzers.implementations.clip_detector.AutoModelForImageClassification")
@patch("analyzers.implementations.clip_detector.AutoFeatureExtractor")
class TestAIImageDetector:
    def test_supported_mime_types(self, mock_extractor_cls, mock_model_cls):
        analyzer = AIImageDetector()
        assert "image/jpeg" in analyzer.supported_mime_types()
        assert "image/png" in analyzer.supported_mime_types()
        assert "image/webp" in analyzer.supported_mime_types()

    def test_analyze_returns_valid_output(self, mock_extractor_cls, mock_model_cls, test_image_path):
        mock_model, mock_fe = _make_mock_model(ai_score_high=True)
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_extractor_cls.from_pretrained.return_value = mock_fe

        analyzer = AIImageDetector()
        output = analyzer.analyze(test_image_path, {})

        assert 0 <= output.confidence <= 1
        assert output.verdict in ("authentic", "suspicious", "fake", "inconclusive")
        assert "ai_probability" in output.evidence
        assert "human_probability" in output.evidence

    def test_high_ai_score_returns_fake(self, mock_extractor_cls, mock_model_cls, test_image_path):
        mock_model, mock_fe = _make_mock_model(ai_score_high=True)
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_extractor_cls.from_pretrained.return_value = mock_fe

        analyzer = AIImageDetector()
        output = analyzer.analyze(test_image_path, {})

        assert output.verdict == "fake"
        assert output.confidence == 0.9

    def test_low_ai_score_returns_authentic(self, mock_extractor_cls, mock_model_cls, test_image_path):
        mock_model, mock_fe = _make_mock_model(ai_score_high=False)
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_extractor_cls.from_pretrained.return_value = mock_fe

        analyzer = AIImageDetector()
        output = analyzer.analyze(test_image_path, {})

        assert output.verdict == "authentic"
        assert output.confidence == 0.8

    def test_model_cached_after_first_call(self, mock_extractor_cls, mock_model_cls, test_image_path):
        mock_model, mock_fe = _make_mock_model()
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_extractor_cls.from_pretrained.return_value = mock_fe

        analyzer = AIImageDetector()
        analyzer.analyze(test_image_path, {})
        analyzer.analyze(test_image_path, {})

        mock_model_cls.from_pretrained.assert_called_once()

    def test_evidence_contains_model_info(self, mock_extractor_cls, mock_model_cls, test_image_path):
        mock_model, mock_fe = _make_mock_model()
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_extractor_cls.from_pretrained.return_value = mock_fe

        analyzer = AIImageDetector()
        output = analyzer.analyze(test_image_path, {})

        assert output.evidence["model"] == "Nahrawy/AIorNot"

    def test_probabilities_sum_to_one(self, mock_extractor_cls, mock_model_cls, test_image_path):
        mock_model, mock_fe = _make_mock_model()
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_extractor_cls.from_pretrained.return_value = mock_fe

        analyzer = AIImageDetector()
        output = analyzer.analyze(test_image_path, {})

        total = output.evidence["ai_probability"] + output.evidence["human_probability"]
        assert abs(total - 1.0) < 0.01
