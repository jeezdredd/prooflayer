import pytest
from PIL import Image

from analyzers.implementations.metadata_analyzer import MetadataAnalyzer

CAMERA_EXIF = {
    "Make": "NIKON CORPORATION",
    "Model": "NIKON D3S",
    "ExposureTime": "1/200",
    "FNumber": 5.6,
    "ISOSpeedRatings": 200,
    "FocalLength": 85,
}


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
        assert result.verdict in ("authentic", "suspicious", "inconclusive")

    def test_camera_photo_edited_later_is_not_suspicious(self, tmp_path):
        path = tmp_path / "press.jpg"
        Image.new("RGB", (100, 100)).save(str(path), format="JPEG")
        exif = {**CAMERA_EXIF, "DateTime": "2014:03:12 10:00:00", "DateTimeOriginal": "2014:03:02 13:54:00"}
        result = self.analyzer.analyze(str(path), {"format": "JPEG", "width": 100, "height": 100, "exif": exif})
        assert "date_inconsistency" in result.evidence["flags"]
        assert "camera_signature" in result.evidence["flags"]
        assert result.evidence["dates"]["details"]
        assert result.verdict == "inconclusive"

    def test_camera_photo_with_ai_tool_still_fake(self, tmp_path):
        path = tmp_path / "gen.jpg"
        Image.new("RGB", (100, 100)).save(str(path), format="JPEG")
        exif = {**CAMERA_EXIF, "Software": "Adobe Firefly", "DateTime": "2024:01:01 12:00:00", "DateTimeOriginal": "2020:06:15 08:30:00"}
        result = self.analyzer.analyze(str(path), {"format": "JPEG", "width": 100, "height": 100, "exif": exif})
        assert result.verdict == "fake"

    def test_camera_photo_with_two_strong_flags_stays_suspicious(self, tmp_path):
        path = tmp_path / "odd.jpg"
        Image.new("RGB", (100, 100)).save(str(path), format="JPEG")
        exif = {**CAMERA_EXIF, "DateTime": "2024:01:01 12:00:00", "DateTimeOriginal": "2020:06:15 08:30:00"}
        self.analyzer._check_gps_plausibility = lambda metadata: {"suspicious": True, "details": "impossible coordinates"}
        result = self.analyzer.analyze(str(path), {"format": "JPEG", "width": 100, "height": 100, "exif": exif})
        assert result.verdict == "suspicious"


LIGHTROOM_XMP = (
    '<x:xmpmeta><rdf:RDF><rdf:Description xmp:CreatorTool="Adobe Photoshop Lightroom Classic 13.0" '
    'aux:ImageNumber="4521" aux:SerialNumber="3021455"/></rdf:RDF></x:xmpmeta>'
)


class TestToolSignatureEvidence:
    def setup_method(self):
        self.analyzer = MetadataAnalyzer()

    def _analyze(self, tmp_path, **metadata):
        path = tmp_path / "photo.png"
        Image.new("RGB", (64, 64)).save(str(path), format="PNG")
        return self.analyzer.analyze(str(path), {"format": "PNG", "width": 64, "height": 64, **metadata})

    def test_lightroom_image_number_is_not_imagen(self, tmp_path):
        result = self._analyze(tmp_path, xmp=LIGHTROOM_XMP)
        assert result.evidence["ai_tool"]["detected"] is False
        assert result.verdict != "fake"

    def test_spanish_description_is_not_a_generator(self, tmp_path):
        xmp = '<rdf:Description><dc:description><rdf:Alt><rdf:li>Una imagen de la playa al atardecer</rdf:li></rdf:Alt></dc:description></rdf:Description>'
        assert self._analyze(tmp_path, xmp=xmp).evidence["ai_tool"]["detected"] is False

    def test_xmp_packet_copied_into_png_text_is_skipped(self, tmp_path):
        result = self._analyze(tmp_path, png_text={"XML:com.adobe.xmp": LIGHTROOM_XMP})
        assert result.evidence["ai_tool"]["detected"] is False

    def test_creator_tool_names_the_generator_with_evidence(self, tmp_path):
        result = self._analyze(tmp_path, xmp='<rdf:Description xmp:CreatorTool="Midjourney v6.1"/>')
        tool = result.evidence["ai_tool"]
        assert tool == {"detected": True, "tool": "midjourney", "field": "xmp:CreatorTool", "raw_value": "Midjourney v6.1"}
        trace = next(t for t in result.evidence["ai_trace"] if t["kind"] == "software_tag")
        assert trace["raw_value"] == "Midjourney v6.1" and trace["field"] == "xmp:CreatorTool"

    def test_word_inside_another_word_is_not_a_match(self, tmp_path):
        result = self._analyze(tmp_path, exif={"Software": "Fluxion Photo Lab"})
        assert result.evidence["ai_tool"]["detected"] is False

    def test_generation_settings_keep_the_prompt(self, tmp_path):
        params = "a red fox in the snow, highly detailed\nNegative prompt: blurry\nSteps: 30, Sampler: Euler a, CFG scale: 7"
        result = self._analyze(tmp_path, png_text={"parameters": params})
        assert result.evidence["generation_params"]["text"] == "a red fox in the snow, highly detailed"
        trace = next(t for t in result.evidence["ai_trace"] if t["kind"] == "generation_params")
        assert trace["text"] == "a red fox in the snow, highly detailed"
