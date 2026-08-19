import re
from datetime import datetime

from analyzers.base import AnalysisOutput, BaseAnalyzer

AI_TOOL_SIGNATURES = [
    "stable diffusion",
    "stable-diffusion",
    "sdxl",
    "dall-e",
    "dall·e",
    "midjourney",
    "novelai",
    "artbreeder",
    "deepai",
    "craiyon",
    "adobe firefly",
    "leonardo.ai",
    "playground ai",
    "nightcafe",
    "starryai",
    "wombo",
    "jasper art",
    "canva ai",
    "bing image creator",
    "copilot designer",
    "flux",
    "black forest labs",
    "ideogram",
    "imagen",
    "gemini",
    "nano banana",
    "recraft",
    "seedream",
    "qwen-image",
    "grok",
    "gpt-image",
    "openai",
    "sora",
    "runway",
    "kling",
    "luma",
    "pika",
    "automatic1111",
    "comfyui",
    "invokeai",
    "fooocus",
    "draw things",
    "krea",
    "magnific",
    "generative fill",
    "generative ai",
    "ai generated",
    "ai-generated",
]

C2PA_AI_MARKERS = (
    "trainedalgorithmicmedia",
    "compositewithtrainedalgorithmicmedia",
    "algorithmicmedia",
)

XMP_AI_MARKERS = C2PA_AI_MARKERS + ("digitalsourcetype",)

GENERATION_PARAM_MARKERS = (
    "negative prompt",
    "steps:",
    "sampler:",
    "cfg scale",
    "denoising strength",
    "model hash",
    "clip skip",
    "lora:",
)

EXIF_SOFTWARE_FIELDS = ["Software", "ProcessingSoftware", "Creator", "CreatorTool"]

CAMERA_SIGNATURE_FIELDS = ["Make", "Model"]
CAMERA_CAPTURE_FIELDS = ["ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength", "LensModel", "LensMake"]


class MetadataAnalyzer(BaseAnalyzer):
    name = "metadata"
    version = "1.5.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        evidence = {}
        flags = []

        evidence["ai_tool"] = self._check_ai_tool_signatures(metadata)
        if evidence["ai_tool"]["detected"]:
            flags.append("ai_tool_signature")

        evidence["generation_params"] = self._check_generation_params(metadata)
        if evidence["generation_params"]["detected"]:
            flags.append("generation_parameters")

        evidence["c2pa"] = self._check_c2pa_ai(metadata)
        if evidence["c2pa"]["ai_declared"]:
            flags.append("c2pa_ai_declared")

        evidence["gps"] = self._check_gps_plausibility(metadata)
        if evidence["gps"]["suspicious"]:
            flags.append("gps_inconsistency")

        evidence["dates"] = self._check_date_consistency(metadata)
        if evidence["dates"]["suspicious"]:
            flags.append("date_inconsistency")

        evidence["metadata_presence"] = self._check_metadata_presence(metadata)
        if evidence["metadata_presence"]["stripped"]:
            flags.append("metadata_stripped")

        evidence["camera"] = self._check_camera_signature(metadata)
        if evidence["camera"]["has_camera_signature"]:
            flags.append("camera_signature")

        strong_flags = [f for f in flags if f not in ("metadata_stripped", "camera_signature")]

        if "c2pa_ai_declared" in flags:
            confidence = 0.95
            verdict = "fake"
        elif "ai_tool_signature" in flags or "generation_parameters" in flags:
            confidence = 0.9
            verdict = "fake"
        elif len(strong_flags) >= 2:
            confidence = 0.8
            verdict = "suspicious"
        elif "camera_signature" in flags and len(strong_flags) == 0:
            confidence = 0.55
            verdict = "authentic"
        elif len(strong_flags) == 1 and "metadata_stripped" in flags:
            confidence = 0.55
            verdict = "suspicious"
        elif len(strong_flags) == 1:
            confidence = 0.6
            verdict = "suspicious"
        elif "metadata_stripped" in flags:
            confidence = 0.4
            verdict = "inconclusive"
        elif metadata.get("exif"):
            confidence = 0.7
            verdict = "authentic"
        else:
            confidence = 0.4
            verdict = "inconclusive"

        evidence["flags"] = flags
        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)

    def _check_ai_tool_signatures(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"detected": False, "tool": None, "field": None}

        for field in EXIF_SOFTWARE_FIELDS:
            value = exif.get(field, "")
            if not isinstance(value, str):
                continue
            value_lower = value.lower()
            for sig in AI_TOOL_SIGNATURES:
                if sig in value_lower:
                    result["detected"] = True
                    result["tool"] = sig
                    result["field"] = field
                    result["raw_value"] = value[:300]
                    return result

        for field, value in (metadata.get("png_text") or {}).items():
            if not isinstance(value, str):
                continue
            value_lower = value.lower()
            for sig in AI_TOOL_SIGNATURES:
                if sig in value_lower:
                    result["detected"] = True
                    result["tool"] = sig
                    result["field"] = f"png_text.{field}"
                    result["raw_value"] = value[:300]
                    return result

        xmp = metadata.get("xmp")
        if isinstance(xmp, str):
            xmp_lower = xmp.lower()
            for sig in AI_TOOL_SIGNATURES:
                if sig in xmp_lower:
                    result["detected"] = True
                    result["tool"] = sig
                    result["field"] = "xmp"
                    return result

        return result

    def _check_generation_params(self, metadata: dict) -> dict:
        result = {"detected": False, "markers": [], "field": None}
        for field, value in (metadata.get("png_text") or {}).items():
            if not isinstance(value, str):
                continue
            lowered = value.lower()
            hits = [m for m in GENERATION_PARAM_MARKERS if m in lowered]
            if len(hits) >= 2:
                result["detected"] = True
                result["markers"] = hits
                result["field"] = f"png_text.{field}"
                return result
        return result

    def _check_c2pa_ai(self, metadata: dict) -> dict:
        result = {"ai_declared": False, "marker": None, "source": None}
        xmp = metadata.get("xmp")
        if isinstance(xmp, str):
            lowered = xmp.lower()
            for marker in XMP_AI_MARKERS[:-1]:
                if marker in lowered:
                    result["ai_declared"] = True
                    result["marker"] = marker
                    result["source"] = "xmp"
                    return result

        c2pa = metadata.get("c2pa")
        if c2pa:
            lowered = str(c2pa).lower()
            for marker in C2PA_AI_MARKERS:
                if marker in lowered:
                    result["ai_declared"] = True
                    result["marker"] = marker
                    result["source"] = "c2pa_manifest"
                    return result
        return result

    def _check_gps_plausibility(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"suspicious": False, "details": None}

        gps_info = exif.get("GPSInfo")
        if not gps_info or not isinstance(gps_info, dict):
            return result

        def _tag(key):
            if key in gps_info:
                return gps_info[key]
            return gps_info.get(str(key))

        try:
            lat = _tag(2)
            lon = _tag(4)
            if lat and lon:
                lat_val = self._gps_to_decimal(lat, _tag(1) or "N")
                lon_val = self._gps_to_decimal(lon, _tag(3) or "E")
                if not (-90 <= lat_val <= 90) or not (-180 <= lon_val <= 180):
                    result["suspicious"] = True
                    result["details"] = f"Invalid coordinates: {lat_val}, {lon_val}"
        except Exception:
            pass

        return result

    def _gps_to_decimal(self, coords, ref) -> float:
        if isinstance(coords, (list, tuple)) and len(coords) == 3:
            d, m, s = coords
            decimal = float(d) + float(m) / 60 + float(s) / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal
        return 0.0

    def _check_date_consistency(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"suspicious": False, "details": None}

        date_fields = ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]
        dates = {}

        for field in date_fields:
            raw = exif.get(field)
            if raw and isinstance(raw, str):
                parsed = self._parse_exif_date(raw)
                if parsed:
                    dates[field] = parsed

        if len(dates) >= 2:
            date_values = list(dates.values())
            for i in range(len(date_values)):
                for j in range(i + 1, len(date_values)):
                    diff = abs((date_values[i] - date_values[j]).total_seconds())
                    if diff > 86400:
                        result["suspicious"] = True
                        result["details"] = f"Date fields differ by {diff / 3600:.1f} hours"
                        return result

        return result

    def _parse_exif_date(self, date_str: str):
        patterns = ["%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"]
        for pattern in patterns:
            try:
                return datetime.strptime(date_str.strip(), pattern)
            except ValueError:
                continue
        return None

    def _check_camera_signature(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"has_camera_signature": False, "make": None, "model": None, "capture_fields_present": 0, "details": None}
        if not isinstance(exif, dict) or not exif:
            return result
        make = exif.get("Make")
        model = exif.get("Model")
        if isinstance(make, str):
            result["make"] = make.strip()
        if isinstance(model, str):
            result["model"] = model.strip()
        capture_count = sum(1 for f in CAMERA_CAPTURE_FIELDS if exif.get(f))
        result["capture_fields_present"] = capture_count
        if (result["make"] and result["model"]) and capture_count >= 2:
            result["has_camera_signature"] = True
            result["details"] = f"Camera EXIF present: {result['make']} {result['model']} (+{capture_count} capture fields)"
        return result

    def _check_metadata_presence(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"stripped": False, "details": None}

        has_format = bool(metadata.get("format"))
        has_dimensions = bool(metadata.get("width") and metadata.get("height"))

        if has_format and has_dimensions and not exif:
            result["stripped"] = True
            result["details"] = "Image has no EXIF data - metadata may have been stripped"

        return result
