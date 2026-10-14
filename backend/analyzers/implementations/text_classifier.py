import json
import logging
import os

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.implementations.custom_detector import RETRAIN_MODEL_DIR
from analyzers.text import classifier
from analyzers.text.language import detect_language
from common.documents import DOCUMENT_MIMES, read_text

logger = logging.getLogger(__name__)

TEXT_LIMIT = 200_000
MIN_TOKENS = 120

_state = {"calibration": None, "dir": None}


def model_dir() -> str:
    return os.environ.get("TEXT_CLASSIFIER_DIR") or os.path.join(RETRAIN_MODEL_DIR, "text")


def load_calibration(directory: str | None = None) -> dict | None:
    directory = directory or model_dir()
    if _state["dir"] == directory:
        return _state["calibration"]
    calibration = None
    try:
        with open(os.path.join(directory, "calibration.json")) as fh:
            data = json.load(fh)
        languages = {}
        for code, entry in data["languages"].items():
            knots = [(float(s), float(p)) for s, p in entry["knots"]]
            scores, probs = [s for s, _ in knots], [p for _, p in knots]
            if len(knots) < 2 or scores != sorted(scores) or len(set(scores)) != len(scores):
                raise ValueError(f"knots for {code} are not strictly increasing by score")
            if probs != sorted(probs):
                raise ValueError(f"knots for {code} are not monotone")
            languages[code] = {**entry, "knots": knots}
        calibration = {"base": data.get("base", ""), "languages": languages}
    except FileNotFoundError:
        logger.info("text_classifier: no calibration in %s", directory)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("text_classifier: rejected calibration in %s: %s", directory, exc)
    _state.update(calibration=calibration, dir=directory)
    return calibration


def probability(score: float, knots: list[tuple[float, float]]) -> float:
    if score <= knots[0][0]:
        return knots[0][1]
    for (s0, p0), (s1, p1) in zip(knots, knots[1:]):
        if score <= s1:
            return p0 + (p1 - p0) * (score - s0) / (s1 - s0)
    return knots[-1][1]


class TextClassifierAnalyzer(BaseAnalyzer):
    name = "text_classifier"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        directory = model_dir()
        calibration = load_calibration(directory)
        if calibration is None:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": "text classifier calibration missing"})
        try:
            text = read_text(file_path, metadata.get("mime_type", "text/plain"), TEXT_LIMIT)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        lang = detect_language(text)
        entry = calibration["languages"].get(lang.code) if lang else None
        if entry is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "language not calibrated"})
        try:
            result = classifier.get_classifier(directory).score(text)
        except ValueError:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "text is empty", "language": lang.code})
        except OSError as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"text classifier unavailable: {exc}"})
        threshold, strict = entry.get("threshold_fpr1"), entry.get("threshold_strict")
        evidence = {
            "language": lang.code,
            "classifier_score": round(result.score, 3),
            "tokens": result.tokens,
            "windows": result.windows,
            "threshold": threshold,
            "threshold_strict": strict,
            "model": calibration["base"],
        }
        if result.tokens < MIN_TOKENS:
            evidence["reason"] = "text too short for a verdict"
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
        ai_probability = round(probability(result.score, entry["knots"]), 4)
        evidence["ai_probability"] = ai_probability
        confidence = round(abs(ai_probability - 0.5) * 2, 4)
        if strict is not None and result.score >= strict:
            evidence["finding"] = "writing pattern scores above every human text in calibration"
            return AnalysisOutput(confidence=confidence, verdict="fake", evidence=evidence)
        if threshold is not None and result.score >= threshold:
            evidence["finding"] = "writing pattern matches machine text more closely than 99% of human texts in calibration"
            return AnalysisOutput(confidence=confidence, verdict="suspicious", evidence=evidence)
        if ai_probability >= 0.5:
            evidence["finding"] = "writing pattern leans towards machine text"
            return AnalysisOutput(confidence=confidence, verdict="suspicious", evidence=evidence)
        evidence["finding"] = "writing pattern in the range of human texts"
        return AnalysisOutput(confidence=confidence, verdict="authentic" if ai_probability <= 0.25 else "inconclusive", evidence=evidence)
