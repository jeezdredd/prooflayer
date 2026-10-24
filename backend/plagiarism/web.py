import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import trafilatura
from django.conf import settings

from analyzers.text.language import detect_language, sentences
from common.url_safety import UnsafeUrlError, safe_get

from .models import PlagiarismReport
from .search import lookup, wikipedia_lookup
from .shingles import Token, copied_pairs, tokenize

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 3 * 1024 * 1024
QUERY_WORDS = 14
MIN_SENTENCE_WORDS = 10
SNIPPET_CHARS = 400


def distinctive_sentences(text: str, limit: int) -> list[str]:
    scored = []
    for order, sentence in enumerate(sentences(text)):
        tokens = tokenize(sentence)
        if len(tokens) < MIN_SENTENCE_WORDS:
            continue
        longish = sum(1 for t in tokens if len(t.norm) >= 7) / len(tokens)
        scored.append((longish + min(len(tokens), 30) / 60, order, sentence))
    best = sorted(scored, key=lambda c: -c[0])[:limit]
    return [sentence for _, _, sentence in sorted(best, key=lambda c: c[1])]


def query_for(sentence: str) -> str:
    words = sentence.split()
    return '"' + " ".join(words[:QUERY_WORDS]).strip(' ,;:"«»') + '"'


def fetch_text(url: str) -> str:
    try:
        resp = safe_get(url, timeout=12, headers={"User-Agent": "ProofLayer-Originality/1.0"})
    except (UnsafeUrlError, Exception) as exc:
        logger.info("skip %s: %s", url, exc)
        return ""
    try:
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type and "text" not in content_type:
            return ""
        body = b""
        for chunk in resp.iter_content(65536):
            body += chunk
            if len(body) > MAX_PAGE_BYTES:
                break
    finally:
        resp.close()
    return trafilatura.extract(body.decode(resp.encoding or "utf-8", errors="replace")) or ""


@dataclass
class WebResult:
    status: str
    matches: list[dict] = field(default_factory=list)
    queries: int = 0
    engines: list[str] = field(default_factory=list)


def web_matches(text: str, tokens: list[Token], hashes: list[int], skip: list[bool]) -> WebResult:
    queries = distinctive_sentences(text, getattr(settings, "PLAGIARISM_WEB_QUERIES", 8))
    if not queries:
        return WebResult(PlagiarismReport.WebStatus.SHORT)
    lang = detect_language(text)
    urls: dict[str, str] = {}
    answered = 0
    engines: set[str] = set()
    for sentence in queries:
        query = query_for(sentence)
        hits, searched = lookup(query, limit=4)
        wiki, wiki_searched = wikipedia_lookup(query, lang.code if lang else "")
        if searched:
            engines.add("web")
        if wiki_searched:
            engines.add("wikipedia")
        if searched or wiki_searched:
            answered += 1
        for hit in hits + wiki:
            host = urlparse(hit.url).hostname or ""
            if host and hit.url not in urls:
                urls[hit.url] = hit.title
    if not answered:
        return WebResult(PlagiarismReport.WebStatus.FAILED)
    matches = []
    fetched = 0
    for url, title in list(urls.items())[: getattr(settings, "PLAGIARISM_WEB_PAGES", 12)]:
        page = fetch_text(url)
        if not page:
            continue
        fetched += 1
        pairs = copied_pairs(tokens, hashes, tokenize(page), skip)
        if pairs:
            matches.append({
                "source": "web",
                "kind": "exact",
                "kinds": ["exact"],
                "url": url,
                "title": title[:200],
                "spans": [own for own, _ in pairs],
                "pairs": [
                    {"own": own, "text": page[found[0]:found[1]][:SNIPPET_CHARS] if found else "", "kind": "exact"}
                    for own, found in pairs
                ],
            })
    if urls and not fetched:
        return WebResult(PlagiarismReport.WebStatus.FAILED)
    return WebResult(PlagiarismReport.WebStatus.OK, matches, answered, sorted(engines))
