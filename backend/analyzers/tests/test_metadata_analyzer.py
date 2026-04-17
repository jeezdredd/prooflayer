import pytest

from analyzers.implementations.metadata_analyzer import MetadataAnalyzer


class TestMetadataAnalyzer:
    def setup_method(self):
        self.analyzer = MetadataAnalyzer()

    def test_supported_mime_types(self):
        types = self.analyzer.supported_mime_types()
        assert "image/jpeg" in types
        assert "image/png" in types
        assert "image/webp" in types

    def test_clean_image_authentic(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (100, 100))
        path = tmp_path / "clean.jpg"
        img.save(str(path), format="JPEG")
        metadata = {"format": "JPEG", "width": 100, "height": 100, "exif": {"Software": "Adobe Photoshop"}}
        result = self.analyzer.analyze(str(path), metadata)
        assert result.verdict == "authentic"
        assert result.confidence > 0

    def test_ai_tool_detected(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (100, 100))
        path = tmp_path / "ai.jpg"
        img.save(str(path), format="JPEG")
        metadata = {
            "format": "JPEG",
            "width": 100,
            "height": 100,
            "exif": {"Software": "Stable Diffusion v1.5"},
        }
        result = self.analyzer.analyze(str(path), metadata)
        assert result.verdict == "fake"
        assert result.confidence >= 0.9
        assert result.evidence["ai_tool"]["detected"] is True

    def test_stripped_metadata(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (100, 100))
        path = tmp_path / "stripped.jpg"
        img.save(str(path), format="JPEG")
        metadata = {"format": "JPEG", "width": 100, "height": 100}
        result = self.analyzer.analyze(str(path), metadata)
        assert "metadata_stripped" in result.evidence["flags"]

    def test_date_inconsistency(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (100, 100))
        path = tmp_path / "dates.jpg"
        img.save(str(path), format="JPEG")
        metadata = {
            "format": "JPEG",
            "width": 100,
            "height": 100,
            "exif": {
                "DateTime": "2024:01:01 12:00:00",
                "DateTimeOriginal": "2020:06:15 08:30:00",
                "Software": "GIMP",
            },
        }
        result = self.analyzer.analyze(str(path), metadata)
        assert "date_inconsistency" in result.evidence["flags"]
        assert result.verdict == "suspicious"

    def test_empty_metadata(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (100, 100))
        path = tmp_path / "empty.jpg"
        img.save(str(path), format="JPEG")
        result = self.analyzer.analyze(str(path), {})
        assert result.verdict in ("authentic", "suspicious")
