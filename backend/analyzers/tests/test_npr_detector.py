import hashlib
from unittest.mock import patch

import pytest
import torch
from PIL import Image
from torch import nn

from analyzers.implementations import npr_detector
from analyzers.implementations.npr_detector import (
    NPRNet,
    NPRDetector,
    ensure_weights,
    npr_residual,
    prepare,
)


@pytest.fixture(autouse=True)
def _reset_model_cache():
    npr_detector._state["model"] = None
    yield
    npr_detector._state["model"] = None


@pytest.fixture
def jpeg_path(tmp_path):
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (64, 64), color=(100, 150, 200)).save(path, format="JPEG")
    return str(path)


class _FixedLogit(nn.Module):
    def __init__(self, logit: float):
        super().__init__()
        self.logit = logit

    def forward(self, x):
        return torch.full((x.shape[0], 1), self.logit)


class TestNprResidual:
    def test_constant_image_has_zero_residual(self):
        x = torch.full((1, 3, 8, 8), 0.42)
        assert float(npr_residual(x).abs().max()) == 0.0

    def test_checkerboard_has_unit_residual(self):
        x = torch.zeros(1, 3, 8, 8)
        x[:, :, ::2, ::2] = 1.0
        assert float(npr_residual(x).abs().max()) == pytest.approx(1.0)

    def test_residual_is_zero_where_2x2_blocks_are_uniform(self):
        x = torch.zeros(1, 3, 4, 4)
        x[:, :, :2, :2] = 1.0
        assert float(npr_residual(x).abs().max()) == 0.0


class TestPrepare:
    def test_odd_dimensions_are_truncated_to_even(self):
        x, info = prepare(Image.new("RGB", (101, 77)))
        assert tuple(x.shape) == (1, 3, 76, 100)
        assert info["cropped"] is True
        assert (info["width"], info["height"]) == (101, 77)

    def test_even_dimensions_pass_through(self):
        x, info = prepare(Image.new("RGB", (64, 48)))
        assert tuple(x.shape) == (1, 3, 48, 64)
        assert info["cropped"] is False

    def test_oversized_image_is_center_cropped_not_resized(self):
        big = Image.new("RGB", (npr_detector.MAX_SIDE + 300, 200))
        x, info = prepare(big)
        assert tuple(x.shape) == (1, 3, 200, npr_detector.MAX_SIDE)
        assert info["cropped"] is True

    def test_normalisation_uses_imagenet_statistics(self):
        x, _ = prepare(Image.new("RGB", (2, 2), color=(255, 255, 255)))
        expected = (1.0 - torch.tensor(npr_detector.IMAGENET_MEAN)) / torch.tensor(npr_detector.IMAGENET_STD)
        assert torch.allclose(x[0, :, 0, 0], expected)


class TestNPRNetStructure:
    def test_matches_released_checkpoint_layout(self):
        keys = set(NPRNet().state_dict())
        assert len(keys) == 146
        assert "conv1.weight" in keys and "fc1.weight" in keys
        assert "layer1.0.downsample.0.weight" in keys
        assert "layer2.3.bn3.running_var" in keys
        assert not any(k.startswith(("layer3", "layer4", "fc.")) for k in keys)

    def test_stem_and_head_shapes(self):
        sd = NPRNet().state_dict()
        assert tuple(sd["conv1.weight"].shape) == (64, 3, 3, 3)
        assert tuple(sd["fc1.weight"].shape) == (1, 512)

    def test_forward_returns_one_logit_at_any_even_resolution(self):
        net = NPRNet().eval()
        with torch.no_grad():
            assert tuple(net(torch.randn(1, 3, 64, 64)).shape) == (1, 1)
            assert tuple(net(torch.randn(2, 3, 96, 128)).shape) == (2, 1)

    def test_round_trips_through_strict_load(self):
        net = NPRNet()
        other = NPRNet()
        other.load_state_dict(net.state_dict(), strict=True)


class TestWeights:
    def test_override_path_skips_download_and_checksum(self, tmp_path, monkeypatch):
        weights = tmp_path / "w.pth"
        weights.write_bytes(b"not a real checkpoint")
        monkeypatch.setenv("NPR_WEIGHTS_PATH", str(weights))
        with patch.object(npr_detector, "_download") as download:
            assert ensure_weights() == str(weights)
        download.assert_not_called()

    def test_checksum_mismatch_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NPR_WEIGHTS_PATH", raising=False)
        monkeypatch.setenv("HF_HOME", str(tmp_path))

        class _Resp:
            def __init__(self):
                self.status_code = 200

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield b"tampered bytes"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with patch.object(npr_detector.requests, "get", return_value=_Resp()):
            with pytest.raises(RuntimeError, match="sha256 mismatch"):
                ensure_weights()
        assert not (tmp_path / npr_detector.WEIGHTS_CACHE_SUBDIR / npr_detector.WEIGHTS_FILENAME).exists()

    def test_matching_checksum_is_accepted(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NPR_WEIGHTS_PATH", raising=False)
        monkeypatch.setenv("HF_HOME", str(tmp_path))
        payload = b"pretend weights"
        monkeypatch.setattr(npr_detector, "WEIGHTS_SHA256", hashlib.sha256(payload).hexdigest())

        class _Resp:
            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield payload

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with patch.object(npr_detector.requests, "get", return_value=_Resp()):
            path = ensure_weights()
        assert open(path, "rb").read() == payload

    def test_cached_file_with_bad_checksum_is_redownloaded(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NPR_WEIGHTS_PATH", raising=False)
        monkeypatch.setenv("HF_HOME", str(tmp_path))
        cache_dir = tmp_path / npr_detector.WEIGHTS_CACHE_SUBDIR
        cache_dir.mkdir()
        (cache_dir / npr_detector.WEIGHTS_FILENAME).write_bytes(b"stale")
        with patch.object(npr_detector, "_download") as download:
            ensure_weights()
        download.assert_called_once()


class TestNPRDetector:
    def test_supported_mime_types(self):
        types = NPRDetector().supported_mime_types()
        assert "image/jpeg" in types and "image/png" in types and "image/webp" in types

    def test_invalid_path_returns_error(self):
        output = NPRDetector().analyze("/nonexistent/path.jpg", {})
        assert output.verdict == "error"
        assert "error" in output.evidence

    @pytest.mark.parametrize(
        ("logit", "verdict", "confidence"),
        [
            (6.0, "fake", 0.8),
            (0.9, "suspicious", 0.6),
            (0.0, "inconclusive", 0.4),
            (-1.0, "authentic", 0.6),
            (-6.0, "authentic", 0.8),
        ],
    )
    def test_verdict_bands(self, jpeg_path, logit, verdict, confidence):
        with patch.object(npr_detector, "_load", return_value=_FixedLogit(logit)):
            output = NPRDetector().analyze(jpeg_path, {})
        assert output.verdict == verdict
        assert output.confidence == confidence
        assert output.evidence["ai_probability"] == pytest.approx(torch.sigmoid(torch.tensor(logit)).item(), abs=1e-4)

    def test_evidence_shape(self, jpeg_path):
        with patch.object(npr_detector, "_load", return_value=_FixedLogit(2.0)):
            output = NPRDetector().analyze(jpeg_path, {})
        assert output.evidence["model"].startswith("NPR")
        assert output.evidence["weights_sha256"] == npr_detector.WEIGHTS_SHA256[:12]
        assert output.evidence["input"]["analysed_width"] == 64
        assert "logit" in output.evidence

    def test_inference_error_returns_error_verdict(self, jpeg_path):
        with patch.object(npr_detector, "_load", side_effect=RuntimeError("model error")):
            output = NPRDetector().analyze(jpeg_path, {})
        assert output.verdict == "error"
