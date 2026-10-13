import logging

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.models import AnalysisResult
from analyzers.text.evasion import scan_docx, scan_text
from analyzers.text.grade import assess, level_label
from analyzers.text.language import detect_language
from analyzers.text.style import drift, features, phrasebook
from common.documents import DOCUMENT_MIMES, read_text
from content.models import Submission

logger = logging.getLogger(__name__)

TEXT_LIMIT = 200_000
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
STYLE_HISTORY = 8
CONTEXT_FLAG = 0.6


def _read(file_path: str, metadata: dict) -> str:
    return read_text(file_path, metadata.get("mime_type", "text/plain"), TEXT_LIMIT)


def _submission(metadata: dict):
    submission_id = metadata.get("submission_id")
    if not submission_id:
        return None
    return Submission.objects.select_related("classroom").filter(id=submission_id).first()


class TextEvasionAnalyzer(BaseAnalyzer):
    name = "text_evasion"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            text = _read(file_path, metadata)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        report = scan_text(text)
        if metadata.get("mime_type") == DOCX_MIME:
            report.hidden_runs = scan_docx(file_path)
        strength = report.strength()
        evidence = report.as_evidence()
        if strength < 0.6:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={**evidence, "finding": "no obfuscation"})
        evidence["ai_probability"] = strength
        evidence["finding"] = "text was altered to slip past detectors"
        return AnalysisOutput(confidence=strength, verdict="fake" if strength >= 0.9 else "suspicious", evidence=evidence)


class TextGradeFitAnalyzer(BaseAnalyzer):
    name = "text_grade_fit"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        submission = _submission(metadata)
        level = getattr(getattr(submission, "classroom", None), "level", None)
        if not level:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "class level not set"})
        try:
            text = _read(file_path, metadata)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        lang = detect_language(text)
        if lang is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "language not supported"})
        fit = assess(text, lang, level)
        if fit is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "text too short", "level_label": level_label(level)})
        evidence = {**fit.as_evidence(), "context_signal": True}
        if fit.mismatch >= CONTEXT_FLAG:
            evidence["finding"] = f"vocabulary and sentence complexity well above {level_label(level)}"
            return AnalysisOutput(confidence=fit.mismatch, verdict="suspicious", evidence=evidence)
        evidence["finding"] = f"fits {level_label(level)}"
        return AnalysisOutput(confidence=1 - fit.mismatch, verdict="inconclusive", evidence=evidence)


class TextStyleAnalyzer(BaseAnalyzer):
    name = "text_style"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def _history(self, submission, language: str) -> list[dict]:
        if submission is None or submission.classroom_id is None:
            return []
        rows = (
            AnalysisResult.objects.filter(
                analyzer__name=self.name,
                submission__user_id=submission.user_id,
                submission__classroom__isnull=False,
                submission__created_at__lt=submission.created_at,
            )
            .exclude(submission_id=submission.id)
            .order_by("-submission__created_at")
            .values_list("evidence", flat=True)[: STYLE_HISTORY * 2]
        )
        profiles = [e.get("profile") for e in rows if isinstance(e, dict) and e.get("profile")]
        return [p for p in profiles if p.get("language") == language][:STYLE_HISTORY]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            text = _read(file_path, metadata)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        lang = detect_language(text)
        if lang is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "language not supported"})
        profile = features(text, lang)
        evidence = {"language": lang.code, "phrasebook": phrasebook(text, lang), "context_signal": True}
        if profile is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={**evidence, "reason": "text too short"})
        evidence["profile"] = profile
        try:
            history = self._history(_submission(metadata), lang.code)
        except Exception as exc:
            logger.warning("style history lookup failed: %s", exc)
            history = []
        if len(history) < 2:
            evidence["finding"] = "not enough earlier work from this student to compare"
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
        result = drift(profile, history)
        evidence["drift"] = result
        if result["score"] >= CONTEXT_FLAG:
            evidence["finding"] = "writing style differs sharply from this student's earlier work"
            return AnalysisOutput(confidence=result["score"], verdict="suspicious", evidence=evidence)
        evidence["finding"] = "consistent with this student's earlier work"
        return AnalysisOutput(confidence=1 - result["score"], verdict="inconclusive", evidence=evidence)
