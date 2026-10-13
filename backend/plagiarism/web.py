import logging
from urllib.parse import urlparse

import trafilatura
from django.conf import settings

from analyzers.text.language import sentences
from common.url_safety import UnsafeUrlError, safe_get

from .search import search
from .shingles import covered_spans, shingle_hashes, tokenize

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 3 * 1024 * 1024
QUERY_WORDS = 14
MIN_SENTENCE_WORDS = 10


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


def web_matches(text: str) -> tuple[list[dict], int]:
    queries = distinctive_sentences(text, getattr(settings, "PLAGIARISM_WEB_QUERIES", 8))
    urls: dict[str, str] = {}
    for sentence in queries:
        for hit in search(query_for(sentence), limit=4):
            host = urlparse(hit.url).hostname or ""
            if host and hit.url not in urls:
                urls[hit.url] = hit.title
    tokens = tokenize(text)
    hashes = shingle_hashes(tokens)
    matches = []
    for url, title in list(urls.items())[: getattr(settings, "PLAGIARISM_WEB_PAGES", 12)]:
        page = fetch_text(url)
        if not page:
            continue
        spans = covered_spans(tokens, hashes, set(shingle_hashes(tokenize(page))))
        if spans:
            matches.append({
                "source": "web",
                "kind": "exact",
                "url": url,
                "title": title[:200],
                "spans": spans,
            })
    return matches, len(queries)
