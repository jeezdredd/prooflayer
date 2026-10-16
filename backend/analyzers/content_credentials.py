import json
import logging
import os
from functools import lru_cache

import c2pa

logger = logging.getLogger(__name__)

TRUST_ANCHORS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trust", "c2pa-trust-anchors.pem")

AI_GENERATED_SOURCES = {"trainedAlgorithmicMedia"}
AI_EDITED_SOURCES = {"compositeWithTrainedAlgorithmicMedia", "compositeSynthetic"}
LIBRARY_GENERATORS = ("c2pa-rs", "c2pa-python", "c2pa-js", "c2pa-node", "c2patool")
VALID_STATES = {"Valid", "Trusted"}
REMNANT_SCAN_BYTES = 64 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_APP1 = 0xE1
JPEG_APP11 = 0xEB
JPEG_SOS = 0xDA


@lru_cache(maxsize=1)
def _context() -> c2pa.Context:
    with open(TRUST_ANCHORS_PATH) as fh:
        anchors = fh.read()
    settings = c2pa.Settings.from_dict({"trust": {"trust_anchors": anchors}, "verify": {"verify_trust": True}})
    return c2pa.Context(settings)


def read_manifest(path: str) -> str | None:
    try:
        with c2pa.Reader(path, context=_context()) as reader:
            return reader.json()
    except Exception as exc:
        logger.debug("no readable C2PA manifest in %s: %s", path, exc)
        return None


def _png_remnants(data: bytes) -> bool:
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        if kind == b"caBX":
            return True
        if kind == b"IEND":
            return False
        pos += 12 + length
    return False


def _jpeg_remnants(data: bytes) -> bool:
    pos = 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker == JPEG_SOS:
            return False
        length = int.from_bytes(data[pos + 2:pos + 4], "big")
        segment = data[pos + 4:pos + 2 + length]
        if marker == JPEG_APP11 and (b"jumb" in segment or b"c2pa" in segment):
            return True
        if marker == JPEG_APP1 and segment.startswith(b"http://ns.adobe.com/xap/") and b"c2pa" in segment.lower():
            return True
        pos += 2 + length
    return False


def _webp_remnants(data: bytes) -> bool:
    pos = 12
    while pos + 8 <= len(data):
        kind = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        if kind == b"C2PA":
            return True
        pos += 8 + size + (size & 1)
    return False


def has_remnants(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            data = fh.read(REMNANT_SCAN_BYTES)
    except OSError:
        return False
    if data.startswith(PNG_SIGNATURE):
        return _png_remnants(data)
    if data.startswith(b"\xff\xd8"):
        return _jpeg_remnants(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _webp_remnants(data)
    return False


def _short_source(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.rstrip("/").rsplit("/", 1)[-1]


def _agent_name(agent) -> str | None:
    if isinstance(agent, dict):
        return agent.get("name")
    if isinstance(agent, str):
        return agent
    return None


def _generator(manifest: dict) -> str | None:
    for info in manifest.get("claim_generator_info") or []:
        name = info.get("name") if isinstance(info, dict) else None
        if name and not name.lower().startswith(LIBRARY_GENERATORS):
            return name
    claim = manifest.get("claim_generator")
    if isinstance(claim, str) and claim:
        first = claim.split()[0].split("/")[0]
        if not first.lower().startswith(LIBRARY_GENERATORS):
            return first
    return None


def _actions(manifest: dict) -> list[dict]:
    actions = []
    for assertion in manifest.get("assertions") or []:
        if str(assertion.get("label", "")).startswith("c2pa.actions"):
            actions.extend((assertion.get("data") or {}).get("actions") or [])
    return [a for a in actions if isinstance(a, dict)]


def summarize(manifest_json) -> dict | None:
    try:
        data = json.loads(manifest_json) if isinstance(manifest_json, str) else manifest_json
        manifest = data["manifests"][data["active_manifest"]]
    except (TypeError, ValueError, KeyError):
        return None

    sources = []
    agents = []
    for action in _actions(manifest):
        source = _short_source(action.get("digitalSourceType"))
        if source:
            sources.append(source)
        name = _agent_name(action.get("softwareAgent"))
        if name:
            agents.append(name)

    if any(s in AI_GENERATED_SOURCES for s in sources):
        ai = "generated"
    elif any(s in AI_EDITED_SOURCES for s in sources):
        ai = "edited"
    else:
        ai = None

    problems = [s.get("code") for s in data.get("validation_status") or [] if isinstance(s, dict) and s.get("code")]
    state = data.get("validation_state") or ("Invalid" if any("mismatch" in p for p in problems) else "Valid")
    signature = manifest.get("signature_info") or {}

    return {
        "state": state,
        "trusted": state == "Trusted",
        "intact": state in VALID_STATES,
        "generator": _generator(manifest) or (agents[0] if agents else None),
        "software_agents": agents[:5],
        "signed_by": signature.get("issuer") or signature.get("common_name"),
        "signed_at": signature.get("time"),
        "source_types": sorted(set(sources)),
        "ai": ai,
        "problems": problems[:5],
    }
