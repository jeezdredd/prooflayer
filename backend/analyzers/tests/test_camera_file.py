import io
import struct

import numpy as np
from PIL import Image

from analyzers import camera_file
from analyzers.implementations.metadata_analyzer import MetadataAnalyzer

WIDTH = 1200
HEIGHT = 900


def scene(width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    rng = np.random.default_rng(7)
    blocks = rng.integers(0, 255, size=(9, 12, 3), dtype=np.uint8)
    return Image.fromarray(blocks).resize((width, height), Image.Resampling.NEAREST)


def jpeg(image: Image.Image, exif: Image.Exif | None = None) -> bytes:
    buf = io.BytesIO()
    if exif is None:
        image.save(buf, format="JPEG", quality=90)
    else:
        image.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


def camera_exif(width: int = WIDTH, height: int = HEIGHT, makernote: bool = True) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 17 Pro Max"
    sub = exif.get_ifd(0x8769)
    if makernote:
        sub[0x927C] = b"Apple iOS\x00" + bytes(400)
    sub[0xA002] = width
    sub[0xA003] = height
    return exif


def mpf_segment(main_size: int, secondary_size: int, secondary_offset: int) -> bytes:
    tiff = b"MM\x00\x2a" + struct.pack(">I", 8)
    ifd = struct.pack(">H", 3)
    ifd += struct.pack(">HHI", 0xB000, 7, 4) + b"0100"
    ifd += struct.pack(">HHII", 0xB001, 4, 1, 2)
    ifd += struct.pack(">HHII", 0xB002, 7, 32, 8 + 2 + 3 * 12 + 4)
    ifd += struct.pack(">I", 0)
    entries = struct.pack(">IIIHH", 0x030000, main_size, 0, 0, 0)
    entries += struct.pack(">IIIHH", 0x000000, secondary_size, secondary_offset, 0, 0)
    payload = b"MPF\x00" + tiff + ifd + entries
    return b"\xff\xe2" + struct.pack(">H", len(payload) + 2) + payload


def mpo(main: bytes, secondary: bytes) -> bytes:
    probe = mpf_segment(0, 0, 0)
    size = len(main) + len(probe)
    base = 2 + 8
    segment = mpf_segment(size, len(secondary), size - base)
    return main[:2] + segment + main[2:] + secondary


def write(tmp_path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def gain_map(image: Image.Image) -> bytes:
    return jpeg(image.convert("L").resize((image.width // 2, image.height // 2)).convert("RGB"))


def noise_map(width: int, height: int) -> bytes:
    rng = np.random.default_rng(3)
    return jpeg(Image.fromarray(rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)))


class TestInspect:
    def test_phone_file_with_matching_gain_map_is_level_three(self, tmp_path):
        image = scene()
        path = write(tmp_path, "phone.jpg", mpo(jpeg(image, camera_exif()), gain_map(image)))
        structure = camera_file.inspect(path)
        assert structure["mpo"] is True
        assert structure["makernote"] is True
        assert structure["gainmap"] == "aligned"
        assert camera_file.camera_level(structure, True) == 3

    def test_gain_map_from_another_picture_does_not_count(self, tmp_path):
        image = scene()
        path = write(tmp_path, "forged.jpg", mpo(jpeg(image, camera_exif()), noise_map(WIDTH // 2, HEIGHT // 2)))
        structure = camera_file.inspect(path)
        assert structure["gainmap"] == "misaligned"
        assert camera_file.camera_level(structure, True) == 2

    def test_gain_map_with_another_shape_is_misaligned(self, tmp_path):
        image = scene()
        other = scene(800, 800)
        path = write(tmp_path, "shape.jpg", mpo(jpeg(image, camera_exif()), gain_map(other)))
        assert camera_file.inspect(path)["gainmap"] == "misaligned"

    def test_flat_gain_map_does_not_count(self, tmp_path):
        image = scene()
        flat = jpeg(Image.new("RGB", (WIDTH // 2, HEIGHT // 2), (128, 128, 128)))
        path = write(tmp_path, "flat.jpg", mpo(jpeg(image, camera_exif()), flat))
        assert camera_file.inspect(path)["gainmap"] == "flat"

    def test_exif_dimensions_of_another_picture_block_level_three(self, tmp_path):
        image = scene()
        path = write(tmp_path, "dims.jpg", mpo(jpeg(image, camera_exif(4032, 3024)), gain_map(image)))
        structure = camera_file.inspect(path)
        assert structure["dims_ok"] is False
        assert camera_file.camera_level(structure, True) == 1

    def test_without_camera_exif_the_level_is_zero(self, tmp_path):
        image = scene()
        path = write(tmp_path, "plain.jpg", mpo(jpeg(image, camera_exif()), gain_map(image)))
        assert camera_file.camera_level(camera_file.inspect(path), False) == 0

    def test_plain_jpeg_without_makernote_is_level_one(self, tmp_path):
        path = write(tmp_path, "single.jpg", jpeg(scene(), camera_exif(makernote=False)))
        structure = camera_file.inspect(path)
        assert structure["mpo"] is False
        assert structure["gainmap"] == "none"
        assert camera_file.camera_level(structure, True) == 1

    def test_png_is_not_inspected(self, tmp_path):
        path = tmp_path / "picture.png"
        scene().save(path, format="PNG")
        assert camera_file.inspect(str(path)) is None


class TestMetadataEvidence:
    def test_metadata_reports_the_camera_file_level(self, tmp_path):
        image = scene()
        path = write(tmp_path, "phone.jpg", mpo(jpeg(image, camera_exif()), gain_map(image)))
        metadata = {"exif": {"Make": "Apple", "Model": "iPhone 17 Pro Max", "DateTimeOriginal": "2026:10:26 10:00:00", "FNumber": 1.8, "ExposureTime": 0.01, "ISOSpeedRatings": 100}}
        result = MetadataAnalyzer().analyze(path, metadata)
        assert result.evidence["camera"]["has_camera_signature"] is True
        assert result.evidence["camera_file"]["level"] == 3
