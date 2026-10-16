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


@lru_cache(maxsize=1)
def _context() -> c2pa.Context:
    with open(TRUST_ANCHORS_PATH) as fh:
        anchors = fh.read()
    return c2pa.Context(c2pa.Settings.from_dict({"trust": {"trust_anchors": anchors}, "verify": {"verify_trust": True}}))


def read_manifest(path: str) -> str | None:
    try:
        with c2pa.Reader(path, context=_context()) as reader:
            return reader.json()
    except Exception as exc:
        logger.debug("no readable C2PA manifest in %s: %s", path, exc)
        return None


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
