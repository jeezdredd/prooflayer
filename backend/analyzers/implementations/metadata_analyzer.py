import re
from datetime import datetime

from analyzers.base import AnalysisOutput, BaseAnalyzer

AI_TOOL_SIGNATURES = [
    "stable diffusion",
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
]

EXIF_SOFTWARE_FIELDS = ["Software", "ProcessingSoftware", "Creator", "CreatorTool"]


class MetadataAnalyzer(BaseAnalyzer):
    name = "metadata"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        evidence = {}
        flags = []

        evidence["ai_tool"] = self._check_ai_tool_signatures(metadata)
        if evidence["ai_tool"]["detected"]:
            flags.append("ai_tool_signature")

        evidence["gps"] = self._check_gps_plausibility(metadata)
        if evidence["gps"]["suspicious"]:
            flags.append("gps_inconsistency")

        evidence["dates"] = self._check_date_consistency(metadata)
        if evidence["dates"]["suspicious"]:
            flags.append("date_inconsistency")

        evidence["metadata_presence"] = self._check_metadata_presence(metadata)
        if evidence["metadata_presence"]["stripped"]:
            flags.append("metadata_stripped")

        if "ai_tool_signature" in flags:
            confidence = 0.9
            verdict = "fake"
        elif len(flags) >= 2:
            confidence = 0.7
            verdict = "suspicious"
        elif len(flags) == 1:
            confidence = 0.5
            verdict = "suspicious"
        else:
            confidence = 0.6
            verdict = "authentic"

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
                    result["raw_value"] = value
                    return result

        return result

    def _check_gps_plausibility(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"suspicious": False, "details": None}

        gps_info = exif.get("GPSInfo")
        if not gps_info or not isinstance(gps_info, dict):
            return result

        try:
            lat = gps_info.get(2)
            lon = gps_info.get(4)
            if lat and lon:
                lat_val = self._gps_to_decimal(lat, gps_info.get(1, "N"))
                lon_val = self._gps_to_decimal(lon, gps_info.get(3, "E"))
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

    def _check_metadata_presence(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"stripped": False, "details": None}

        has_format = bool(metadata.get("format"))
        has_dimensions = bool(metadata.get("width") and metadata.get("height"))

        if has_format and has_dimensions and not exif:
            result["stripped"] = True
            result["details"] = "Image has no EXIF data — metadata may have been stripped"

        return result
