import re
from collections import Counter

from analyzers.text.citations import bibliography_entries

UP = r"[A-ZÀ-ÖØ-ÝА-ЯЁ]"
LETTER = r"[^\W\d_]"
SURNAME = rf"{UP}{LETTER}*(?:[\-'’]{LETTER}+)*"
INITIALS = rf"(?:{UP}\.\s?(?:-{UP}\.\s?)?){{1,3}}"
FIRST_NAME = rf"{UP}{LETTER}+"

NUM_PREFIX = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s*")
URL = re.compile(r"https?://\S+")
YEAR_PAREN_DOT = re.compile(r"\((?:\d{4}[a-z]?|n\.d\.)(?:, [^)]{3,20})?\)\.")
YEAR_PAREN = re.compile(r"\(\d{4}[a-z]?\)")

LABELS = {
    "apa": "APA 7",
    "mla": "MLA 9",
    "chicago": "Chicago",
    "harvard": "Harvard",
    "ieee": "IEEE",
    "vancouver": "Vancouver",
    "gost": "ГОСТ Р 7.0.100-2018",
    "iso690": "ISO 690",
}
IN_TEXT = {
    "apa": "author-year",
    "harvard": "author-year",
    "chicago": "author-year",
    "mla": "author-page",
    "ieee": "numeric",
    "vancouver": "numeric",
}
ALPHABETICAL = {"apa", "mla", "chicago", "harvard", "gost", "iso690"}
NUMBERED = {"ieee", "vancouver"}
MIN_STYLE_SCORE = 2.0

FEATURES = {
    "apa": [
        (re.compile(rf"^{SURNAME}, {INITIALS}"), 1.0),
        (YEAR_PAREN_DOT, 2.0),
        (re.compile(r", & "), 0.5),
        (re.compile(r"https://doi\.org/"), 0.3),
    ],
    "harvard": [
        (re.compile(rf"^{SURNAME}, {INITIALS}"), 1.0),
        (re.compile(r"\(\d{4}[a-z]?\)\s(?!\.)"), 2.0),
        (re.compile(r"Available at:?", re.IGNORECASE), 1.5),
        (re.compile(r"\(Accessed", re.IGNORECASE), 1.5),
    ],
    "mla": [
        (re.compile(rf"^{SURNAME}, {FIRST_NAME}"), 1.0),
        (re.compile(r"[\"“][^\"”]+\.[\"”]"), 1.5),
        (re.compile(r", vol\. \d+"), 1.0),
        (re.compile(r", no\. \d+"), 0.5),
        (re.compile(r", \d{4}, pp?\. \d"), 1.5),
    ],
    "chicago": [
        (re.compile(rf"^{SURNAME}, {FIRST_NAME}"), 1.0),
        (re.compile(r"^[^.()]+\. \d{4}\. "), 2.0),
        (re.compile(r"\d+, no\. \d+ \(\d{4}\): \d"), 2.0),
        (re.compile(r"\d+ \(\d+\): \d+"), 1.0),
    ],
    "ieee": [
        (re.compile(r"^\s*\[\d+\]"), 1.5),
        (re.compile(rf"^\s*\[\d+\]\s*(?:{UP}\.\s?)+{UP}{LETTER}"), 2.0),
        (re.compile(r"[\"“][^\"”]+,[\"”]"), 1.5),
        (re.compile(r", vol\. \d+, no\. \d+, pp\. "), 0.5),
    ],
    "vancouver": [
        (re.compile(r"^\s*\d+\.\s"), 1.0),
        (re.compile(rf"^(?:\s*\d+\.\s*)?{SURNAME} {UP}{{1,3}}[,.]"), 2.0),
        (re.compile(r"\d{4}(?: [A-Z][a-z]{2})?;\s?\d+(?:\(\d+\))?:\s?\d+"), 2.0),
    ],
    "gost": [
        (re.compile(r"\.\s[–—-]\s"), 1.5),
        (re.compile(r"\s/\s"), 1.0),
        (re.compile(r"\b\d+\s?с\.|[–—-]\s?С\.\s?\d"), 1.0),
        (re.compile(r"дата обращения", re.IGNORECASE), 1.0),
        (re.compile(r"[А-ЯЁ]"), 0.5),
    ],
    "iso690": [
        (re.compile(r"^[A-ZÀ-Ý]{2,}[A-ZÀ-Ý\-]*,\s"), 2.5),
        (re.compile(r"\s:\s"), 0.5),
    ],
}


def cyrillic_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum("а" <= c.lower() <= "я" or c.lower() == "ё" for c in letters) / len(letters) if letters else 0.0


def detect_style(entry: str) -> str | None:
    if cyrillic_share(entry) > 0.5:
        return "gost"
    body = NUM_PREFIX.sub("", entry)
    scores = {}
    for style, features in FEATURES.items():
        target = entry if style in NUMBERED else body
        scores[style] = sum(weight for pattern, weight in features if pattern.search(target))
    style, score = max(scores.items(), key=lambda item: item[1])
    return style if score >= MIN_STYLE_SCORE else None


def _ends_ok(body: str) -> bool:
    stripped = body.rstrip()
    if not stripped:
        return False
    return stripped.endswith(".") or bool(URL.fullmatch(stripped.split()[-1]))


def _authors(body: str) -> str:
    stop = re.search(r"\(\d{4}|\(n\.d\.|[\"“]", body)
    if stop:
        return body[: stop.start()]
    initials = re.match(rf"^(.*?\b{UP}{{1,3}})\.\s", body)
    return initials.group(1) if initials else body.split(". ")[0]


def _doi_prefix(body: str) -> bool:
    return bool(re.search(r"\bdoi:\s*10\.", body, re.IGNORECASE))


def _apa(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(rf"{SURNAME}, {INITIALS}", body):
        issues.append("list authors as Surname, A. B.")
    if not YEAR_PAREN_DOT.search(body):
        issues.append("put the year in parentheses after the authors, followed by a period: (2019).")
    if re.search(r"\band\b", _authors(body)):
        issues.append("use & before the last author, not 'and'")
    if _doi_prefix(body):
        issues.append("write the DOI as https://doi.org/10...")
    if re.search(r"retrieved from", body, re.IGNORECASE):
        issues.append("APA 7 drops 'Retrieved from' before a link")
    return issues


def _harvard(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(rf"{SURNAME}, {INITIALS}", body):
        issues.append("list authors as Surname, A.")
    if not YEAR_PAREN.search(body):
        issues.append("put the year in parentheses after the authors: (2019)")
    if URL.search(body) and not re.search(r"available at", body, re.IGNORECASE):
        issues.append("introduce a link with 'Available at:'")
    if re.search(r"available at", body, re.IGNORECASE) and not re.search(r"\(accessed", body, re.IGNORECASE):
        issues.append("add (Accessed: 1 May 2024) after the link")
    return issues


def _mla(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(rf"{SURNAME}, {FIRST_NAME}", body):
        issues.append("give the first author as Last, First name")
    if re.search(r"\b(?:Vol\.|Volume|No\.|Number)\s?\d", body):
        issues.append("use lowercase vol. and no.")
    if re.match(r"[^()]+\(\d{4}\)\.", body):
        issues.append("MLA puts the year after the publisher or journal, not in parentheses after the author")
    if re.search(r"\bpg\.|\bp\.\s?\d+\s?[-–]\s?\d+", body):
        issues.append("page ranges take pp.")
    if re.search(r"[\"”][.,]", body):
        issues.append('put the period or comma inside the quotation marks: "Title."')
    return issues


def _chicago(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(rf"{SURNAME}, {FIRST_NAME}", body):
        issues.append("give the first author as Last, First name")
    if _doi_prefix(body):
        issues.append("write the DOI as https://doi.org/10...")
    return issues


def _ieee(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(r"^\s*\[\d+\]", entry):
        issues.append("number each entry in square brackets: [1]")
    if not re.match(rf"(?:{UP}\.\s?)+{UP}", body):
        issues.append("write initials before the surname: A. B. Surname")
    if re.search(r"[\"”],", body):
        issues.append('put the comma inside the quotation marks: "Title,"')
    if "&" in _authors(body):
        issues.append("use 'and' before the last author, not &")
    return issues


def _vancouver(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(r"^\s*\d+\.", entry):
        issues.append("number each entry: 1.")
    if re.search(rf"{SURNAME} (?:{UP}\.){{2,3}}|{SURNAME} {UP}\.,", body):
        issues.append("write initials without periods: Smith JA")
    if re.search(r"&|\band\b", _authors(body)):
        issues.append("separate authors with commas only, no 'and' or &")
    return issues


def _gost(entry: str, body: str) -> list[str]:
    issues = []
    if re.search(r"\.\s-\s", body):
        issues.append("области разделяются точкой и тире ( . – ), а не дефисом")
    if not re.match(rf"{SURNAME}, {INITIALS}", body) and re.match(rf"{SURNAME},? (?:{UP}\.\s?){{1,2}}", body):
        issues.append("фамилия и инициалы через запятую и с пробелами: Иванов, И. И.")
    if URL.search(body):
        if not re.search(r"URL:\s*https?://", body):
            issues.append("перед адресом пишется URL:")
        if not re.search(r"дата обращения:\s*\d{2}\.\d{2}\.\d{4}", body, re.IGNORECASE):
            issues.append("после адреса нужна (дата обращения: ДД.ММ.ГГГГ)")
    if re.search(r"\bстр\b", body):
        issues.append("страницы обозначаются «С. 45–67» или «256 с.», не «стр.»")
    return issues


def _iso690(entry: str, body: str) -> list[str]:
    issues = []
    if not re.match(r"^[A-ZÀ-Ý]{2,}", body):
        issues.append("nom de l'auteur en majuscules : DUPONT, Jean")
    if re.search(r"[^\s:]:\s", URL.sub("", body)):
        issues.append("espace avant les deux-points : Paris : Gallimard")
    return issues


CHECKS = {
    "apa": _apa,
    "harvard": _harvard,
    "mla": _mla,
    "chicago": _chicago,
    "ieee": _ieee,
    "vancouver": _vancouver,
    "gost": _gost,
    "iso690": _iso690,
}
END_PERIOD = {
    "gost": "запись заканчивается точкой",
    "iso690": "terminez la référence par un point",
}


def entry_issues(entry: str, style: str) -> list[str]:
    body = NUM_PREFIX.sub("", entry).strip()
    issues = CHECKS[style](entry, body)
    if not _ends_ok(body):
        issues.append(END_PERIOD.get(style, "end the entry with a period"))
    return issues


def _sort_key(entry: str) -> str:
    return NUM_PREFIX.sub("", entry).strip().lower()


def in_text_citations(text: str) -> dict:
    return {
        "author-year": re.findall(rf"\(({SURNAME})(?: et al\.| и др\.)?,? (\d{{4}})[a-z]?(?:, [^)]*)?\)", text),
        "author-page": re.findall(rf"\(({SURNAME})(?: et al\.)? (\d+(?:[-–]\d+)?)\)", text),
        "numeric": re.findall(r"\[(\d+)(?:\s?[,–-]\s?\d+)*(?:, [сcp]\.\s?\d+)?\]", text),
    }


def _list_issues(entries: list[str], rows: list[dict], dominant: str) -> list[str]:
    issues = []
    others = Counter(r["style"] for r in rows if r["style"] and r["style"] != dominant)
    for style, n in others.items():
        issues.append(f"{n} of {len(rows)} entries follow {LABELS[style]} while the list is mostly {LABELS[dominant]}")
    keys = [_sort_key(e) for e in entries]
    if dominant in ALPHABETICAL and len(keys) > 1 and keys != sorted(keys):
        issues.append("the list is not in alphabetical order by author")
    if dominant in NUMBERED:
        numbers = [int(m.group(1)) for m in (re.match(r"^\s*\[?(\d+)", e) for e in entries) if m]
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            issues.append("entries are not numbered 1, 2, 3 in order")
    return issues


def _citation_issues(text: str, entries: list[str], dominant: str | None) -> list[str]:
    issues = []
    found = in_text_citations(text)
    expected = IN_TEXT.get(dominant or "")
    used = max(found, key=lambda k: len(found[k]))
    if expected and found[used] and used != expected and not found[expected]:
        issues.append(f"in-text citations are {used}, but {LABELS[dominant]} uses {expected} citations")
    references = " ".join(entries).lower()
    orphans = sorted({name for name, _ in found["author-year"] if name.lower() not in references})
    if orphans:
        issues.append("cited in the text but missing from the list: " + ", ".join(orphans[:8]))
    beyond = sorted({int(n) for n in found["numeric"] if int(n) > len(entries)})
    if beyond:
        issues.append("numbered citations with no matching entry: " + ", ".join(f"[{n}]" for n in beyond[:8]))
    return issues


def check_format(text: str) -> dict | None:
    entries = bibliography_entries(text)
    if not entries:
        return None
    rows = []
    for entry in entries:
        style = detect_style(entry)
        rows.append({"entry": entry[:200], "style": style, "issues": entry_issues(entry, style) if style else []})
    counts = Counter(r["style"] for r in rows if r["style"])
    dominant = counts.most_common(1)[0][0] if counts else None
    if dominant is None:
        issues = ["no recognisable citation style in the reference list"]
    else:
        issues = _list_issues(entries, rows, dominant)
    issues += _citation_issues(text, entries, dominant)
    return {
        "style": dominant,
        "label": LABELS.get(dominant or "", "unknown"),
        "entries": rows,
        "issues": issues,
        "issue_count": len(issues) + sum(len(r["issues"]) for r in rows),
    }
