import io
from datetime import datetime
from urllib.parse import urlparse

from django.utils import timezone

from plagiarism.serializers import report_payload
from provenance.visibility import provenance_rows
from reports.copy import (
    COPY,
    FC_ASSESSMENT_TONE,
    MEMBER_TONE,
    STATUS_TONE,
    VERDICT_TONE,
    analyzer_name,
    field_name,
    kind_name,
    lang_or_default,
    tone_set,
)
from reports.render import image_data_uri, render_pdf, shared_context

from .viewer import result_url, viewer_info

EXCERPT_CHARS = 700
MAX_SOURCES = 6
MAX_PASSAGES = 3
PASSAGE_FLOOR = 0.45
PASSAGE_CHARS = 600
AI_LOOK = 0.45
SPREAD_ALERT = 0.5
MIN_CORROBORATING_FAKE = 2
FLAGGED = {"fake", "likely_fake", "suspicious"}
AI_VERDICTS = ("fake", "likely_fake")
TEXT_ANALYZERS = ("text_classifier", "text_evasion", "text_grade_fit", "text_style", "text_citations", "text_shadow")
CONTEXT_ANALYZERS = ("text_evasion", "text_grade_fit", "text_style", "text_citations", "text_shadow", "text_genre", "ela")
IMAGE_DETECTORS = (
    "community_forensics", "ai_detector", "clip_probe", "custom_detector", "npr_detector", "siglip_detector", "llm_vision",
)
RANK = {"off": 0, "wait": 1, "ok": 2, "look": 3, "alert": 4}
MAIN_SOURCE_SHARE = 50


def _members(results, lang: str, image: bool = False) -> list[dict]:
    votes = COPY[lang]["votes_image" if image else "votes"]
    rows = []
    for result in results:
        if result.verdict == "error":
            continue
        rows.append({
            "name": analyzer_name(result.analyzer.name, lang),
            "vote": votes.get(result.verdict, result.verdict),
            "order": {"fake": 0, "suspicious": 1, "authentic": 2}.get(result.verdict, 3),
            **tone_set(MEMBER_TONE.get(result.verdict, "ink")),
        })
    rows.sort(key=lambda r: r["order"])
    return rows


def _source_title(match: dict, c: dict) -> str:
    if match.get("source") == "web":
        return match.get("title") or match.get("url") or ""
    if match.get("submission_id") and match.get("author"):
        name = match["author"] if not match.get("classroom") else f"{match['author']}, {match['classroom']}"
        return c["internal_author"].format(name=name)
    return c["internal_source"]


def _originality(payload: dict | None, lang: str) -> dict | None:
    if not payload or payload.get("status") != "done" or payload.get("originality") is None:
        return None
    c = COPY[lang]
    pct = round(payload["originality"])
    sources = [
        {"title": _source_title(match, c), "url": match.get("url", ""), "share": match.get("share", 0)}
        for match in payload.get("matches", [])[:MAX_SOURCES]
    ]
    tone = "sage" if pct >= 85 else "amber" if pct >= 60 else "blood"
    return {
        "pct": pct,
        "tone": tone_set(tone)["tone"],
        "matched_line": c["matched"].format(matched=payload.get("matched_chars", 0), total=payload.get("total_chars", 0)),
        "scope": c["web_on"] if payload.get("web_searched") else c["web_off"],
        "sources": sources,
    }


def _claims(factcheck, lang: str) -> list[dict]:
    claims = getattr(factcheck, "claims", None) or []
    c = COPY[lang]
    rows = []
    for claim in claims:
        get = claim.get if isinstance(claim, dict) else (lambda k, d=None, o=claim: getattr(o, k, d))
        assessment = get("assessment", "uncertain")
        rows.append({
            "text": get("claim", ""),
            "explanation": get("explanation", ""),
            "label": c["fc_assessment"].get(assessment, assessment),
            **tone_set(FC_ASSESSMENT_TONE.get(assessment, "ink")),
        })
    return rows


def _passages(results) -> list[dict]:
    classifier = next((r for r in results if r.analyzer.name == "text_classifier"), None)
    segments = ((classifier.evidence or {}).get("segments") or []) if classifier else []
    if len(segments) < 2:
        return []
    picked = sorted((s for s in segments if s.get("ai_probability", 0) >= PASSAGE_FLOOR), key=lambda s: -s["ai_probability"])[:MAX_PASSAGES]
    rows = []
    for segment in picked:
        text = (segment.get("text") or segment.get("excerpt") or "").strip()
        tone = "blood" if segment["ai_probability"] >= 0.75 else "amber"
        rows.append({
            "text": text[:PASSAGE_CHARS].rstrip() + ("…" if len(text) > PASSAGE_CHARS else ""),
            "pct": round(segment["ai_probability"] * 100),
            **tone_set(tone),
        })
    return rows


def _file_size(size: int, lang: str) -> str:
    units = COPY[lang]["units"]
    value, unit = float(size or 0), units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    number = f"{value:.0f}" if unit == units[0] else f"{value:.1f}"
    return f"{number.replace('.', ',') if lang == 'ru' else number} {unit}"


def _short_hash(value: str) -> str:
    return f"{value[:16]}…{value[-8:]}" if value and len(value) > 28 else (value or "-")


def _evidence(by_name: dict, name: str) -> dict:
    result = by_name.get(name)
    return (result.evidence or {}) if result is not None else {}


def main_source(payload, plain: dict) -> tuple[str, bool] | None:
    matches = (payload or {}).get("matches") or []
    if not matches:
        return None
    top = matches[0]
    most = (top.get("share") or 0) >= MAIN_SOURCE_SHARE
    if top.get("source") == "web":
        host = (urlparse(top.get("url") or "").hostname or "").removeprefix("www.")
        title = top.get("title") or ""
        name = f"{title} ({host})" if title and host else (title or host)
        return (name, most) if name else None
    if not top.get("hidden") and top.get("author"):
        return plain["source_student"].format(name=top["author"]), most
    return plain["source_other"], most


def _plain_outcome(
    verdict: str, originality, too_short: bool, audience: str, c: dict, source: tuple[str, bool] | None = None,
) -> tuple[str, str]:
    plain = c["plain"]
    key = verdict if verdict in plain["teacher"] else "inconclusive"
    text = plain[audience][key]
    status = {"authentic": "ok", "authentic_edited": "ok", "needs_review": "look", "suspicious": "look"}.get(key, "alert" if key in ("likely_fake", "fake") else "wait")
    if key == "inconclusive" and too_short:
        text = plain["too_short"][audience]
        status = "wait"
    if originality is not None and originality < 60 and RANK[status] < RANK["alert"]:
        if source and audience == "teacher":
            name, most = source
            return plain["copy_source" if most else "copy_sources_main"].format(source=name), "alert"
        return plain["copy_most"][audience], "alert"
    if originality is not None and originality < 85 and RANK[status] < RANK["look"]:
        return plain["copy_part"][audience], "look"
    return text, status


def _level(value, k: dict) -> str:
    if not isinstance(value, int):
        return k["level_unknown"]
    return k["level_school"].format(n=value) if value <= 11 else k["level_university"].format(n=value - 11)


def _ai_check(by_name, k):
    result = by_name.get("text_classifier")
    if result is None:
        return None
    ev = result.evidence or {}
    p = ev.get("ai_probability")
    if not isinstance(p, (int, float)):
        return "off", k["ai_none"]
    uneven = isinstance(ev.get("segment_spread"), (int, float)) and ev["segment_spread"] >= SPREAD_ALERT
    if result.verdict in FLAGGED:
        return "alert", k["ai_alert"]
    if p >= AI_LOOK or uneven:
        return "look", k["ai_parts"] if uneven else k["ai_some"]
    return "ok", k["ai_ok"]


def _copy_check(payload, k):
    if not payload:
        return None
    if payload.get("status") == "failed":
        return "off", k["copy_failed"]
    if payload.get("status") != "done" or payload.get("originality") is None:
        return "wait", k["copy_wait"]
    if not payload.get("matches"):
        return "ok", k["copy_ok"]
    originality = payload["originality"]
    status = "ok" if originality >= 85 else "look" if originality >= 60 else "alert"
    return status, k["copy_share"].format(n=100 - round(originality))


def _tricks_check(by_name, k):
    result = by_name.get("text_evasion")
    if result is None:
        return None
    if result.verdict in ("fake", "suspicious"):
        return "alert", k["tricks_alert"]
    return "ok", k["tricks_ok"]


def _age_check(by_name, k, student: bool):
    result = by_name.get("text_grade_fit")
    if result is None:
        return None
    ev = result.evidence or {}
    level = _level(ev.get("level"), k)
    baseline = ev.get("baseline") if isinstance(ev.get("baseline"), dict) else None
    if result.verdict == "suspicious":
        return "look", k["age_high"].format(level=level)
    if baseline and baseline.get("have", 0) < baseline.get("need", 0):
        return "wait", k["age_early"].format(level=level)
    if baseline:
        return "ok", k["age_usual"].format(level=level)
    if ev.get("reason") == "class level not set":
        return None if student else ("off", k["age_unset"])
    if isinstance(ev.get("reason"), str):
        return None
    return "ok", k["age_ok"].format(level=level)


def _style_check(by_name, k):
    result = by_name.get("text_style")
    if result is None:
        return None
    ev = result.evidence or {}
    if result.verdict == "suspicious":
        return "look", k["style_diff"]
    if ev.get("drift"):
        return "ok", k["style_ok"]
    baseline = ev.get("baseline") if isinstance(ev.get("baseline"), dict) else {}
    return "wait", k["style_wait"].format(have=baseline.get("have", 0), need=baseline.get("need", 3))


def _sources_check(by_name, k):
    result = by_name.get("text_citations")
    if result is None:
        return None
    ev = result.evidence or {}
    refs = [r for r in (ev.get("references") or []) if isinstance(r, dict)]
    missing = sum(1 for r in refs if r.get("status") == "missing")
    found = sum(1 for r in refs if r.get("status") == "found")
    if not refs:
        return ("look", k["sources_report"]) if ev.get("genre") == "report" else ("off", k["sources_none"])
    if result.verdict == "suspicious":
        return "alert", k["sources_fake"].format(missing=missing, total=len(refs))
    if missing:
        return "look", k["sources_missing"].format(missing=missing, total=len(refs))
    if found:
        return "ok", k["sources_ok"]
    return "off", k["sources_unchecked"]


def _shadow_check(by_name, k, student: bool):
    result = by_name.get("text_shadow")
    if result is None:
        return None
    ev = result.evidence or {}
    share = ev.get("share")
    if not isinstance(share, (int, float)):
        if ev.get("reason") == "not a class submission" or student:
            return None
        return "off", k["shadow_none"]
    if result.verdict == "suspicious":
        return "alert", k["shadow_alert"].format(n=round(share * 100))
    return "ok", k["shadow_ok"]


def _text_checks(by_name: dict, payload, lang: str, student: bool) -> list[dict]:
    c = COPY[lang]
    k = c["check"]
    found = [
        ("ai", _ai_check(by_name, k)),
        ("copy", _copy_check(payload, k)),
        ("tricks", _tricks_check(by_name, k)),
        ("age", _age_check(by_name, k, student)),
        ("style", _style_check(by_name, k)),
        ("sources", _sources_check(by_name, k)),
        ("shadow", _shadow_check(by_name, k, student)),
    ]
    return [
        {"key": key, "title": k[key], "status": status, "word": c["status"][status], "headline": headline, **tone_set(STATUS_TONE[status])}
        for key, outcome in found
        if outcome is not None
        for status, headline in [outcome]
    ]


def _trace_lines(metadata: dict, lang: str) -> list[str]:
    t = COPY[lang]["trace"]
    lines = []
    for trace in metadata.get("ai_trace") or []:
        kind = trace.get("kind")
        action = t["edited"] if trace.get("ai") == "edited" else t["generated"]
        if kind == "watermark":
            key = "watermark_damaged" if trace.get("damaged") else "watermark"
            lines.append(t[key].format(name=trace.get("generator") or ""))
        elif kind == "c2pa":
            parts = [t["c2pa"].format(action=action)]
            if trace.get("signed_by"):
                parts.append(t["c2pa_signed"].format(name=trace["signed_by"]))
            if trace.get("trusted"):
                parts.append(t["c2pa_trusted"])
            elif trace.get("state") == "Invalid":
                parts.append(t["c2pa_damaged"])
            else:
                parts.append(t["c2pa_untrusted"])
            lines.append(", ".join(parts) + ".")
        elif kind == "xmp":
            lines.append(t["xmp"].format(action=action) + ".")
        elif kind == "software_tag":
            value = trace.get("raw_value") or trace.get("generator") or ""
            lines.append(t["software"].format(field=field_name(trace.get("field"), lang), value=value) + ".")
        elif kind == "generation_params":
            lines.append(t["params"].format(text=trace["text"]) + "." if trace.get("text") else t["params_empty"] + ".")
    return lines


def _proof_generator(metadata: dict) -> tuple[str, str] | None:
    if not metadata.get("provenance_proof"):
        return None
    for trace in metadata.get("ai_trace") or []:
        if trace.get("kind") == "watermark" and not trace.get("damaged"):
            return "meaning_proof", trace.get("generator") or ""
        if trace.get("kind") == "c2pa" and trace.get("trusted"):
            return "meaning_proof_signed", trace.get("signed_by") or trace.get("generator") or ""
    return "meaning_proof", ""


def _detector_votes(results) -> tuple[int, int]:
    voters = [r for r in results if r.analyzer.name in IMAGE_DETECTORS and r.verdict != "error"]
    return sum(1 for r in voters if r.verdict in ("fake", "suspicious")), len(voters)


def _meaning(verdict: str, results, metadata: dict, lang: str) -> str:
    c = COPY[lang]
    proof = _proof_generator(metadata)
    if proof:
        return c[proof[0]].format(generator=proof[1]).replace(" ()", "")
    fake_votes = sum(1 for r in results if r.verdict == "fake" and r.analyzer.name not in CONTEXT_ANALYZERS)
    if verdict in ("fake", "likely_fake") and fake_votes < MIN_CORROBORATING_FAKE:
        return c["meaning_one_detector"]
    return c["meaning"].get(verdict, "")


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _local_date(value, lang: str) -> str:
    local = timezone.localtime(value)
    return local.strftime("%d.%m.%Y") if lang == "ru" else local.strftime("%b %d, %Y")


def _where_line(row: dict, lang: str, student: bool) -> str | None:
    w = COPY[lang]["where"]
    match = row.get("match")
    if not match:
        return None
    what = w[match["kind"]]
    scope = match["scope"]
    if scope in ("visible", "yours"):
        first = match.get("author") if scope == "visible" else row.get("title")
        parts = [p for p in (first, match.get("classroom")) if p]
        if match.get("submitted_at"):
            parts.append(_local_date(datetime.fromisoformat(match["submitted_at"]), lang))
        key = "yours_class" if scope == "yours" and student else scope
        return w[key].format(what=what, who=", ".join(parts))
    return w[scope].format(what=what)


def _provenance(submission, user, lang: str, student: bool) -> list[dict]:
    rows = []
    for row in provenance_rows(submission, user):
        line = _where_line(row, lang, student)
        if line is not None:
            rows.append({"title": line, "url": "", "similarity": None})
        else:
            score = row.get("similarity_score")
            rows.append({
                "title": row.get("title") or row.get("source_url") or "",
                "url": row.get("source_url") or "",
                "similarity": round(score * 100) if score is not None and score <= 1 else None,
            })
    return rows


def build_report_context(submission, user=None) -> dict:
    lang = lang_or_default(getattr(user, "language", None))
    c = COPY[lang]
    verdict = submission.final_verdict or "inconclusive"
    viewer = viewer_info(submission, user)
    in_class = submission.classroom_id is not None
    audience = "student" if viewer["student_view"] else "teacher"
    case_ref = str(submission.id).split("-")[0].upper()

    results = list(submission.analysis_results.select_related("analyzer").all())
    by_name = {r.analyzer.name: r for r in results}
    metadata = _evidence(by_name, "metadata")
    is_text = any(name in by_name for name in TEXT_ANALYZERS)
    is_image = (submission.mime_type or "").startswith("image/")
    payload = report_payload(submission, user)

    fingerprint = getattr(submission, "text_fingerprint", None)
    excerpt = ""
    if fingerprint is not None and fingerprint.text:
        text = fingerprint.text.strip()
        excerpt = text[:EXCERPT_CHARS].rstrip() + ("…" if len(text) > EXCERPT_CHARS else "")

    checks = _text_checks(by_name, payload, lang, audience == "student") if is_text else []
    proof = _proof_generator(metadata) if verdict in AI_VERDICTS else None
    status = ""
    if in_class:
        originality = payload.get("originality") if payload and payload.get("status") == "done" else None
        too_short = _evidence(by_name, "text_classifier").get("reason") == "text too short for a verdict"
        headline, status = _plain_outcome(verdict, originality, too_short, audience, c, main_source(payload, c["plain"]))
        if is_image and audience == "teacher" and status == "alert":
            headline = c["proof_headline"] if proof else c["plain"]["image_alert"]
        tone = tone_set(STATUS_TONE[status])
    else:
        headline = c["headline"].get(verdict, verdict.replace("_", " ").capitalize())
        tone = tone_set(VERDICT_TONE.get(verdict, "ink"))

    raised = [ch for ch in checks if ch["status"] in ("alert", "look")]
    if in_class and is_text:
        meaning = c["raised_by"].format(reasons="; ".join(_lower_first(ch["headline"]) for ch in raised)) if raised else c["no_concerns"]
    else:
        meaning = _meaning(verdict, results, metadata, lang)
    fake_votes, total_votes = _detector_votes(results)
    detector_line = c["detector_count"].format(fake=fake_votes, total=total_votes) if is_image and total_votes and not proof else ""
    next_step = ""
    if in_class and audience == "teacher" and (proof or status in ("look", "alert") or raised):
        next_step = c["next_step_proof"] if proof else c["next_step"]
    if proof:
        note = c["proof_note"] if in_class else c["proof_note_main"]
    else:
        note = c["class_note"] if in_class else c["human_note"]

    handed_in = _local_date(submission.created_at, lang)
    details = []
    if in_class and viewer["student_name"]:
        details.append([
            (c["student"], viewer["student_name"]),
            (c["classroom"], viewer["classroom"]["name"] if viewer["classroom"] else "-"),
            (c["handed_in"], handed_in),
        ])
    details.append([
        (c["file"], submission.original_filename),
        (c["type"], kind_name(submission.mime_type, lang)),
        (c["size"] if in_class else c["uploaded"], _file_size(submission.file_size, lang) if in_class else handed_in),
    ])
    technical = f"SHA-256 {_short_hash(submission.sha256_hash)}"
    if submission.tribunal_version:
        technical += f" · Tribunal {submission.tribunal_version}"

    return {
        **shared_context(lang, c["report"], case_ref),
        **tone,
        "badge": c["in_short"] if in_class else c["verdict"],
        "headline": headline,
        "meaning": meaning,
        "detector_line": detector_line,
        "next_step": next_step,
        "note": note,
        "known_fake": submission.is_known_fake,
        "thumbnail": image_data_uri(submission.thumbnail),
        "excerpt": excerpt,
        "checks": checks,
        "show_traces": is_image and "metadata" in by_name,
        "traces": _trace_lines(metadata, lang),
        "members": [] if is_text and in_class else _members(results, lang, image=is_image),
        "passages": _passages(results),
        "originality": _originality(payload, lang),
        "provenance": _provenance(submission, user, lang, audience == "student") if is_image else [],
        "claims": _claims(getattr(submission, "factcheck_result", None), lang),
        "details": details,
        "technical": technical,
        "result_url": result_url(submission),
    }


def generate_report_pdf(submission, request=None):
    user = getattr(request, "user", None)
    return io.BytesIO(render_pdf("content/report.html", build_report_context(submission, user)))
