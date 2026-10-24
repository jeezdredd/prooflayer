import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Hit:
    url: str
    title: str
    snippet: str


def _searxng(query: str, limit: int) -> list[Hit] | None:
    base = getattr(settings, "SEARXNG_URL", "").rstrip("/")
    if not base:
        return None
    resp = requests.get(f"{base}/search", params={"q": query, "format": "json"}, timeout=15)
    resp.raise_for_status()
    rows = resp.json().get("results", [])[:limit]
    return [Hit(r.get("url", ""), r.get("title", ""), r.get("content", "")) for r in rows if r.get("url")]


def _ddg(query: str, limit: int) -> list[Hit]:
    with DDGS() as ddgs:
        rows = list(ddgs.text(query, max_results=limit))
    return [Hit(r.get("href", ""), r.get("title", ""), r.get("body", "")) for r in rows if r.get("href")]


def _brave(query: str, limit: int) -> list[Hit] | None:
    key = getattr(settings, "BRAVE_SEARCH_API_KEY", "")
    if not key:
        return None
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json().get("web", {}).get("results", [])
    return [Hit(r.get("url", ""), r.get("title", ""), r.get("description", "")) for r in rows if r.get("url")]


PROVIDERS = {"searxng": _searxng, "ddg": _ddg, "brave": _brave}
WIKIPEDIA_LANGS = ("ru", "en", "fr")
USER_AGENT = "ProofLayer-Originality/1.0 (https://prooflayer.cloud)"


def wikipedia_lookup(query: str, lang: str, limit: int = 2) -> tuple[list[Hit], bool]:
    if not getattr(settings, "PLAGIARISM_WIKIPEDIA", True) or lang not in WIKIPEDIA_LANGS:
        return [], False
    try:
        resp = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "format": "json", "utf8": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json().get("query", {}).get("search", [])
    except Exception as exc:
        logger.warning("wikipedia search failed: %s", exc)
        return [], False
    return [Hit(f"https://{lang}.wikipedia.org/wiki/{r['title'].replace(' ', '_')}", r["title"], "") for r in rows if r.get("title")], True


def provider_chain() -> list[str]:
    configured = getattr(settings, "PLAGIARISM_SEARCH_PROVIDERS", ["searxng", "ddg"])
    return [p for p in configured if p in PROVIDERS]


def lookup(query: str, limit: int = 5) -> tuple[list[Hit], bool]:
    answered = False
    for name in provider_chain():
        try:
            hits = PROVIDERS[name](query, limit)
        except Exception as exc:
            logger.warning("plagiarism search via %s failed: %s", name, exc)
            continue
        if hits is None:
            continue
        answered = True
        if hits:
            return hits, True
    return [], answered


def search(query: str, limit: int = 5) -> list[Hit]:
    return lookup(query, limit)[0]
