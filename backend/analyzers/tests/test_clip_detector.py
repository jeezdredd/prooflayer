import tempfile
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
import torch
from PIL import Image

from analyzers.implementations.clip_detector import (
    AIImageDetector,
    _ai_prob_from_outputs,
    _model_cache,
    _photographic_score,
)


@pytest.fixture(autouse=True)
def clear_model_cache():
    _model_cache.clear()
    yield
    _model_cache.clear()


@pytest.fixture
def photographic_image_path():
    arr = (np.random.rand(256, 256, 3) * 255).astype("uint8")
    img = Image.fromarray(arr, mode="RGB")
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


@pytest.fixture
def flat_image_path():
    img = Image.new("RGB", (256, 256), color=(120, 120, 120))
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


def _mk_mock_for_label(ai_prob: float, label_real="human", label_ai="artificial"):
    mock_model = MagicMock()
    mock_extractor = MagicMock()
    logits = torch.tensor([[float(np.log(max(1 - ai_prob, 1e-6))), float(np.log(max(ai_prob, 1e-6)))]])
    mock_outputs = MagicMock()
    mock_outputs.logits = logits
    mock_model.return_value = mock_outputs
    mock_model.eval = MagicMock()
    mock_model.config = MagicMock()
    mock_model.config.id2label = {0: label_real, 1: label_ai}
    mock_extractor.return_value = {"pixel_values": torch.randn(1, 3, 224, 224)}
    return mock_model, mock_extractor


class TestPhotographicScore:
    def test_flat_image_marked_non_photographic(self, flat_image_path):
        img = Image.open(flat_image_path)
        score = _photographic_score(img)
        assert score["is_photographic"] is False

    def test_noisy_image_marked_photographic(self, photographic_image_path):
        img = Image.open(photographic_image_path)
        score = _photographic_score(img)
        assert score["is_photographic"] is True


class TestAIProbFromOutputs:
    def test_split_ai_real_keys(self):
        model = MagicMock()
        model.config.id2label = {0: "human", 1: "artificial"}
        probs = torch.tensor([0.2, 0.8])
        result = _ai_prob_from_outputs(model, probs)
        assert abs(result - 0.8) < 1e-3

    def test_unknown_labels_returns_neutral(self):
        model = MagicMock()
        model.config.id2label = {0: "alpha", 1: "beta"}
        probs = torch.tensor([0.5, 0.5])
        assert _ai_prob_from_outputs(model, probs) == 0.5


@patch("analyzers.implementations.clip_detector.AutoModelForImageClassification")
@patch("analyzers.implementations.clip_detector.AutoFeatureExtractor")
class TestAIImageDetector:
    def test_supported_mime_types(self, _ext, _mod):
        a = AIImageDetector()
        assert "image/jpeg" in a.supported_mime_types()
        assert "image/png" in a.supported_mime_types()
        assert "image/webp" in a.supported_mime_types()

    def test_non_photographic_returns_inconclusive(self, mock_ext, mock_mod, flat_image_path):
        out = AIImageDetector().analyze(flat_image_path, {})
        assert out.verdict == "inconclusive"
        assert out.evidence["content_check"]["is_photographic"] is False
        mock_mod.from_pretrained.assert_not_called()

    def test_high_ensemble_returns_fake(self, mock_ext, mock_mod, photographic_image_path):
        m, e = _mk_mock_for_label(ai_prob=0.95)
        mock_mod.from_pretrained.return_value = m
        mock_ext.from_pretrained.return_value = e
        out = AIImageDetector().analyze(photographic_image_path, {})
        assert out.verdict == "fake"
        assert out.evidence["ensemble_size"] == 3

    def test_low_ensemble_returns_authentic(self, mock_ext, mock_mod, photographic_image_path):
        m, e = _mk_mock_for_label(ai_prob=0.05)
        mock_mod.from_pretrained.return_value = m
        mock_ext.from_pretrained.return_value = e
        out = AIImageDetector().analyze(photographic_image_path, {})
        assert out.verdict == "authentic"

    def test_evidence_contains_per_model(self, mock_ext, mock_mod, photographic_image_path):
        m, e = _mk_mock_for_label(ai_prob=0.5)
        mock_mod.from_pretrained.return_value = m
        mock_ext.from_pretrained.return_value = e
        out = AIImageDetector().analyze(photographic_image_path, {})
        assert "models" in out.evidence
        assert len(out.evidence["models"]) == 3
