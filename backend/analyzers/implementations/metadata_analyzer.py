import html
import re
from datetime import datetime

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.watermarks import find_known_watermark

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
    "made with google ai",
    "google ai",
    "imagined with ai",
    "meta ai",
    "generative fill",
    "generative ai",
    "ai generated",
    "ai-generated",
]

CREDIT_SIGNATURES = [
    "made with google ai",
    "google ai",
    "imagined with ai",
    "meta ai",
    "generative ai",
    "ai generated",
    "ai-generated",
]


def _signature_patterns(signatures):
    return [(sig, re.compile(rf"(?<![a-z]){re.escape(sig)}(?![a-z])")) for sig in signatures]


TOOL_PATTERNS = _signature_patterns(AI_TOOL_SIGNATURES)
CREDIT_PATTERNS = _signature_patterns(CREDIT_SIGNATURES)

PNG_TOOL_KEYS = {"parameters", "software", "comment", "prompt", "workflow"}
XMP_TOOL_FIELDS = ("xmp:CreatorTool", "xap:CreatorTool", "stEvt:softwareAgent", "tiff:Software")
XMP_CREDIT_FIELDS = ("photoshop:Credit",)
RAW_VALUE_CHARS = 300


def find_signature(value: str, patterns) -> str | None:
    lowered = value.lower()
    for sig, pattern in patterns:
        if pattern.search(lowered):
            return sig
    return None


def xmp_values(xmp: str, field: str) -> list[str]:
    name = re.escape(field)
    pattern = re.compile(rf"{name}\s*=\s*\"([^\"]*)\"|{name}\s*=\s*'([^']*)'|<{name}>([^<]*)</{name}>")
    return [html.unescape(next(g for g in m.groups() if g is not None)).strip() for m in pattern.finditer(xmp)]


def prompt_text(value: str) -> str:
    prompt = re.split(r"\n\s*negative prompt:", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return prompt.strip()[:RAW_VALUE_CHARS]


AI_GENERATED_PATTERN = re.compile(r"(?<!compositewith)trainedalgorithmicmedia")
AI_EDITED_MARKERS = ("compositewithtrainedalgorithmicmedia", "compositesynthetic")

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
DATE_ONLY_FLAGS = {"date_inconsistency"}


def camera_signature(metadata: dict) -> dict:
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


class MetadataAnalyzer(BaseAnalyzer):
    name = "metadata"
    version = "1.9.0"

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
        elif evidence["c2pa"]["ai_edited"]:
            flags.append("c2pa_ai_edited")

        evidence["watermark"] = find_known_watermark(file_path)
        intact_mark = bool(evidence["watermark"]) and evidence["watermark"]["state"] == "intact"
        if intact_mark:
            flags.append("invisible_watermark")
        elif evidence["watermark"]:
            flags.append("damaged_watermark")

        evidence["evasion"] = self._evasion(evidence, metadata)
        proof = intact_mark or (evidence["c2pa"]["ai_declared"] and evidence["c2pa"].get("trusted") is True)
        evidence["provenance_proof"] = proof
        evidence["ai_trace"] = self._ai_trace(evidence)

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

        if proof:
            confidence = 0.98
            verdict = "fake"
        elif "c2pa_ai_declared" in flags:
            confidence = 0.95
            verdict = "fake"
        elif "damaged_watermark" in flags:
            confidence = 0.9
            verdict = "fake"
        elif "ai_tool_signature" in flags or "generation_parameters" in flags:
            confidence = 0.9
            verdict = "fake"
        elif "c2pa_ai_edited" in flags:
            confidence = 0.7
            verdict = "suspicious"
        elif len(strong_flags) >= 2:
            confidence = 0.8
            verdict = "suspicious"
        elif "camera_signature" in flags and len(strong_flags) == 0:
            confidence = 0.55
            verdict = "authentic"
        elif "camera_signature" in flags and set(strong_flags) <= DATE_ONLY_FLAGS:
            confidence = 0.5
            verdict = "inconclusive"
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

    def _tool_candidates(self, metadata: dict):
        exif = metadata.get("exif") or {}
        if isinstance(exif, dict):
            for field in EXIF_SOFTWARE_FIELDS:
                value = exif.get(field)
                if isinstance(value, str):
                    yield field, value, TOOL_PATTERNS
        for key, value in (metadata.get("png_text") or {}).items():
            if isinstance(value, str) and str(key).lower() in PNG_TOOL_KEYS:
                yield f"png_text.{key}", value, TOOL_PATTERNS
        xmp = metadata.get("xmp")
        if isinstance(xmp, str):
            for field in XMP_TOOL_FIELDS:
                for value in xmp_values(xmp, field):
                    yield field, value, TOOL_PATTERNS
            for field in XMP_CREDIT_FIELDS:
                for value in xmp_values(xmp, field):
                    yield field, value, CREDIT_PATTERNS

    def _check_ai_tool_signatures(self, metadata: dict) -> dict:
        for field, value, patterns in self._tool_candidates(metadata):
            sig = find_signature(value, patterns)
            if sig:
                return {"detected": True, "tool": sig, "field": field, "raw_value": value[:RAW_VALUE_CHARS]}
        return {"detected": False, "tool": None, "field": None}

    def _check_generation_params(self, metadata: dict) -> dict:
        result = {"detected": False, "markers": [], "field": None}
        for field, value in (metadata.get("png_text") or {}).items():
            if not isinstance(value, str) or str(field).lower() not in PNG_TOOL_KEYS:
                continue
            lowered = value.lower()
            hits = [m for m in GENERATION_PARAM_MARKERS if m in lowered]
            if len(hits) >= 2:
                result["detected"] = True
                result["markers"] = hits
                result["field"] = f"png_text.{field}"
                result["text"] = prompt_text(value)
                return result
        return result

    def _check_c2pa_ai(self, metadata: dict) -> dict:
        result = {"ai_declared": False, "ai_edited": False, "marker": None, "source": None}
        summary = metadata.get("c2pa_summary")
        if isinstance(summary, dict):
            for key in ("generator", "signed_by", "signed_at", "state", "trusted", "problems"):
                result[key] = summary.get(key)
            result["source"] = "c2pa_manifest"
            if summary.get("ai") == "generated":
                result["ai_declared"] = True
                result["marker"] = "trainedAlgorithmicMedia"
                return result
            if summary.get("ai") == "edited":
                result["ai_edited"] = True
                sources = summary.get("source_types") or []
                result["marker"] = next((s for s in sources if s.lower() in AI_EDITED_MARKERS), None)
                return result

        texts = [("xmp", metadata.get("xmp"))]
        if not isinstance(summary, dict):
            texts.append(("c2pa_manifest", metadata.get("c2pa")))
        for source, text in texts:
            if not text:
                continue
            lowered = str(text).lower()
            if AI_GENERATED_PATTERN.search(lowered):
                result.update(ai_declared=True, marker="trainedAlgorithmicMedia", source=source)
                return result
            edited = next((m for m in AI_EDITED_MARKERS if m in lowered), None)
            if edited:
                result.update(ai_edited=True, marker=edited, source=source)
                return result
        return result

    def _evasion(self, evidence: dict, metadata: dict) -> list[dict]:
        found = []
        mark = evidence["watermark"]
        if mark and mark["state"] == "damaged":
            found.append({
                "kind": "damaged_watermark",
                "generator": mark["name"],
                "vendor": mark["vendor"],
                "match": mark["match"],
            })
        if evidence["c2pa"].get("state") == "Invalid":
            found.append({"kind": "credentials_altered", "generator": evidence["c2pa"].get("generator")})
        if metadata.get("c2pa_remnants"):
            found.append({"kind": "credentials_removed"})
        return found

    def _ai_trace(self, evidence: dict) -> list[dict]:
        trace = []
        c2pa = evidence["c2pa"]
        if c2pa["ai_declared"] or c2pa["ai_edited"]:
            trace.append({
                "kind": "c2pa" if c2pa["source"] == "c2pa_manifest" else "xmp",
                "ai": "generated" if c2pa["ai_declared"] else "edited",
                "generator": c2pa.get("generator"),
                "signed_by": c2pa.get("signed_by"),
                "trusted": c2pa.get("trusted"),
                "state": c2pa.get("state"),
            })
        mark = evidence["watermark"]
        if mark:
            trace.append({
                "kind": "watermark", "ai": "generated", "generator": mark["name"], "signed_by": mark["vendor"],
                "match": mark["match"], "damaged": mark["state"] == "damaged",
            })
        if evidence["ai_tool"]["detected"]:
            tool = evidence["ai_tool"]
            trace.append({
                "kind": "software_tag", "ai": "generated", "generator": tool["tool"], "field": tool["field"],
                "raw_value": tool.get("raw_value", ""),
            })
        if evidence["generation_params"]["detected"]:
            params = evidence["generation_params"]
            trace.append({"kind": "generation_params", "ai": "generated", "field": params["field"], "text": params.get("text", "")})
        return trace

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
        return camera_signature(metadata)

    def _check_metadata_presence(self, metadata: dict) -> dict:
        exif = metadata.get("exif", {})
        result = {"stripped": False, "details": None}

        has_format = bool(metadata.get("format"))
        has_dimensions = bool(metadata.get("width") and metadata.get("height"))

        if has_format and has_dimensions and not exif:
            result["stripped"] = True
            result["details"] = "Image has no EXIF data - metadata may have been stripped"

        return result
