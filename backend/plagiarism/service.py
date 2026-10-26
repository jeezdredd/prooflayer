import logging
import math
import re

from django.conf import settings
from django.db import transaction
from pgvector.django import CosineDistance

from analyzers.text.evasion import hidden_docx_texts, strip_hidden
from analyzers.text.language import CYRILLIC_RE, LATIN_RE, detect_language
from classroom.models import ShadowSet
from common.documents import DOCX_MIME, read_text
from content.storage_utils import local_file

from .embeddings import EmbeddingsUnavailable, embed
from .models import PlagiarismReport, SentenceVector, TextFingerprint
from .shingles import (
    SHINGLE,
    copied_pairs,
    covered_token_chars,
    matched_runs,
    merge_spans,
    shingle_hashes,
    text_chars,
    tokenize,
    tokens_in,
    winnow,
)
from .web import WebResult, web_matches

logger = logging.getLogger(__name__)

TEXT_LIMIT = 200_000
SENTENCE_RE = re.compile(r"[^.!?…\n]+[.!?…]*")
MIN_SENTENCE_WORDS = 8
MAX_SENTENCES = 250
CANDIDATES = 200
TOP_SOURCES = 15
PARAPHRASE_SIMILAR = 0.95
TRANSLATION_SIMILAR = 0.92
STRONG_SIMILAR = 0.98
COMMON_AUTHORS = 3
COMMON_SHARE = 0.3
COMMON_MAX_WORDS = 30
MIN_SOURCE_CHARS = 60
MIN_SHARE = 0.6
MAX_PAIRS = 20
KINDS = ("exact", "paraphrase", "translation")
BIBLIOGRAPHY_RE = re.compile(
    r"^[ \t]*(?:список(?:[ \t]+\w+){0,2}[ \t]+(?:литературы|источников)|литература|библиография"
    r"|(?:использованные[ \t]+)?источники|references|bibliography|works cited|reference list|sources|literature(?:[ \t]+cited)?|bibliographie"
    r"|références|sources et références)[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


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


def body_end(text: str) -> int:
    for match in BIBLIOGRAPHY_RE.finditer(text):
        if match.start() >= len(text) * 0.4:
            return match.start()
    return len(text)


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


def common_mask(submission, tokens, hashes) -> list[bool]:
    common = [False] * len(tokens)
    if submission.classroom_id is None or not hashes:
        return common
    prompts: set[int] = set()
    for prompt in ShadowSet.objects.filter(classroom_id=submission.classroom_id).values_list("prompt", flat=True):
        prompts.update(shingle_hashes(tokenize(prompt)))
    classmates = TextFingerprint.objects.filter(
        in_repository=True, submission__classroom_id=submission.classroom_id,
    ).exclude(submission__user_id=submission.user_id)
    needed = max(COMMON_AUTHORS, math.ceil(COMMON_SHARE * classmates.values("submission__user_id").distinct().count()))
    own = set(hashes)
    authors: dict[int, set] = {}
    rows = classmates.filter(fingerprints__overlap=winnow(hashes)).values_list("submission__user_id", "text")
    for user_id, text in rows[:CANDIDATES]:
        for h in own.intersection(shingle_hashes(tokenize(text))):
            authors.setdefault(h, set()).add(user_id)
    shared = {h for h, users in authors.items() if len(users) >= needed}
    runs = [r for r in matched_runs(tokens, hashes, shared, min_len=SHINGLE) if r[1] - r[0] <= COMMON_MAX_WORDS]
    runs += matched_runs(tokens, hashes, prompts, min_len=SHINGLE)
    for a, b in runs:
        for j in range(a, b):
            common[j] = True
    return common


def mostly_skipped(starts: list[int], skip: list[bool], span: tuple[int, int]) -> bool:
    inside = tokens_in(starts, span)
    return not inside or 2 * sum(skip[j] for j in inside) >= len(inside)


def internal_exact(submission, tokens, hashes, skip: list[bool]) -> list[dict]:
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
        pairs = copied_pairs(tokens, hashes, tokenize(source_text), skip)
        if pairs:
            matches.append({
                "source": "internal",
                "kind": "exact",
                "kinds": ["exact"],
                "submission_id": str(source_id),
                "submitted_at": created.isoformat(),
                "spans": [own for own, _ in pairs],
                "pairs": [{"own": own, "src": found, "kind": "exact"} for own, found in pairs],
            })
    return matches


def reused(hits: list[dict]) -> bool:
    if any(h["similarity"] >= STRONG_SIMILAR for h in hits):
        return True
    placed = {(h["index"], h["position"]) for h in hits}
    return any((i + 1, p + 1) in placed for i, p in placed)


def internal_semantic(submission, language: str, sents, vectors, skipped: list[bool]) -> list[dict]:
    found: dict[str, list[dict]] = {}
    created: dict[str, str] = {}
    for i, ((start, end, sentence), vector) in enumerate(zip(sents, vectors)):
        if skipped[i]:
            continue
        own_language = sentence_language(sentence, language)
        nearest = (
            SentenceVector.objects.exclude(submission__user_id=submission.user_id)
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")
            .values("submission_id", "position", "start", "end", "language", "distance", "submission__created_at")
            .first()
        )
        if not nearest:
            continue
        similarity = 1 - float(nearest["distance"])
        translated = bool(nearest["language"]) and nearest["language"] != own_language
        if similarity < (TRANSLATION_SIMILAR if translated else PARAPHRASE_SIMILAR):
            continue
        key = str(nearest["submission_id"])
        created.setdefault(key, nearest["submission__created_at"].isoformat())
        found.setdefault(key, []).append({
            "index": i,
            "position": nearest["position"],
            "own": (start, end),
            "src": (nearest["start"], nearest["end"]),
            "kind": "translation" if translated else "paraphrase",
            "similarity": round(similarity, 3),
        })
    matches = []
    for key, hits in found.items():
        kinds = sorted({h["kind"] for h in hits}, key=KINDS.index)
        matches.append({
            "source": "internal",
            "kind": kinds[0],
            "kinds": kinds,
            "submission_id": key,
            "submitted_at": created[key],
            "spans": [h["own"] for h in hits],
            "pairs": [{"own": h["own"], "src": h["src"], "kind": h["kind"]} for h in hits],
            "similarity": max(h["similarity"] for h in hits),
            "reused": reused(hits),
        })
    return matches


def overlap(span, spans) -> int:
    return sum(max(0, min(span[1], e) - max(span[0], s)) for s, e in spans)


def merge_sources(exact: list[dict], semantic: list[dict], tokens) -> list[dict]:
    by_source = {m["submission_id"]: m for m in exact}
    merged = list(exact)
    for m in semantic:
        target = by_source.get(m["submission_id"])
        backed = target is not None and covered_token_chars(tokens, target["spans"]) >= MIN_SOURCE_CHARS
        if not (m.pop("reused") or backed):
            continue
        if target is None:
            merged.append(m)
            continue
        covered = merge_spans(target["spans"])
        added = [p for p in m["pairs"] if 2 * overlap(p["own"], covered) < p["own"][1] - p["own"][0]]
        if not added:
            continue
        target["pairs"] += added
        target["spans"] += [p["own"] for p in added]
        target["kinds"] = sorted(set(target["kinds"]) | {p["kind"] for p in added}, key=KINDS.index)
        target["similarity"] = m["similarity"]
    return merged


def counted(matches: list[dict], tokens, total: int) -> tuple[list[dict], int]:
    kept = []
    for m in matches:
        m["matched_chars"] = covered_token_chars(tokens, m["spans"])
        if m["matched_chars"] < MIN_SOURCE_CHARS or 100 * m["matched_chars"] / total < MIN_SHARE:
            continue
        m["spans"] = merge_spans(m["spans"])
        longest = sorted(m["pairs"], key=lambda p: p["own"][0] - p["own"][1])[:MAX_PAIRS]
        m["pairs"] = sorted(longest, key=lambda p: p["own"][0])
        kept.append(m)
    kept.sort(key=lambda m: -m["matched_chars"])
    matched = covered_token_chars(tokens, [span for m in kept for span in m["spans"]])
    return kept, min(total, matched)


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
        end = body_end(text)
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

        skip = [flag or t.start >= end for flag, t in zip(common_mask(submission, tokens, hashes), tokens)]
        starts = [t.start for t in tokens]
        skipped = [s >= end or mostly_skipped(starts, skip, (s, e)) for s, e, _ in sents]
        matches = merge_sources(
            internal_exact(submission, tokens, hashes, skip),
            internal_semantic(submission, language, sents, vectors, skipped),
            tokens,
        )
        web = WebResult(PlagiarismReport.WebStatus.OFF)
        if web_search_allowed(submission):
            web = web_matches(text[:end], tokens, hashes, skip)
            matches += web.matches

        total = max(1, text_chars([t for t in tokens if t.start < end]))
        matches, matched = counted(matches, tokens, total)

        report.matches = matches
        report.total_chars = total
        report.matched_chars = matched
        report.originality = round(100 * (1 - matched / total), 1)
        report.web_status = web.status
        report.web_searched = web.status == PlagiarismReport.WebStatus.OK
        report.web_queries = web.queries
        report.web_engines = web.engines
        report.status = PlagiarismReport.Status.DONE
    except Exception as exc:
        logger.exception("plagiarism check failed for %s", submission.id)
        report.status = PlagiarismReport.Status.FAILED
        report.error = str(exc)[:500]
    report.save()
    return report


def _read(submission) -> str:
    with local_file(submission.file) as path:
        text = read_text(path, submission.mime_type, TEXT_LIMIT)
        if submission.mime_type == DOCX_MIME:
            text = strip_hidden(text, hidden_docx_texts(path))
        return text
