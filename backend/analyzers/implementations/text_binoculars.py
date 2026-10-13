import json
import logging
import os

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.text import binoculars
from analyzers.text.language import detect_language
from common.documents import DOCUMENT_MIMES, read_text

logger = logging.getLogger(__name__)

TEXT_LIMIT = 200_000
MIN_TOKENS = 120
CALIBRATION_PATH = os.environ.get(
    "BINOCULARS_CALIBRATION",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "text", "binoculars_calibration.json"),
)

_state = {"calibration": None, "path": None}


def load_calibration(path: str | None = None) -> dict | None:
    path = path or CALIBRATION_PATH
    if _state["path"] == path:
        return _state["calibration"]
    calibration = None
    try:
        with open(path) as fh:
            data = json.load(fh)
        languages = {}
        for code, entry in data["languages"].items():
            knots = [(float(s), float(p)) for s, p in entry["knots"]]
            if len(knots) < 2 or [s for s, _ in knots] != sorted(s for s, _ in knots):
                raise ValueError(f"knots for {code} are not sorted by score")
            if [p for _, p in knots] != sorted((p for _, p in knots), reverse=True):
                raise ValueError(f"knots for {code} are not monotone")
            languages[code] = {**entry, "knots": knots}
        calibration = {"observer": data["observer"], "performer": data["performer"], "languages": languages}
    except FileNotFoundError:
        logger.info("text_binoculars: no calibration at %s", path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("text_binoculars: rejected calibration %s: %s", path, exc)
    _state.update(calibration=calibration, path=path)
    return calibration


def probability(score: float, knots: list[tuple[float, float]]) -> float:
    if score <= knots[0][0]:
        return knots[0][1]
    for (s0, p0), (s1, p1) in zip(knots, knots[1:]):
        if score <= s1:
            return p0 + (p1 - p0) * (score - s0) / (s1 - s0)
    return knots[-1][1]


class TextBinocularsAnalyzer(BaseAnalyzer):
    name = "text_binoculars"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        calibration = load_calibration()
        if calibration is None:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "binoculars calibration missing"})
        try:
            text = read_text(file_path, metadata.get("mime_type", "text/plain"), TEXT_LIMIT)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        lang = detect_language(text)
        entry = calibration["languages"].get(lang.code) if lang else None
        if entry is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "language not calibrated"})
        try:
            scorer = binoculars.get_scorer(calibration["observer"], calibration["performer"])
            result = scorer.score(text)
        except binoculars.BinocularsUnavailable as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        except ValueError:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "text too short", "language": lang.code})
        evidence = {
            "language": lang.code,
            "binoculars_score": round(result.score, 4),
            "tokens": result.tokens,
            "windows": result.windows,
            "threshold": entry.get("threshold_fpr1"),
            "observer": calibration["observer"],
            "performer": calibration["performer"],
        }
        if result.tokens < MIN_TOKENS:
            evidence["reason"] = "text too short for a statistical verdict"
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
        ai_probability = round(probability(result.score, entry["knots"]), 4)
        evidence["ai_probability"] = ai_probability
        confidence = round(abs(ai_probability - 0.5) * 2, 4)
        if entry.get("threshold_fpr1") is not None and result.score < entry["threshold_fpr1"]:
            evidence["finding"] = "word choices are far more predictable than in human writing in this language"
            return AnalysisOutput(confidence=confidence, verdict="fake", evidence=evidence)
        if ai_probability >= 0.5:
            evidence["finding"] = "word choices are more predictable than typical human writing"
            return AnalysisOutput(confidence=confidence, verdict="suspicious", evidence=evidence)
        evidence["finding"] = "predictability in the range of human writing"
        return AnalysisOutput(confidence=confidence, verdict="authentic" if ai_probability <= 0.25 else "inconclusive", evidence=evidence)
