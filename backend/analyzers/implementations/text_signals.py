import logging
from statistics import median

from analyzers.base import AnalysisOutput, BaseAnalyzer
from analyzers.models import AnalysisResult
from analyzers.text.citation_style import check_format
from analyzers.text.citations import check_citations
from analyzers.text.evasion import scan_docx, scan_text
from analyzers.text.genre import detect_genre
from analyzers.text.grade import assess, level_label
from analyzers.text.language import detect_language
from classroom.shadow import active_answers, best_match
from analyzers.text.style import drift, features, phrasebook
from common.documents import DOCUMENT_MIMES, read_text
from content.models import Submission

logger = logging.getLogger(__name__)

TEXT_LIMIT = 200_000
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
STYLE_HISTORY = 8
CONTEXT_FLAG = 0.6
BASELINE_WORKS = 3
PERSONAL_JUMP = 0.3


def _read(file_path: str, metadata: dict) -> str:
    return read_text(file_path, metadata.get("mime_type", "text/plain"), TEXT_LIMIT)


def _submission(metadata: dict):
    submission_id = metadata.get("submission_id")
    if not submission_id:
        return None
    return Submission.objects.select_related("classroom").filter(id=submission_id).first()


def student_evidence(name: str, submission, limit: int = STYLE_HISTORY * 2) -> list[dict]:
    if submission is None or submission.classroom_id is None:
        return []
    rows = (
        AnalysisResult.objects.filter(
            analyzer__name=name,
            submission__user_id=submission.user_id,
            submission__classroom__isnull=False,
            submission__created_at__lt=submission.created_at,
        )
        .exclude(submission_id=submission.id)
        .order_by("-submission__created_at")
        .values_list("evidence", flat=True)[:limit]
    )
    return [e for e in rows if isinstance(e, dict)]


def baseline_note(have: int) -> dict:
    return {"have": have, "need": BASELINE_WORKS}


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
            history = [
                e["mismatch"] for e in student_evidence(self.name, submission)
                if e.get("language") == lang.code and isinstance(e.get("mismatch"), (int, float))
            ]
            evidence["baseline"] = baseline_note(len(history))
            if len(history) < BASELINE_WORKS:
                evidence["finding"] = (
                    f"above {level_label(level)}, but there is not enough earlier work from this student "
                    f"to tell whether that is unusual for them ({len(history)} of {BASELINE_WORKS})"
                )
                return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
            usual = median(history)
            evidence["baseline"]["usual_mismatch"] = round(usual, 3)
            if fit.mismatch - usual < PERSONAL_JUMP:
                evidence["finding"] = f"above {level_label(level)}, as this student's earlier work also is"
                return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
            evidence["finding"] = f"vocabulary and sentence complexity well above {level_label(level)} and above this student's usual level"
            return AnalysisOutput(confidence=fit.mismatch, verdict="suspicious", evidence=evidence)
        evidence["finding"] = f"fits {level_label(level)}"
        return AnalysisOutput(confidence=1 - fit.mismatch, verdict="inconclusive", evidence=evidence)


class TextStyleAnalyzer(BaseAnalyzer):
    name = "text_style"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def _history(self, submission, language: str) -> list[dict]:
        profiles = [e.get("profile") for e in student_evidence(self.name, submission) if e.get("profile")]
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
        evidence["baseline"] = baseline_note(len(history))
        if len(history) < BASELINE_WORKS:
            evidence["finding"] = f"not enough earlier work from this student to compare ({len(history)} of {BASELINE_WORKS})"
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
        result = drift(profile, history)
        evidence["drift"] = result
        if result["score"] >= CONTEXT_FLAG:
            evidence["finding"] = "writing style differs sharply from this student's earlier work"
            return AnalysisOutput(confidence=result["score"], verdict="suspicious", evidence=evidence)
        evidence["finding"] = "consistent with this student's earlier work"
        return AnalysisOutput(confidence=1 - result["score"], verdict="inconclusive", evidence=evidence)


class TextCitationsAnalyzer(BaseAnalyzer):
    name = "text_citations"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            text = _read(file_path, metadata)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        report = check_citations(text)
        evidence = {**report.as_evidence(), "format": check_format(text), "context_signal": True}
        lang = detect_language(text)
        genre = detect_genre(text, lang) if lang else None
        if genre:
            evidence["genre"] = genre.key
        if not report.references:
            expected = genre is not None and genre.expects_sources
            evidence["finding"] = f"a {genre.label} with no sources at all" if expected else "no references, links or quotes to check"
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence=evidence)
        if report.flagged:
            evidence["finding"] = "cited sources that do not exist"
            return AnalysisOutput(confidence=report.confidence(), verdict="suspicious", evidence=evidence)
        evidence["finding"] = "cited sources check out" if report.checked_weight else "sources could not be checked"
        return AnalysisOutput(confidence=report.confidence() if report.checked_weight else 0.0, verdict="inconclusive", evidence=evidence)


class TextGenreAnalyzer(BaseAnalyzer):
    name = "text_genre"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            text = _read(file_path, metadata)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot read text: {exc}"})
        lang = detect_language(text)
        if lang is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "language not supported"})
        genre = detect_genre(text, lang)
        evidence = {**genre.as_evidence(), "language": lang.code, "context_signal": True, "finding": f"reads as a {genre.label}"}
        return AnalysisOutput(confidence=genre.confidence, verdict="inconclusive", evidence=evidence)


class TextShadowAnalyzer(BaseAnalyzer):
    name = "text_shadow"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain", *DOCUMENT_MIMES]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        submission = _submission(metadata)
        classroom = getattr(submission, "classroom", None)
        if classroom is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "not a class submission"})
        answers = active_answers(classroom)
        if not answers:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "no AI answers generated for this class yet"})
        try:
            text = _read(file_path, metadata)
            match = best_match(text, answers)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"shadow comparison failed: {exc}"})
        if match is None:
            return AnalysisOutput(confidence=0.0, verdict="inconclusive", evidence={"reason": "text too short to compare"})
        evidence = {**match, "context_signal": True}
        if match["flagged"]:
            evidence["finding"] = "follows the structure of an AI answer to this assignment"
            return AnalysisOutput(confidence=round(min(0.95, 0.5 + match["share"] / 2), 3), verdict="suspicious", evidence=evidence)
        evidence["finding"] = "does not follow any AI answer to this class's assignments"
        return AnalysisOutput(confidence=round(1 - match["share"], 3), verdict="inconclusive", evidence=evidence)
