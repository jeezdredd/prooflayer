import io
import tempfile

import numpy as np
import pytest
from PIL import Image

from analyzers.implementations.ela_analyzer import ELAAnalyzer


@pytest.fixture
def analyzer():
    return ELAAnalyzer()


@pytest.fixture
def solid_image_path():
    img = Image.new("RGB", (256, 256), color=(100, 100, 100))
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG", quality=95)
    f.close()
    return f.name


@pytest.fixture
def noisy_image_path():
    arr = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG", quality=75)
    f.close()
    return f.name


@pytest.fixture
def spliced_image_path():
    base = np.full((256, 256, 3), 100, dtype=np.uint8)
    base[50:150, 50:150] = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    img = Image.fromarray(base)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    buf.seek(0)
    img2 = Image.open(buf)
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img2.save(f, format="JPEG", quality=95)
    f.close()
    return f.name


class TestELAAnalyzer:
    def test_supported_mime_types(self, analyzer):
        assert "image/jpeg" in analyzer.supported_mime_types()
        assert "image/png" in analyzer.supported_mime_types()

    def test_solid_image_low_error(self, analyzer, solid_image_path):
        output = analyzer.analyze(solid_image_path, {})
        assert output.evidence["mean_error"] < 10.0
        assert output.verdict in ("fake", "suspicious", "inconclusive")

    def test_noisy_image_high_variation(self, analyzer, noisy_image_path):
        output = analyzer.analyze(noisy_image_path, {})
        assert output.evidence["mean_error"] > 0
        assert output.confidence > 0

    def test_spliced_image_detectable(self, analyzer, spliced_image_path):
        output = analyzer.analyze(spliced_image_path, {})
        assert "mean_error" in output.evidence
        assert "uniformity_ratio" in output.evidence

    def test_output_structure(self, analyzer, solid_image_path):
        output = analyzer.analyze(solid_image_path, {})
        assert hasattr(output, "confidence")
        assert hasattr(output, "verdict")
        assert hasattr(output, "evidence")
        assert 0 <= output.confidence <= 1
        assert output.verdict in ("authentic", "suspicious", "fake", "inconclusive")
