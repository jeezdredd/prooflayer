import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import requests
from django.conf import settings

from common.url_safety import UnsafeUrlError, safe_get
from plagiarism import academic
from plagiarism.search import search

logger = logging.getLogger(__name__)

USER_AGENT = "ProofLayer-Citations/1.0 (+https://prooflayer.cloud)"
TIMEOUT = 8
ARXIV_TIMEOUT = 20
MAX_REFERENCES = 20
MAX_QUOTES = 3
WORKERS = 6

FOUND, MISSING, UNCHECKED = "found", "missing", "unchecked"
WEIGHT = {"doi": 1.0, "arxiv": 1.0, "isbn": 1.0, "bibliography": 0.6, "url": 0.4, "quote": 0.25}
FLAG_MISSING_WEIGHT = 1.0
FLAG_MISSING_SHARE = 0.34

DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>«»]+", re.IGNORECASE)
ARXIV = re.compile(r"arxiv[:\s/]*(?:abs/)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
ISBN = re.compile(r"ISBN(?:-1[03])?:?\s*([0-9Xx][0-9Xx\- ]{8,16}[0-9Xx])")
URL = re.compile(r"https?://[^\s<>\"'«»]+")
QUOTE = re.compile(r"[«“\"]([^«»“”\"\n]{40,320})[»”\"]")
YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
WORD = re.compile(r"\w+", re.UNICODE)
HEADING = re.compile(
    r"^\s*(references|bibliography|works cited|sources|literature|список литературы|список использованной литературы|"
    r"литература|источники|библиография|bibliographie|références|sources et références)\s*:?\s*$",
    re.IGNORECASE,
)
TRAILING = ".,;:)]}"
COVERED_HOSTS = {"doi.org", "dx.doi.org", "arxiv.org", "export.arxiv.org"}


@dataclass
class Reference:
    kind: str
    value: str
    status: str = UNCHECKED
    detail: str = ""

    def as_evidence(self) -> dict:
        return {"kind": self.kind, "value": self.value[:200], "status": self.status, "detail": self.detail[:200]}


def isbn_valid(raw: str) -> bool:
    digits = raw.replace("-", "").replace(" ", "").upper()
    if len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(digits))
        return total % 11 == 0
    if len(digits) == 13 and digits.isdigit():
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digits))
        return total % 10 == 0
    return False


def bibliography_entries(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        if HEADING.match(line):
            entries = [ln for ln in lines[i + 1 :] if ln]
            return [e for e in entries if len(e.split()) >= 6 and YEAR.search(e)][:MAX_REFERENCES]
    return []


def extract(text: str) -> list[Reference]:
    refs: list[Reference] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str, status: str = UNCHECKED, detail: str = ""):
        key = (kind, value.lower())
        if key not in seen and len(refs) < MAX_REFERENCES:
            seen.add(key)
            refs.append(Reference(kind, value, status, detail))

    for match in DOI.finditer(text):
        add("doi", match.group(0).rstrip(TRAILING))
    for match in ARXIV.finditer(text):
        add("arxiv", match.group(1))
    for match in ISBN.finditer(text):
        digits = match.group(1).replace("-", "").replace(" ", "").upper()
        if isbn_valid(digits):
            add("isbn", digits)
        else:
            add("isbn", digits, MISSING, "check digit does not match, no real book has this ISBN")
    for match in URL.finditer(text):
        url = match.group(0).rstrip(TRAILING)
        if (urlparse(url).hostname or "").lower() not in COVERED_HOSTS:
            add("url", url)
    for entry in bibliography_entries(text):
        if not (DOI.search(entry) or URL.search(entry) or ISBN.search(entry)):
            add("bibliography", entry)
    quotes = sorted({m.group(1).strip() for m in QUOTE.finditer(text) if len(m.group(1).split()) >= 8}, key=len, reverse=True)
    for q in quotes[:MAX_QUOTES]:
        add("quote", q)
    return refs


def _get(url: str, **params) -> requests.Response:
    return requests.get(url, params=params or None, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)


def _openalex(query: str) -> requests.Response | None:
    if academic.blocked("openalex"):
        return None
    params = {"search": query, "per-page": 5}
    if settings.OPENALEX_MAILTO:
        params["mailto"] = settings.OPENALEX_MAILTO
    headers = {"User-Agent": USER_AGENT}
    if settings.OPENALEX_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OPENALEX_API_KEY}"
    resp = requests.get(academic.OPENALEX_URL, params=params, headers=headers, timeout=TIMEOUT)
    if resp.status_code == 429:
        academic.block("openalex", resp, academic.OPENALEX_BLOCK)
        return None
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if isinstance(remaining, str) and remaining.strip().isdigit() and int(remaining) < academic.OPENALEX_SEARCH_CREDITS:
        academic.block("openalex", resp, academic.OPENALEX_BLOCK)
    return resp


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text) if len(w) > 2]


TITLE_PATTERNS = [
    re.compile(r"[\"“«]([^\"”»]{6,})[\"”»]"),
    re.compile(r"\(\d{4}[a-z]?\)\.?\s*(.+?)[.?!](?:\s|$)"),
    re.compile(r"^[^.()]+\. \d{4}\. (.+?)\.\s"),
    re.compile(r"^[^,]+, (?:\S\.\s?){1,3}\s*(.+?)(?: [:/] |\. [–—-] )"),
    re.compile(r"^(?:\d+\.\s*)?.*?\b[A-Z]{1,3}\.\s(.+?)\.\s"),
]


GOST_AUTHORS = re.compile(r"^(?:[А-ЯЁ][а-яё\-]+,?\s(?:[А-ЯЁ]\.\s?){1,3},?\s*)+")
GOST_TAIL = re.compile(r"\s*(?://|\.\s*[–—-]\s|\.\s+[А-ЯЁ][А-Яа-яё]{0,6}\.?\s*:)")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
NUMBERING = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s*")
AUTHOR_PATTERNS = (
    re.compile(r"^([A-ZА-ЯЁ][\w'\-]+),\s*(?:[A-ZА-ЯЁ]\.|[A-ZА-ЯЁ][a-zа-яё]+[.,])"),
    re.compile(r"^([A-ZА-ЯЁ][\w'\-]+)\s+(?:[A-ZА-ЯЁ]\.\s?){1,3}"),
    re.compile(r"^(?:[A-Z]\.\s?){1,3}\s*([A-Z][\w'\-]+)"),
    re.compile(r"^([A-Z][\w'\-]+)\s+[A-Z]{1,3}[,.]"),
)
PAGE_OPENS = "page opens"
PAGE_NOT_FOUND = "page not found"
NOT_COVERED = "not covered by open catalogues"


def guess_title(entry: str) -> str:
    body = re.sub(r"^\s*(?:\[\d+\]|\d+[.)])\s*", "", entry)
    authors = GOST_AUTHORS.match(body)
    if authors:
        title = GOST_TAIL.split(body[authors.end():], maxsplit=1)[0].strip().rstrip(".")
        if len(_tokens(title)) >= 2:
            return title
    for pattern in TITLE_PATTERNS:
        match = pattern.search(body)
        if match and len(_tokens(match.group(1))) >= 2:
            return match.group(1).strip()
    return YEAR.sub(" ", body)


def _covered(words: list[str], text: str) -> bool:
    present = set(_tokens(text))
    return len(words) >= 2 and sum(w in present for w in words) / len(words) >= 0.8


def title_matches(title: str, entry: str) -> bool:
    return _covered(_tokens(title), entry) or _covered(_tokens(guess_title(entry)), title)


def check_doi(ref: Reference):
    resp = _get(f"https://doi.org/api/handles/{quote(ref.value, safe='/')}")
    code = resp.json().get("responseCode") if resp.status_code in (200, 404) else None
    if code == 1:
        ref.status, ref.detail = FOUND, "registered DOI"
    elif code == 100:
        ref.status, ref.detail = MISSING, "no DOI with this number is registered"


def check_arxiv(ref: Reference):
    if academic.blocked("arxiv") or not academic.wait_turn("arxiv"):
        return
    resp = requests.get(academic.ARXIV_URL, params={"id_list": ref.value}, headers={"User-Agent": USER_AGENT}, timeout=ARXIV_TIMEOUT)
    if resp.status_code in (429, 503):
        academic.block("arxiv", resp, academic.ARXIV_BLOCK)
        return
    if resp.status_code != 200:
        return
    titles = [" ".join(t.split()) for t in re.findall(r"<title>(.*?)</title>", resp.text, re.S)[1:]]
    if titles and titles[0] and titles[0] != "Error":
        ref.status, ref.detail = FOUND, titles[0]
    else:
        ref.status, ref.detail = MISSING, "no arXiv paper with this id"


def check_isbn(ref: Reference):
    resp = _get(f"https://openlibrary.org/isbn/{ref.value}.json")
    if resp.status_code == 200:
        ref.status, ref.detail = FOUND, str(resp.json().get("title", "listed in Open Library"))
        return
    books = _get("https://www.googleapis.com/books/v1/volumes", q=f"isbn:{ref.value}")
    if books.status_code != 200:
        return
    items = books.json().get("items") or []
    if items:
        ref.status, ref.detail = FOUND, str(items[0].get("volumeInfo", {}).get("title", "listed in Google Books"))
    elif resp.status_code == 404:
        ref.status, ref.detail = MISSING, "not in Open Library or Google Books"


def check_url(ref: Reference):
    try:
        resp = safe_get(ref.value, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    except UnsafeUrlError as exc:
        if str(exc) == "Invalid URL":
            ref.status, ref.detail = MISSING, "domain does not exist"
        return
    try:
        if resp.status_code < 400:
            ref.status, ref.detail = FOUND, PAGE_OPENS
        elif resp.status_code in (404, 410):
            ref.status, ref.detail = MISSING, PAGE_NOT_FOUND
    finally:
        resp.close()


def first_author(entry: str) -> str | None:
    body = NUMBERING.sub("", entry).strip()
    for pattern in AUTHOR_PATTERNS:
        match = pattern.match(body)
        if match:
            return match.group(1)
    return None


def author_matches(entry: str, authors: list[str]) -> bool:
    surname = first_author(entry)
    names = " ".join(a for a in authors if a)
    if not surname or not names:
        return True
    if CYRILLIC.search(surname) and not CYRILLIC.search(names):
        return True
    return surname.lower() in names.lower()


def _openalex_authors(work: dict) -> list[str]:
    return [(a.get("author") or {}).get("display_name") or "" for a in work.get("authorships") or []]


def _crossref_authors(item: dict) -> list[str]:
    return [" ".join(filter(None, (a.get("given"), a.get("family"), a.get("name")))) for a in item.get("author") or []]


def check_bibliography(ref: Reference):
    query = YEAR.sub(" ", ref.value)[:240]
    answered = False
    openalex = _openalex(guess_title(ref.value)[:200])
    if openalex is not None and openalex.status_code == 200:
        answered = True
        for work in openalex.json().get("results", []):
            title = work.get("title") or work.get("display_name") or ""
            if title and title_matches(title, ref.value) and author_matches(ref.value, _openalex_authors(work)):
                ref.status, ref.detail = FOUND, title
                return
    crossref = _get("https://api.crossref.org/works", **{"query.bibliographic": query, "rows": 3})
    if crossref.status_code == 200:
        answered = True
        for item in crossref.json().get("message", {}).get("items", []):
            title = " ".join(item.get("title") or [])
            if title and title_matches(title, ref.value) and author_matches(ref.value, _crossref_authors(item)):
                ref.status, ref.detail = FOUND, title
                return
    title = guess_title(ref.value)
    words = _tokens(title)
    for hit in search(f'"{title[:200]}"', limit=5):
        if _covered(words, f"{hit.title} {hit.snippet}"):
            ref.status, ref.detail = FOUND, hit.url
            return
    if CYRILLIC.search(ref.value):
        ref.detail = NOT_COVERED
        return
    if answered:
        ref.status, ref.detail = MISSING, "no matching work in OpenAlex or Crossref"


def check_quote(ref: Reference):
    hits = search(f'"{ref.value}"', limit=3)
    words = _tokens(ref.value)
    for hit in hits:
        text = set(_tokens(f"{hit.title} {hit.snippet}"))
        if words and sum(w in text for w in words) / len(words) >= 0.6:
            ref.status, ref.detail = FOUND, hit.url
            return
    if hits:
        ref.status, ref.detail = MISSING, "no page with this wording"


CHECKS = {
    "doi": check_doi,
    "arxiv": check_arxiv,
    "isbn": check_isbn,
    "url": check_url,
    "bibliography": check_bibliography,
    "quote": check_quote,
}


def _verify_one(ref: Reference) -> Reference:
    if ref.status != UNCHECKED:
        return ref
    try:
        CHECKS[ref.kind](ref)
    except Exception as exc:
        logger.info("citation check %s %s failed: %s", ref.kind, ref.value[:80], exc)
    return ref


def verify(refs: list[Reference]) -> list[Reference]:
    if not refs:
        return []
    with ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(_verify_one, refs))


@dataclass
class CitationReport:
    references: list[Reference]

    @property
    def missing_weight(self) -> float:
        return sum(WEIGHT[r.kind] for r in self.references if r.status == MISSING)

    @property
    def checked_weight(self) -> float:
        return sum(WEIGHT[r.kind] for r in self.references if r.status in (FOUND, MISSING))

    @property
    def missing_share(self) -> float:
        return self.missing_weight / self.checked_weight if self.checked_weight else 0.0

    @property
    def flagged(self) -> bool:
        return self.missing_weight >= FLAG_MISSING_WEIGHT and self.missing_share >= FLAG_MISSING_SHARE

    def confidence(self) -> float:
        if not self.flagged:
            return round(1 - self.missing_share, 3)
        extra = self.missing_weight - FLAG_MISSING_WEIGHT
        return round(min(0.95, 0.6 + 0.25 * self.missing_share + 0.05 * extra), 3)

    def as_evidence(self) -> dict:
        counts = {s: sum(r.status == s for r in self.references) for s in (FOUND, MISSING, UNCHECKED)}
        return {
            "references": [r.as_evidence() for r in self.references],
            "counts": counts,
            "missing_share": round(self.missing_share, 3),
        }


def check_citations(text: str) -> CitationReport:
    return CitationReport(verify(extract(text)))
