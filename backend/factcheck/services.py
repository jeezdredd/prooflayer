import json
import logging

import requests as http_requests
from django.conf import settings

logger = logging.getLogger(__name__)

OLLAMA_FACTCHECK_PROMPT = """You are a fact-checking assistant. Analyze the text below for factual claims.

Use the web search results provided as context to assess each claim.

For each sentence containing a verifiable factual claim, return an assessment.
Respond ONLY with a JSON array:
[
  {{"claim": "...", "assessment": "likely_true|likely_false|uncertain", "explanation": "one sentence"}}
]

Web search context:
{search_context}

Text to analyze:
{text}"""


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


def analyze_with_ollama(text):
    ollama_url = getattr(settings, "OLLAMA_URL", "http://ollama:11434")
    model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")

    search_context = search_web(text[:200])
    prompt = OLLAMA_FACTCHECK_PROMPT.format(
        search_context=search_context or "No search results available.",
        text=text[:2000],
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
            return parsed
        if isinstance(parsed, dict):
            if "claims" in parsed:
                return parsed["claims"]
            return [parsed]
        raise ValueError(f"Unexpected type: {type(parsed)}")
    except Exception as exc:
        logger.warning("Ollama factcheck failed: %s", exc)
        return _fallback_sentence_split(text)


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
    }
