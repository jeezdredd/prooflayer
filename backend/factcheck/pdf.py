import uuid

from reports.copy import COPY, FC_ASSESSMENT_TONE, FC_TONE, lang_or_default, tone_set
from reports.render import render_pdf, shared_context

EXCERPT_CHARS = 1500
MAX_SOURCES = 4


def _sources(claim: dict) -> list[dict]:
    rows = []
    wiki = claim.get("wikipedia") or {}
    if wiki.get("url"):
        rows.append({"title": f"Wikipedia · {wiki.get('title') or wiki['url']}", "url": wiki["url"]})
    for source in claim.get("sources") or []:
        if source.get("url"):
            rows.append({"title": source.get("title") or source["url"], "url": source["url"]})
    for check in claim.get("fact_checks") or []:
        if check.get("url"):
            title = " · ".join(part for part in (check.get("publisher"), check.get("rating")) if part) or check["url"]
            rows.append({"title": title, "url": check["url"]})
    return rows[:MAX_SOURCES]


def _confidence(value) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 1:
        number *= 100
    return max(0, min(100, round(number)))


def build_factcheck_context(result: dict, original_text: str = "", lang: str | None = None) -> dict:
    lang = lang_or_default(lang)
    c = COPY[lang]
    verdict = result.get("overall_verdict", "no_claims")
    claims = []
    for index, claim in enumerate(result.get("claims") or [], start=1):
        assessment = claim.get("assessment", "uncertain")
        claims.append({
            "number": f"{index:02d}",
            "text": claim.get("claim", ""),
            "label": c["fc_assessment"].get(assessment, assessment),
            "confidence": _confidence(claim.get("confidence")),
            "explanation": claim.get("explanation", ""),
            "sources": _sources(claim),
            **tone_set(FC_ASSESSMENT_TONE.get(assessment, "ink")),
        })
    count = len(claims)
    if lang == "ru":
        claims_line = f"Утверждений проверено: {count}"
    else:
        claims_line = f"{count} claim{'s' if count != 1 else ''} checked"
    entities = []
    for entity in result.get("entities") or []:
        text = entity.get("text") if isinstance(entity, dict) else str(entity)
        if text and text not in entities:
            entities.append(text)
    text = (original_text or "").strip()
    return {
        **shared_context(lang, c["factcheck_report"], uuid.uuid4().hex[:8].upper()),
        **tone_set(FC_TONE.get(verdict, "ink")),
        "headline": c["fc_headline"].get(verdict, verdict.replace("_", " ").capitalize()),
        "claims_line": claims_line,
        "claims": claims,
        "entities": entities[:30],
        "excerpt": text[:EXCERPT_CHARS].rstrip() + ("…" if len(text) > EXCERPT_CHARS else ""),
    }


def render_factcheck_pdf(result: dict, original_text: str = "", lang: str | None = None) -> bytes:
    return render_pdf("factcheck/report.html", build_factcheck_context(result, original_text, lang))
