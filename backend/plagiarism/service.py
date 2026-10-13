import logging
import re

from django.conf import settings
from django.db import transaction
from pgvector.django import CosineDistance

from analyzers.text.language import CYRILLIC_RE, LATIN_RE, detect_language
from common.documents import read_text
from content.storage_utils import local_file

from .embeddings import EmbeddingsUnavailable, embed
from .models import PlagiarismReport, SentenceVector, TextFingerprint
from .shingles import covered_spans, merge_spans, shingle_hashes, span_chars, text_chars, tokenize, winnow
from .web import web_matches

logger = logging.getLogger(__name__)

TEXT_LIMIT = 200_000
SENTENCE_RE = re.compile(r"[^.!?…\n]+[.!?…]*")
MIN_SENTENCE_WORDS = 8
MAX_SENTENCES = 250
CANDIDATES = 200
TOP_SOURCES = 15
SIMILAR = 0.92
COUNTED_SIMILAR = 0.95


def sentence_spans(text: str) -> list[tuple[int, int, str]]:
    out = []
    for m in SENTENCE_RE.finditer(text):
        chunk = m.group()
        stripped = chunk.strip()
        if len(stripped.split()) < MIN_SENTENCE_WORDS:
            continue
        start = m.start() + (len(chunk) - len(chunk.lstrip()))
        out.append((start, start + len(stripped), stripped))
        if len(out) >= MAX_SENTENCES:
            break
    return out


def sentence_language(sentence: str, default: str) -> str:
    lang = detect_language(sentence)
    if lang is not None:
        return lang.code
    cyr = len(CYRILLIC_RE.findall(sentence))
    lat = len(LATIN_RE.findall(sentence))
    if cyr > lat:
        return "ru"
    if lat > cyr:
        return default if default in ("en", "fr") else "en"
    return default


def index(submission, text: str, language: str, hashes: list[int], sents: list[tuple[int, int, str]], vectors: list[list[float]]):
    in_repository = submission.classroom_id is not None
    with transaction.atomic():
        TextFingerprint.objects.update_or_create(
            submission=submission,
            defaults={"language": language, "text": text, "fingerprints": winnow(hashes), "in_repository": in_repository},
        )
        SentenceVector.objects.filter(submission=submission).delete()
        if not in_repository:
            return
        SentenceVector.objects.bulk_create([
            SentenceVector(submission=submission, position=i, start=s, end=e, language=sentence_language(text_, language), embedding=v)
            for i, ((s, e, text_), v) in enumerate(zip(sents, vectors))
        ])


def internal_exact(submission, tokens, hashes) -> list[dict]:
    fingerprints = set(winnow(hashes))
    if not fingerprints:
        return []
    rows = (
        TextFingerprint.objects.filter(in_repository=True, fingerprints__overlap=list(fingerprints))
        .exclude(submission__user_id=submission.user_id)
        .values_list("submission_id", "fingerprints", "text", "submission__created_at")[:CANDIDATES]
    )
    ranked = sorted(rows, key=lambda r: -len(fingerprints.intersection(r[1])))[:TOP_SOURCES]
    matches = []
    for source_id, _, source_text, created in ranked:
        spans = covered_spans(tokens, hashes, set(shingle_hashes(tokenize(source_text))))
        if spans:
            matches.append({
                "source": "internal",
                "kind": "exact",
                "submission_id": str(source_id),
                "submitted_at": created.isoformat(),
                "spans": spans,
            })
    return matches


def internal_semantic(submission, language: str, sents, vectors) -> list[dict]:
    by_source: dict[str, dict] = {}
    for (start, end, sentence), vector in zip(sents, vectors):
        own_language = sentence_language(sentence, language)
        nearest = (
            SentenceVector.objects.exclude(submission__user_id=submission.user_id)
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")
            .values("submission_id", "language", "distance", "submission__created_at")
            .first()
        )
        if not nearest:
            continue
        similarity = 1 - float(nearest["distance"])
        if similarity < SIMILAR:
            continue
        key = str(nearest["submission_id"])
        entry = by_source.setdefault(key, {
            "source": "internal",
            "kind": "translation" if nearest["language"] and nearest["language"] != own_language else "paraphrase",
            "submission_id": key,
            "submitted_at": nearest["submission__created_at"].isoformat(),
            "spans": [],
            "counted_spans": [],
            "similarity": 0.0,
        })
        entry["spans"].append((start, end))
        if similarity >= COUNTED_SIMILAR:
            entry["counted_spans"].append((start, end))
        entry["similarity"] = round(max(entry["similarity"], similarity), 3)
    return list(by_source.values())


def web_search_allowed(submission) -> bool:
    if not getattr(settings, "PLAGIARISM_WEB_ENABLED", True):
        return False
    if submission.classroom_id is None:
        return True
    organization = submission.classroom.organization
    return organization is not None and organization.web_search_enabled


def run_check(submission) -> PlagiarismReport:
    report, _ = PlagiarismReport.objects.get_or_create(submission=submission)
    report.status = PlagiarismReport.Status.RUNNING
    report.error = ""
    report.save(update_fields=["status", "error", "updated_at"])
    try:
        text = _read(submission)
        lang = detect_language(text)
        language = lang.code if lang else ""
        tokens = tokenize(text)
        hashes = shingle_hashes(tokens)
        sents = sentence_spans(text)
        try:
            vectors = embed([s for _, _, s in sents])
        except EmbeddingsUnavailable as exc:
            logger.error("originality check without semantic matching: %s", exc)
            vectors = []
        index(submission, text, language, hashes, sents, vectors)

        matches = internal_exact(submission, tokens, hashes)
        exact_sources = {m["submission_id"] for m in matches}
        matches += [m for m in internal_semantic(submission, language, sents, vectors) if m["submission_id"] not in exact_sources]
        web_queries = 0
        if web_search_allowed(submission):
            web, web_queries = web_matches(text)
            matches += web

        counted = []
        for m in matches:
            counted += m.get("counted_spans", m["spans"]) if m["kind"] != "exact" else m["spans"]
            m["matched_chars"] = span_chars(m["spans"])
        total = max(1, text_chars(tokens))
        matched = min(total, span_chars(counted))
        matches.sort(key=lambda m: -m["matched_chars"])
        for m in matches:
            m["spans"] = merge_spans(m["spans"])
            m.pop("counted_spans", None)

        report.matches = matches
        report.total_chars = total
        report.matched_chars = matched
        report.originality = round(100 * (1 - matched / total), 1)
        report.web_searched = web_queries > 0
        report.web_queries = web_queries
        report.status = PlagiarismReport.Status.DONE
    except Exception as exc:
        logger.exception("plagiarism check failed for %s", submission.id)
        report.status = PlagiarismReport.Status.FAILED
        report.error = str(exc)[:500]
    report.save()
    return report


def _read(submission) -> str:
    with local_file(submission.file) as path:
        return read_text(path, submission.mime_type, TEXT_LIMIT)
