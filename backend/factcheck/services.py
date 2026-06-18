import json
import logging

import requests as http_requests
from django.conf import settings

from factcheck.ner import extract_claim_sentences, extract_entities

logger = logging.getLogger(__name__)

OLLAMA_ASSESS_PROMPT = """Assess each factual claim listed below. Use web context if helpful.

Rules:
- "likely_true": matches well-known facts or confirmed by web context.
- "likely_false": contradicts known facts or refuted by web context.
- "uncertain": recent/ongoing or genuinely ambiguous.

Web context:
{search_context}

Claims to assess (assess ALL of them, in order):
{claims_list}

Respond ONLY with a JSON array, one object per claim, same order as above:
[{{"claim": "...", "assessment": "likely_true|likely_false|uncertain", "explanation": "one sentence"}}]"""


def search_web(query, max_results=5):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        snippets = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("href", "")
            snippets.append(f"[{title}] {body} ({url})")
        return "\n".join(snippets)
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return ""


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
            return parsed[:len(claims_raw)]
        if isinstance(parsed, dict):
            if "claims" in parsed:
                return parsed["claims"][:len(claims_raw)]
            return [parsed]
        raise ValueError(f"Unexpected type: {type(parsed)}")
    except Exception as exc:
        logger.warning("Ollama factcheck failed: %s", exc)
        return [{"claim": c, "assessment": "uncertain", "explanation": "LLM unavailable"} for c in claims_raw]


def analyze_with_ollama(text):
    candidate_claims = extract_claim_sentences(text, max_claims=8)
    if not candidate_claims:
        return _fallback_sentence_split(text)

    search_query = " ".join(candidate_claims[:2])[:200]
    search_context = search_web(search_query)

    return _build_assessed_claims(candidate_claims, search_context)


def _fallback_sentence_split(text):
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 20]
    return [{"claim": s, "assessment": "uncertain", "explanation": "LLM unavailable"} for s in sentences[:8]]


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
