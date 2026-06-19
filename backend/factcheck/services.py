import json
import logging
from urllib.parse import quote

import requests as http_requests
from django.conf import settings
from duckduckgo_search import DDGS

from factcheck.ner import extract_claim_sentences, extract_entities

logger = logging.getLogger(__name__)

OLLAMA_ASSESS_PROMPT = """You are a fact-checking engine. Assess each claim below strictly.

Assessment rules (use EXACTLY these values, no other values allowed):
- "likely_true": matches well-known established facts or confirmed by web context.
- "likely_false": contradicts established facts, scientifically disproven, or refuted by web context.
- "uncertain": recent/ongoing event, genuinely ambiguous, or cannot verify.

Confidence rules:
- "confidence": integer 0-100. Strength of supporting evidence.
- High (80-100): authoritative sources or established knowledge clearly confirm/refute.
- Medium (40-79): partial evidence or limited sources.
- Low (0-39): little/conflicting evidence, mostly inference.

Be strict: if a claim is scientifically wrong or historically incorrect, use "likely_false", not "uncertain".

Web context:
{search_context}

Claims (assess ALL, in order):
{claims_list}

Respond ONLY with a JSON array, exactly one object per claim, same order:
[{{"claim": "exact claim text", "assessment": "likely_true", "confidence": 85, "explanation": "one sentence"}},
 {{"claim": "exact claim text", "assessment": "likely_false", "confidence": 90, "explanation": "one sentence"}}]

The "assessment" field MUST be one of: likely_true, likely_false, uncertain.
The "confidence" field MUST be an integer 0-100."""


def search_web(query, max_results=5):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        out = []
        for r in results:
            out.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "url": r.get("href", ""),
            })
        return out
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []


def lookup_wikipedia(query):
    if not query:
        return None
    try:
        base = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "titles": query,
            "redirects": 1,
        }
        headers = {"User-Agent": "ProofLayer/1.0"}
        resp = http_requests.get(base, params=params, timeout=8, headers=headers)
        resp.raise_for_status()
        pages = (resp.json().get("query") or {}).get("pages") or {}
        for pid, page in pages.items():
            if pid == "-1":
                continue
            extract = (page.get("extract") or "").strip()
            title = page.get("title", "")
            if extract:
                return {
                    "title": title,
                    "extract": extract[:800],
                    "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                }
        resp2 = http_requests.get(
            base,
            params={"action": "opensearch", "format": "json", "search": query, "limit": 1, "namespace": 0},
            timeout=8,
            headers=headers,
        )
        resp2.raise_for_status()
        data = resp2.json()
        if len(data) >= 2 and data[1]:
            title = data[1][0]
            params["titles"] = title
            r3 = http_requests.get(base, params=params, timeout=8, headers=headers)
            r3.raise_for_status()
            pages = (r3.json().get("query") or {}).get("pages") or {}
            for pid, page in pages.items():
                if pid == "-1":
                    continue
                extract = (page.get("extract") or "").strip()
                if extract:
                    return {
                        "title": page.get("title", title),
                        "extract": extract[:800],
                        "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                    }
    except Exception as exc:
        logger.warning("Wikipedia lookup failed for %r: %s", query, exc)
    return None


_ASSESSMENT_ALIASES = {
    "true": "likely_true",
    "likely true": "likely_true",
    "likelytrue": "likely_true",
    "probably_true": "likely_true",
    "probably true": "likely_true",
    "correct": "likely_true",
    "accurate": "likely_true",
    "false": "likely_false",
    "likely false": "likely_false",
    "likelyfalse": "likely_false",
    "probably_false": "likely_false",
    "probably false": "likely_false",
    "incorrect": "likely_false",
    "inaccurate": "likely_false",
    "misleading": "likely_false",
    "unknown": "uncertain",
    "unverifiable": "uncertain",
    "mixed": "uncertain",
    "partially_true": "uncertain",
    "partially true": "uncertain",
}

_VALID_ASSESSMENTS = {"likely_true", "likely_false", "uncertain"}


def _normalize_assessment(raw) -> str:
    if not raw:
        return "uncertain"
    v = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if v in _VALID_ASSESSMENTS:
        return v
    return _ASSESSMENT_ALIASES.get(v, "uncertain")


def _normalize_confidence(raw) -> int:
    try:
        if raw is None:
            return 50
        if isinstance(raw, str):
            raw = raw.strip().rstrip("%")
        v = int(float(raw))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, v))


def _build_assessed_claims(claims_raw: list, search_context: str) -> list:
    ollama_url = getattr(settings, "OLLAMA_URL", "http://ollama:11434")
    model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")

    claims_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims_raw))
    prompt = OLLAMA_ASSESS_PROMPT.format(
        search_context=search_context or "No search results available.",
        claims_list=claims_list,
    )

    try:
        response = http_requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=180,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            items = parsed[:len(claims_raw)]
        elif isinstance(parsed, dict):
            items = parsed.get("claims", [parsed])[:len(claims_raw)]
        else:
            raise ValueError(f"Unexpected type: {type(parsed)}")
        for item in items:
            if isinstance(item, dict):
                if "assessment" in item:
                    item["assessment"] = _normalize_assessment(str(item["assessment"]))
                else:
                    item["assessment"] = "uncertain"
                item["confidence"] = _normalize_confidence(item.get("confidence"))
        return items
    except Exception as exc:
        logger.warning("Ollama factcheck failed: %s", exc)
        return [
            {"claim": c, "assessment": "uncertain", "confidence": 0, "explanation": "LLM unavailable"}
            for c in claims_raw
        ]


def format_search_context(web_results: list, wiki_hits: list) -> str:
    lines = []
    if web_results:
        lines.append("Web search:")
        for r in web_results:
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("url", "")
            lines.append(f"[{title}] {body} ({url})")
    if wiki_hits:
        lines.append("")
        lines.append("Wikipedia:")
        for w in wiki_hits:
            lines.append(f"[{w.get('title','')}] {w.get('extract','')}")
    return "\n".join(lines)


def match_wiki(claim_text: str, wiki_hits: list):
    if not claim_text or not wiki_hits:
        return None
    ct = claim_text.lower()
    for w in wiki_hits:
        title = (w.get("title") or "").lower()
        if title and title in ct:
            return w
    return wiki_hits[0] if wiki_hits else None


def analyze_with_ollama(text):
    candidate_claims = extract_claim_sentences(text, max_claims=8)
    if not candidate_claims:
        return _fallback_sentence_split(text)

    search_query = " ".join(candidate_claims[:2])[:200]
    web_results = search_web(search_query)
    wiki_hits = []
    for c in candidate_claims[:4]:
        hit = lookup_wikipedia(c[:120])
        if hit:
            wiki_hits.append(hit)
    context = format_search_context(web_results, wiki_hits)

    assessed = _build_assessed_claims(candidate_claims, context)
    sources = [{"title": r["title"], "url": r["url"]} for r in web_results[:3] if r.get("url")]
    out = []
    for item in assessed:
        claim_text = (item.get("claim") or "").strip()
        wiki = match_wiki(claim_text, wiki_hits)
        out.append({**item, "sources": sources, "wikipedia": wiki})
    return out


def _fallback_sentence_split(text):
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 20]
    return [
        {"claim": s, "assessment": "uncertain", "confidence": 0, "explanation": "LLM unavailable",
         "sources": [], "wikipedia": None}
        for s in sentences[:8]
    ]


def check_google_fact_check(claim_text):
    api_key = getattr(settings, "GOOGLE_FACT_CHECK_KEY", None)
    if not api_key:
        return []

    try:
        response = http_requests.get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params={"query": claim_text, "key": api_key, "languageCode": "en"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("claims", [])[:3]:
            reviews = item.get("claimReview", [])
            if reviews:
                review = reviews[0]
                results.append({
                    "claim_text": item.get("text", ""),
                    "rating": review.get("textualRating", ""),
                    "url": review.get("url", ""),
                    "publisher": review.get("publisher", {}).get("name", ""),
                })
        return results
    except Exception as exc:
        logger.warning("Google Fact Check API failed: %s", exc)
        return []


def analyze_text(text):
    claims = analyze_with_ollama(text)
    entities = extract_entities(text)
    enriched = []
    for claim_obj in claims:
        fact_checks = check_google_fact_check(claim_obj.get("claim", ""))
        enriched.append({**claim_obj, "fact_checks": fact_checks})

    false_count = sum(1 for c in enriched if c.get("assessment") == "likely_false")
    uncertain_count = sum(1 for c in enriched if c.get("assessment") == "uncertain")
    total = len(enriched)

    if total == 0:
        overall = "no_claims"
    elif false_count / max(total, 1) >= 0.4:
        overall = "misleading"
    elif (false_count + uncertain_count) / max(total, 1) >= 0.5:
        overall = "mixed"
    else:
        overall = "mostly_accurate"

    return {
        "claims_count": total,
        "overall_verdict": overall,
        "claims": enriched,
        "entities": entities,
    }
