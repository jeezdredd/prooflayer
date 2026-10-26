import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

import requests
from django.conf import settings
from django.core.cache import cache

from .search import USER_AGENT

logger = logging.getLogger(__name__)

OPENALEX_URL = "https://api.openalex.org/works"
ARXIV_URL = "https://export.arxiv.org/api/query"
OPENALEX_FIELDS = (
    "id,doi,title,display_name,publication_year,authorships,primary_location,"
    "best_oa_location,open_access,locations,abstract_inverted_index"
)
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
PAPER_ENGINES = ("openalex", "arxiv")
PHRASE_WORDS = 8
MIN_PHRASE_WORDS = 6
OPENALEX_QUERY_BYTES = 2800
ARXIV_QUERY_BYTES = 1800
ARXIV_INTERVAL = 3.0
ARXIV_MAX_WAIT = 30.0
OPENALEX_SEARCH_CREDITS = 10
OPENALEX_BLOCK = 3600
ARXIV_BLOCK = 600
BLOCK_MIN = 60
BLOCK_MAX = 24 * 3600
MAX_AUTHORS = 10
MAX_FULLTEXT_URLS = 3
FREE_FULLTEXT_HOSTS = ("cyberleninka.ru",)
ARXIV_HOSTS = ("arxiv.org",)
WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
LATIN_RE = re.compile(r"[A-Za-z]")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/(\S+?)(?:v\d+)?$")
OPERATORS = {"AND", "OR", "NOT"}
TITLE_KEY_RE = re.compile(r"[\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Paper:
    engine: str
    url: str
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    abstract: str = ""
    fulltext: tuple[str, ...] = ()


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def key_phrase(sentence: str, size: int = PHRASE_WORDS) -> str:
    words = [w.lower() if w in OPERATORS else w.replace("’", "'") for w in WORD_RE.findall(sentence)]
    if len(words) <= size:
        return " ".join(words)
    best = max(range(len(words) - size + 1), key=lambda i: (sum(len(w) >= 7 for w in words[i:i + size]), -i))
    return " ".join(words[best:best + size])


def latin(phrase: str) -> bool:
    return len(LATIN_RE.findall(phrase)) > len(CYRILLIC_RE.findall(phrase))


def or_groups(terms: list[tuple[int, str]], budget: int) -> list[tuple[str, list[int]]]:
    groups: list[tuple[str, list[int]]] = []
    current: list[tuple[int, str]] = []
    for term in terms:
        candidate = " OR ".join(t for _, t in [*current, term])
        if current and len(quote(candidate)) > budget:
            groups.append((" OR ".join(t for _, t in current), [i for i, _ in current]))
            current = [term]
        else:
            current.append(term)
    if current:
        groups.append((" OR ".join(t for _, t in current), [i for i, _ in current]))
    return groups


def rebuild_abstract(index: dict | None) -> str:
    if not index:
        return ""
    placed = sorted((pos, word) for word, positions in index.items() for pos in positions or [])
    return " ".join(word for _, word in placed)


def _cache_key(engine: str, query: str, limit: int) -> str:
    return f"plag:{engine}:" + hashlib.sha1(f"{limit}|{query}".encode()).hexdigest()


def _block_key(engine: str) -> str:
    return f"plag:{engine}:blocked"


def blocked(engine: str) -> bool:
    return bool(cache.get(_block_key(engine)))


def block(engine: str, resp: requests.Response | None, default: int) -> None:
    seconds = default
    if resp is not None:
        for header in ("Retry-After", "X-RateLimit-Reset"):
            value = (resp.headers.get(header) or "").strip()
            if value.isdigit():
                seconds = int(value)
                break
    cache.set(_block_key(engine), 1, min(max(seconds, BLOCK_MIN), BLOCK_MAX))


def wait_turn(engine: str, interval: float = ARXIV_INTERVAL, max_wait: float = ARXIV_MAX_WAIT) -> bool:
    first = math.ceil(time.time() / interval)
    for slot in range(first, first + int(max_wait // interval) + 1):
        if cache.add(f"plag:{engine}:turn:{slot}", 1, int(max_wait + 2 * interval)):
            delay = slot * interval - time.time()
            if delay > 0:
                time.sleep(delay)
            return True
    return False


def fetch_turn(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in ARXIV_HOSTS):
        return True
    return not blocked("arxiv") and wait_turn("arxiv")


def _http_url(url: str | None) -> bool:
    return bool(url) and url.startswith(("http://", "https://"))


def _free_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in FREE_FULLTEXT_HOSTS)


def fulltext_urls(work: dict) -> tuple[str, ...]:
    best = work.get("best_oa_location") or {}
    candidates = [best.get("pdf_url"), best.get("landing_page_url") if best.get("is_oa") else None]
    candidates.append((work.get("open_access") or {}).get("oa_url"))
    for location in work.get("locations") or []:
        for url in (location.get("pdf_url"), location.get("landing_page_url")):
            if _http_url(url) and (location.get("is_oa") or _free_host(url)):
                candidates.append(url)
    urls: list[str] = []
    for url in candidates:
        if _http_url(url) and url not in urls:
            urls.append(url)
    return tuple(urls[:MAX_FULLTEXT_URLS])


def openalex_paper(work: dict) -> Paper | None:
    title = _clean(work.get("title") or work.get("display_name"))
    if not title:
        return None
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    doi = work.get("doi") or ""
    url = next((u for u in (doi, primary.get("landing_page_url"), work.get("id")) if _http_url(u)), "")
    if not url:
        return None
    authors = tuple(
        name for name in (_clean((a.get("author") or {}).get("display_name")) for a in work.get("authorships") or []) if name
    )
    year = work.get("publication_year")
    return Paper(
        engine="openalex",
        url=url,
        title=title,
        authors=authors[:MAX_AUTHORS],
        year=year if isinstance(year, int) else None,
        venue=_clean(source.get("display_name")),
        abstract=rebuild_abstract(work.get("abstract_inverted_index")),
        fulltext=fulltext_urls(work),
    )


def _remaining(resp: requests.Response) -> int | None:
    value = (resp.headers.get("X-RateLimit-Remaining") or "").strip()
    return int(value) if value.isdigit() else None


def openalex_search(query: str) -> list[Paper] | None:
    limit = settings.PLAGIARISM_OPENALEX_HITS
    key = _cache_key("openalex", query, limit)
    cached = cache.get(key)
    if cached is not None:
        return cached
    if blocked("openalex"):
        return None
    params = {"search": query, "per-page": limit, "select": OPENALEX_FIELDS}
    if settings.OPENALEX_MAILTO:
        params["mailto"] = settings.OPENALEX_MAILTO
    keys = [settings.OPENALEX_API_KEY, ""] if settings.OPENALEX_API_KEY else [""]
    resp = None
    for api_key in keys:
        headers = {"User-Agent": USER_AGENT}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = requests.get(OPENALEX_URL, params=params, headers=headers, timeout=settings.PLAGIARISM_OPENALEX_TIMEOUT)
        except requests.RequestException as exc:
            logger.warning("openalex search failed: %s", exc)
            return None
        if resp.status_code not in (401, 403):
            break
        logger.warning("openalex refused the api key (%s), retrying without it", resp.status_code)
    if resp.status_code == 429:
        logger.warning("openalex daily budget spent, pausing")
        block("openalex", resp, OPENALEX_BLOCK)
        return None
    if resp.status_code != 200:
        logger.warning("openalex search answered %s", resp.status_code)
        return None
    try:
        rows = resp.json().get("results") or []
    except ValueError as exc:
        logger.warning("openalex answer is not json: %s", exc)
        return None
    remaining = _remaining(resp)
    if remaining is not None and remaining < OPENALEX_SEARCH_CREDITS:
        block("openalex", resp, OPENALEX_BLOCK)
    papers = [p for p in (openalex_paper(w) for w in rows if isinstance(w, dict)) if p]
    cache.set(key, papers, settings.PLAGIARISM_ACADEMIC_CACHE)
    return papers


def parse_arxiv(content: bytes) -> list[Paper] | None:
    root = ElementTree.fromstring(content)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = _clean(entry.findtext(f"{ATOM}id"))
        if "/api/errors" in entry_id:
            return None
        match = ARXIV_ID_RE.search(entry_id)
        title = _clean(entry.findtext(f"{ATOM}title"))
        if not match or not title:
            continue
        arxiv_id = match.group(1)
        published = _clean(entry.findtext(f"{ATOM}published"))[:4]
        authors = tuple(
            name for name in (_clean(a.findtext(f"{ATOM}name")) for a in entry.findall(f"{ATOM}author")) if name
        )
        papers.append(Paper(
            engine="arxiv",
            url=f"https://arxiv.org/abs/{arxiv_id}",
            title=title,
            authors=authors[:MAX_AUTHORS],
            year=int(published) if published.isdigit() else None,
            venue=_clean(entry.findtext(f"{ARXIV_NS}journal_ref")) or "arXiv",
            abstract=_clean(entry.findtext(f"{ATOM}summary")),
            fulltext=(f"https://arxiv.org/pdf/{arxiv_id}",),
        ))
    return papers


def arxiv_search(query: str) -> list[Paper] | None:
    limit = settings.PLAGIARISM_ARXIV_HITS
    key = _cache_key("arxiv", query, limit)
    cached = cache.get(key)
    if cached is not None:
        return cached
    if blocked("arxiv") or not wait_turn("arxiv"):
        return None
    try:
        resp = requests.get(
            ARXIV_URL,
            params={"search_query": query, "start": 0, "max_results": limit},
            headers={"User-Agent": USER_AGENT},
            timeout=settings.PLAGIARISM_ARXIV_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("arxiv search failed: %s", exc)
        return None
    if resp.status_code in (429, 503):
        logger.warning("arxiv asked to slow down (%s), pausing", resp.status_code)
        block("arxiv", resp, ARXIV_BLOCK)
        return None
    if resp.status_code != 200:
        logger.warning("arxiv search answered %s", resp.status_code)
        return None
    try:
        papers = parse_arxiv(resp.content)
    except ElementTree.ParseError as exc:
        logger.warning("arxiv answer is not atom: %s", exc)
        return None
    if papers is None:
        logger.warning("arxiv rejected the query")
        return None
    cache.set(key, papers, settings.PLAGIARISM_ACADEMIC_CACHE)
    return papers


def title_key(title: str) -> str:
    return TITLE_KEY_RE.sub(" ", title).strip().casefold()


def _collect(groups: list[tuple[str, list[int]]], search, limit: int) -> tuple[list[Paper], set[int]]:
    papers: list[Paper] = []
    answered: set[int] = set()
    seen: set[str] = set()
    for query, members in groups:
        found = search(query)
        if found is None:
            continue
        answered.update(members)
        for paper in found:
            key = title_key(paper.title)
            if key not in seen:
                seen.add(key)
                papers.append(paper)
    return papers[:limit], answered


def openalex_lookup(phrases: list[str]) -> tuple[list[Paper], set[int]]:
    if not getattr(settings, "PLAGIARISM_OPENALEX", False):
        return [], set()
    terms = [(i, f'"{p}"') for i, p in enumerate(phrases) if len(p.split()) >= MIN_PHRASE_WORDS]
    return _collect(or_groups(terms, OPENALEX_QUERY_BYTES), openalex_search, settings.PLAGIARISM_OPENALEX_HITS)


def arxiv_lookup(phrases: list[str]) -> tuple[list[Paper], set[int]]:
    if not getattr(settings, "PLAGIARISM_ARXIV", False):
        return [], set()
    terms = [(i, f'all:"{p}"') for i, p in enumerate(phrases) if len(p.split()) >= MIN_PHRASE_WORDS and latin(p)]
    return _collect(or_groups(terms, ARXIV_QUERY_BYTES), arxiv_search, settings.PLAGIARISM_ARXIV_HITS)
