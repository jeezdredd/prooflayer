import hashlib
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import trafilatura
from django.conf import settings
from django.core.cache import cache

from analyzers.text.language import detect_language, sentences
from common.documents import extract_pdf
from common.url_safety import UnsafeUrlError, safe_get

from .academic import Paper, arxiv_lookup, fetch_turn, key_phrase, openalex_lookup, title_key
from .models import PlagiarismReport
from .search import USER_AGENT, lookup, wikipedia_lookup
from .shingles import Token, copied_pairs, shingle_hashes, tokenize

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_PDF_BYTES = 15 * 1024 * 1024
PDF_PAGES = 60
QUERY_WORDS = 14
MIN_SENTENCE_WORDS = 10
SNIPPET_CHARS = 400
PAPER_TEXT_CHARS = 400_000
MIN_FULLTEXT_CHARS = 1000
FAILED_FETCH_CACHE = 3600
SHOWN_AUTHORS = 5


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
        resp = safe_get(url, timeout=12, headers={"User-Agent": USER_AGENT})
    except (UnsafeUrlError, Exception) as exc:
        logger.info("skip %s: %s", url, exc)
        return ""
    try:
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("Content-Type", "").lower()
        pdf = "pdf" in content_type or "octet-stream" in content_type
        if not pdf and "html" not in content_type and "text" not in content_type:
            return ""
        cap = MAX_PDF_BYTES if pdf else MAX_PAGE_BYTES
        chunks = []
        size = 0
        for chunk in resp.iter_content(65536):
            chunks.append(chunk)
            size += len(chunk)
            if size > cap:
                if pdf:
                    return ""
                break
        body = b"".join(chunks)
    except Exception as exc:
        logger.info("skip %s: %s", url, exc)
        return ""
    finally:
        resp.close()
    if body.startswith(b"%PDF"):
        try:
            return extract_pdf(body, PDF_PAGES)
        except Exception as exc:
            logger.info("unreadable pdf %s: %s", url, exc)
            return ""
    if pdf:
        return ""
    return trafilatura.extract(body.decode(resp.encoding or "utf-8", errors="replace")) or ""


def paper_text(paper: Paper) -> str:
    for url in paper.fulltext:
        key = "plag:fulltext:" + hashlib.sha1(url.encode()).hexdigest()
        text = cache.get(key)
        if text is None:
            if not fetch_turn(url):
                continue
            text = fetch_text(url)[:PAPER_TEXT_CHARS]
            cache.set(key, text, settings.PLAGIARISM_ACADEMIC_CACHE if text else FAILED_FETCH_CACHE)
        if len(text) >= MIN_FULLTEXT_CHARS:
            return text
    return ""


def shares_shingles(text: str, own: set[int]) -> bool:
    return bool(own.intersection(shingle_hashes(tokenize(text))))


@dataclass
class WebResult:
    status: str
    matches: list[dict] = field(default_factory=list)
    queries: int = 0
    engines: list[str] = field(default_factory=list)


def _match(url: str, title: str, engine: str, source: str, pairs) -> dict:
    return {
        "source": "web",
        "engine": engine,
        "kind": "exact",
        "kinds": ["exact"],
        "url": url,
        "title": title[:200],
        "spans": [own for own, _ in pairs],
        "pairs": [
            {"own": own, "text": source[found[0]:found[1]][:SNIPPET_CHARS] if found else "", "kind": "exact"}
            for own, found in pairs
        ],
    }


def paper_matches(
    papers: list[Paper], tokens: list[Token], hashes: list[int], skip: list[bool], compared: set[str],
) -> list[dict]:
    own = set(hashes)
    budget = settings.PLAGIARISM_PAPER_TEXTS
    titles: set[str] = set()
    matches = []
    for paper in papers:
        key = title_key(paper.title)
        if paper.url in compared or key in titles:
            continue
        compared.add(paper.url)
        titles.add(key)
        head = "\n".join(part for part in (paper.title, paper.abstract) if part)
        source = head
        wanted = paper.engine != "arxiv" or shares_shingles(head, own)
        if paper.fulltext and budget > 0 and wanted:
            budget -= 1
            full = paper_text(paper)
            if full:
                source = f"{head}\n{full}"
        pairs = copied_pairs(tokens, hashes, tokenize(source), skip)
        if pairs:
            match = _match(paper.url, paper.title, paper.engine, source, pairs)
            match.update({
                "authors": list(paper.authors[:SHOWN_AUTHORS]),
                "authors_total": len(paper.authors),
                "year": paper.year,
                "venue": paper.venue[:200],
            })
            matches.append(match)
    return matches


def web_matches(text: str, tokens: list[Token], hashes: list[int], skip: list[bool]) -> WebResult:
    queries = distinctive_sentences(text, getattr(settings, "PLAGIARISM_WEB_QUERIES", 8))
    if not queries:
        return WebResult(PlagiarismReport.WebStatus.SHORT)
    lang = detect_language(text)
    urls: dict[str, tuple[str, str]] = {}
    answered: set[int] = set()
    engines: set[str] = set()
    for i, sentence in enumerate(queries):
        query = query_for(sentence)
        hits, searched = lookup(query, limit=4)
        wiki, wiki_searched = wikipedia_lookup(query, lang.code if lang else "")
        if searched:
            engines.add("web")
            answered.add(i)
        if wiki_searched:
            engines.add("wikipedia")
            answered.add(i)
        for engine, found in (("web", hits), ("wikipedia", wiki)):
            for hit in found:
                if urlparse(hit.url).hostname and hit.url not in urls:
                    urls[hit.url] = (hit.title, engine)
    phrases = [key_phrase(sentence) for sentence in queries]
    papers: list[Paper] = []
    for engine, search in (("arxiv", arxiv_lookup), ("openalex", openalex_lookup)):
        found, found_answered = search(phrases)
        if found_answered:
            engines.add(engine)
            answered |= found_answered
            papers += found
    if not answered:
        return WebResult(PlagiarismReport.WebStatus.FAILED)
    matches = []
    tried: dict[str, int] = {}
    opened: dict[str, int] = {}
    for url, (title, engine) in list(urls.items())[: getattr(settings, "PLAGIARISM_WEB_PAGES", 12)]:
        tried[engine] = tried.get(engine, 0) + 1
        page = fetch_text(url)
        if not page:
            continue
        opened[engine] = opened.get(engine, 0) + 1
        pairs = copied_pairs(tokens, hashes, tokenize(page), skip)
        if pairs:
            matches.append(_match(url, title, engine, page, pairs))
    matches += paper_matches(papers, tokens, hashes, skip, set(urls))
    engines = {e for e in engines if not (tried.get(e) and not opened.get(e))}
    if not engines:
        return WebResult(PlagiarismReport.WebStatus.FAILED)
    return WebResult(PlagiarismReport.WebStatus.OK, matches, len(answered), sorted(engines))
