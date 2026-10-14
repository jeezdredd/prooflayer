import io

from django.conf import settings
from django.template.defaultfilters import filesizeformat

from plagiarism.serializers import report_payload
from provenance.visibility import results_for_viewer, sensitive_match_ids
from reports.copy import (
    COPY,
    FC_ASSESSMENT_TONE,
    MEMBER_TONE,
    VERDICT_TONE,
    analyzer_name,
    kind_name,
    lang_or_default,
    tone_set,
)
from reports.render import image_data_uri, render_pdf, shared_context

EXCERPT_CHARS = 700
MAX_SOURCES = 6


def _members(results, lang: str) -> list[dict]:
    c = COPY[lang]
    rows = []
    for result in results:
        if result.verdict == "error":
            continue
        tone = tone_set(MEMBER_TONE.get(result.verdict, "ink"))
        rows.append({
            "name": analyzer_name(result.analyzer.name, lang),
            "vote": c["votes"].get(result.verdict, result.verdict),
            "pct": None if result.verdict == "inconclusive" else max(0, min(100, round((result.confidence or 0) * 100))),
            "order": {"fake": 0, "suspicious": 1, "authentic": 2}.get(result.verdict, 3),
            **tone,
        })
    rows.sort(key=lambda r: (r["order"], -(r["pct"] or 0)))
    return rows


def _originality(payload: dict | None, lang: str) -> dict | None:
    if not payload or payload.get("status") != "done" or payload.get("originality") is None:
        return None
    c = COPY[lang]
    pct = round(payload["originality"])
    sources = []
    for match in payload.get("matches", [])[:MAX_SOURCES]:
        title = match.get("title") or match.get("url") or (c["internal_source"] if match.get("source") == "internal" else "")
        sources.append({"title": title, "url": match.get("url", ""), "share": match.get("share", 0)})
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


def _short_hash(value: str) -> str:
    return f"{value[:16]}…{value[-8:]}" if value and len(value) > 28 else (value or "-")


def build_report_context(submission, user=None) -> dict:
    lang = lang_or_default(getattr(user, "language", None))
    c = COPY[lang]
    verdict = submission.final_verdict or "inconclusive"
    tone = tone_set(VERDICT_TONE.get(verdict, "ink"))
    score_pct = round((submission.final_score or 0) * 100)
    case_ref = str(submission.id).split("-")[0].upper()

    results = list(submission.analysis_results.select_related("analyzer").all())
    provenance = list(submission.provenance_results.all())
    provenance = results_for_viewer(provenance, user, sensitive_match_ids(provenance))
    fingerprint = getattr(submission, "text_fingerprint", None)
    excerpt = ""
    if fingerprint is not None and fingerprint.text:
        text = fingerprint.text.strip()
        excerpt = text[:EXCERPT_CHARS].rstrip() + ("…" if len(text) > EXCERPT_CHARS else "")

    uploaded = submission.created_at.strftime("%d.%m.%Y %H:%M") if lang == "ru" else submission.created_at.strftime("%b %d, %Y %H:%M")
    details = [
        [(c["file"], submission.original_filename, False), (c["type"], kind_name(submission.mime_type, lang), False), (c["size"], filesizeformat(submission.file_size), False)],
        [(c["uploaded"], f"{uploaded} UTC", False), (c["tribunal"], submission.tribunal_version and f"Tribunal {submission.tribunal_version}" or "-", False), (c["fingerprint"], _short_hash(submission.sha256_hash), True)],
    ]

    return {
        **shared_context(lang, c["report"], case_ref),
        **tone,
        "headline": c["headline"].get(verdict, verdict.replace("_", " ").capitalize()),
        "meaning": c["meaning"].get(verdict, ""),
        "score_pct": score_pct,
        "score_bar": max(2, score_pct),
        "known_fake": submission.is_known_fake,
        "thumbnail": image_data_uri(submission.thumbnail),
        "excerpt": excerpt,
        "members": _members(results, lang),
        "originality": _originality(report_payload(submission, user), lang),
        "provenance": [
            {
                "title": p.title or p.source_url or p.get_source_type_display(),
                "url": p.source_url,
                "similarity": round(p.similarity_score * 100) if p.similarity_score is not None and p.similarity_score <= 1 else None,
            }
            for p in provenance
        ],
        "claims": _claims(getattr(submission, "factcheck_result", None), lang),
        "details": details,
        "result_url": f"{settings.FRONTEND_URL}/results/{submission.id}",
    }


def generate_report_pdf(submission, request=None):
    user = getattr(request, "user", None)
    return io.BytesIO(render_pdf("content/report.html", build_report_context(submission, user)))
