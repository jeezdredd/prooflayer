import tempfile

import numpy as np
import pytest
from PIL import Image

from content.services import compute_perceptual_hashes


@pytest.fixture
def jpeg_path():
    img = Image.new("RGB", (128, 128), color="green")
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f, format="JPEG")
    f.close()
    return f.name


class TestPerceptualHashes:
    def test_compute_returns_ints(self, jpeg_path):
        result = compute_perceptual_hashes(jpeg_path)
        assert isinstance(result["phash"], int)
        assert isinstance(result["dhash"], int)

    def test_same_image_same_hash(self, jpeg_path):
        r1 = compute_perceptual_hashes(jpeg_path)
        r2 = compute_perceptual_hashes(jpeg_path)
        assert r1["phash"] == r2["phash"]
        assert r1["dhash"] == r2["dhash"]

    def test_different_images_different_hash(self):
        arr1 = np.zeros((128, 128, 3), dtype=np.uint8)
        arr1[:64, :, 0] = 255
        img1 = Image.fromarray(arr1)
        f1 = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img1.save(f1, format="JPEG")
        f1.close()

        arr2 = np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)
        img2 = Image.fromarray(arr2)
        f2 = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img2.save(f2, format="JPEG")
        f2.close()

        ph1 = compute_perceptual_hashes(f1.name)["phash"]
        ph2 = compute_perceptual_hashes(f2.name)["phash"]
        assert ph1 != ph2

    def test_invalid_file_returns_none(self):
        result = compute_perceptual_hashes("/nonexistent/file.jpg")
        assert result["phash"] is None
        assert result["dhash"] is None

    def test_fits_in_bigint(self, jpeg_path):
        result = compute_perceptual_hashes(jpeg_path)
        assert -(2**63) <= result["phash"] <= 2**63 - 1
        assert -(2**63) <= result["dhash"] <= 2**63 - 1
