import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field

from lxml import etree
from wordfreq import zipf_frequency

CYRILLIC_LOOKALIKES = set("аеорсухіјѕԁԛԝАВЕНІЈКМОРСТХЅ")
LATIN_LOOKALIKES = set("aeopcyxijsdqwABEHIJKMOPCTXS")
GREEK_LOOKALIKES = set("αεορτυνικΑΒΕΗΙΚΜΝΟΡΤΥΧΖ")

INVISIBLE = {
    "​": "zero-width space",
    "‌": "zero-width non-joiner",
    "‍": "zero-width joiner",
    "‎": "left-to-right mark",
    "‏": "right-to-left mark",
    "⁠": "word joiner",
    "⁡": "invisible function application",
    "⁢": "invisible times",
    "⁣": "invisible separator",
    "⁤": "invisible plus",
    "﻿": "zero-width no-break space",
    "­": "soft hyphen",
    "᠎": "Mongolian vowel separator",
    "؜": "Arabic letter mark",
    "͏": "combining grapheme joiner",
}
ODD_SPACES = {chr(c) for c in range(0x2000, 0x200B)} | {" ", " ", "　", "⠀"}

LOOKALIKE_PUNCT = {
    "\u2024": "one dot leader",
    "\ufe52": "small full stop",
    "\uff0e": "fullwidth full stop",
    "\u0589": "Armenian full stop",
    "\u06d4": "Arabic full stop",
    "\ua4f8": "Lisu tone mark (looks like a full stop)",
    "\ua4f9": "Lisu tone mark (looks like a comma)",
    "\ufe50": "small comma",
    "\uff0c": "fullwidth comma",
    "\u060c": "Arabic comma",
    "\uff1a": "fullwidth colon",
    "\uff1b": "fullwidth semicolon",
    "\uff01": "fullwidth exclamation mark",
    "\uff1f": "fullwidth question mark",
}
CJK_RANGES = ((0x3040, 0x30FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF))
CJK_TOLERANCE = 20
STYLED_RANGES = ((0x1D400, 0x1D7FF), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A), (0x24B6, 0x24E9))
COMMON_WORD_ZIPF = 4.0
WORD_LANGS = ("en", "ru", "fr")
COMMON_MARKS = {
    chr(c)
    for c in (0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x0306, 0x0307, 0x0308, 0x030A, 0x030B, 0x030C, 0x0327, 0x0328)
}

TOKEN_RE = re.compile(r"\S+")
PLAIN_SPACE = " \n\r\t"
SHOWN_MARK = "\u00b7"
EXAMPLE_REACH = 20
MAX_EXAMPLES = 10
EXAMPLE_KINDS = ("invisible", "odd_space", "tag", "stray_mark", "punct")
TRIM = ".,;:!?()[]\"«»"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WHITE = {"FFFFFF", "FEFEFE", "FDFDFD", "FCFCFC"}
TINY_HALF_POINTS = 4


@dataclass
class EvasionReport:
    mixed_script_words: list[str] = field(default_factory=list)
    invisible: Counter = field(default_factory=Counter)
    odd_spaces: int = 0
    tag_characters: int = 0
    hidden_runs: list[dict] = field(default_factory=list)
    letters: int = 0
    lookalike_punctuation: Counter = field(default_factory=Counter)
    stray_marks: int = 0
    styled_letter_words: list[str] = field(default_factory=list)
    examples: dict[str, list[str]] = field(default_factory=dict)

    @property
    def invisible_total(self) -> int:
        return sum(self.invisible.values())

    @property
    def hidden_characters(self) -> int:
        return sum(len(r["text"]) for r in self.hidden_runs)

    def strength(self) -> float:
        mixed = len(self.mixed_script_words)
        score = 0.0
        if mixed >= 3:
            score = max(score, 0.95)
        elif mixed:
            score = max(score, 0.7)
        if self.invisible_total >= 5 or self.tag_characters:
            score = max(score, 0.95)
        elif self.invisible_total:
            score = max(score, 0.6)
        if self.hidden_characters >= 30:
            score = max(score, 0.97)
        elif self.hidden_characters:
            score = max(score, 0.7)
        if self.odd_spaces >= 10 and self.letters and self.odd_spaces / max(1, self.letters) > 0.005:
            score = max(score, 0.8)
        punct = sum(self.lookalike_punctuation.values())
        if punct >= 3:
            score = max(score, 0.9)
        elif punct:
            score = max(score, 0.6)
        if self.stray_marks >= 3:
            score = max(score, 0.9)
        styled = len(self.styled_letter_words)
        if styled >= 2:
            score = max(score, 0.95)
        elif styled:
            score = max(score, 0.7)
        return score

    def as_evidence(self) -> dict:
        return {
            "mixed_script_words": self.mixed_script_words[:20],
            "mixed_script_count": len(self.mixed_script_words),
            "invisible_characters": dict(self.invisible),
            "odd_spaces": self.odd_spaces,
            "tag_characters": self.tag_characters,
            "hidden_runs": self.hidden_runs[:10],
            "hidden_characters": self.hidden_characters,
            "lookalike_punctuation": dict(self.lookalike_punctuation),
            "stray_marks": self.stray_marks,
            "styled_letter_words": self.styled_letter_words[:20],
            **{f"{kind}_words": self.examples.get(kind, []) for kind in EXAMPLE_KINDS},
        }

    def add_example(self, kind: str, example: str):
        found = self.examples.setdefault(kind, [])
        if example and example not in found and len(found) < MAX_EXAMPLES:
            found.append(example)


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    if name.startswith("CYRILLIC"):
        return "cyrillic"
    if name.startswith("LATIN"):
        return "latin"
    if name.startswith("GREEK"):
        return "greek"
    return "other"


def _is_mixed(token: str) -> bool:
    for part in re.split(r"[-–—/'’.]", token):
        letters = [c for c in part if c.isalpha()]
        if len(letters) < 3:
            continue
        scripts = Counter(_script(c) for c in letters)
        scripts.pop(None, None)
        if len(scripts) < 2:
            continue
        major, _ = scripts.most_common(1)[0]
        minority = [c for c in letters if _script(c) != major]
        lookalikes = {"cyrillic": LATIN_LOOKALIKES | GREEK_LOOKALIKES, "latin": CYRILLIC_LOOKALIKES | GREEK_LOOKALIKES}.get(major, set())
        if minority and all(c in lookalikes for c in minority):
            return True
    return False


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in CJK_RANGES)


def _styled_letter(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in STYLED_RANGES)


def _is_common_word(word: str) -> bool:
    return any(zipf_frequency(word, lang) >= COMMON_WORD_ZIPF for lang in WORD_LANGS)


def _stray_marks(text: str, report: EvasionReport) -> int:
    count = 0
    for token in TOKEN_RE.findall(text):
        decomposed = unicodedata.normalize("NFD", token)
        odd = sum(1 for ch in decomposed if unicodedata.combining(ch) and ch not in COMMON_MARKS)
        if not odd:
            continue
        bare = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip(TRIM).lower()
        if bare.isalpha() and _is_common_word(unicodedata.normalize("NFC", bare)):
            count += odd
            report.add_example("stray_mark", token.strip(TRIM))
    return count


def _example(text: str, index: int, show: str) -> str:
    start = index
    while start > 0 and index - start < EXAMPLE_REACH and text[start - 1] not in PLAIN_SPACE:
        start -= 1
    end = index + 1
    while end < len(text) and end - index < EXAMPLE_REACH and text[end] not in PLAIN_SPACE:
        end += 1
    left = "".join(ch for ch in text[start:index] if ch not in INVISIBLE)
    right = "".join(ch for ch in text[index + 1:end] if ch not in INVISIBLE)
    return f"{left}{show}{right}".strip(TRIM)


def scan_text(text: str) -> EvasionReport:
    report = EvasionReport()
    cjk = sum(1 for ch in text if _is_cjk(ch))
    latin_text = cjk < CJK_TOLERANCE
    for i, ch in enumerate(text):
        if latin_text and ch in LOOKALIKE_PUNCT:
            report.lookalike_punctuation[LOOKALIKE_PUNCT[ch]] += 1
            report.add_example("punct", _example(text, i, ch))
        if ch in INVISIBLE:
            report.invisible[INVISIBLE[ch]] += 1
            if i > 0:
                report.add_example("invisible", _example(text, i, SHOWN_MARK))
        elif ch in ODD_SPACES:
            report.odd_spaces += 1
            report.add_example("odd_space", _example(text, i, SHOWN_MARK))
        elif 0xE0000 <= ord(ch) <= 0xE007F:
            report.tag_characters += 1
            report.add_example("tag", _example(text, i, SHOWN_MARK))
        elif ch.isalpha():
            report.letters += 1
    if text.startswith("﻿"):
        report.invisible["zero-width no-break space"] -= 1
        if report.invisible["zero-width no-break space"] <= 0:
            del report.invisible["zero-width no-break space"]
    if latin_text:
        report.stray_marks = _stray_marks(text, report)
    cleaned = "".join(ch for ch in text if ch not in INVISIBLE)
    for token in TOKEN_RE.findall(cleaned):
        letters = [c for c in token if c.isalpha()]
        styled = sum(1 for c in letters if _styled_letter(c))
        if latin_text and styled and styled < len(letters):
            report.styled_letter_words.append(token.strip(".,;:!?()[]\"«»"))
        if _is_mixed(token):
            report.mixed_script_words.append(token.strip(".,;:!?«»\"()[]"))
    return report


def _run_text(run) -> str:
    return "".join(t.text or "" for t in run.iter(f"{W}t"))


def _hidden_reasons(rpr) -> list[str]:
    reasons = []
    vanish = rpr.find(f"{W}vanish")
    if vanish is not None and vanish.get(f"{W}val", "true") not in ("0", "false"):
        reasons.append("hidden")
    color = rpr.find(f"{W}color")
    if color is not None and (color.get(f"{W}val") or "").upper() in WHITE:
        highlight = rpr.find(f"{W}highlight")
        shading = rpr.find(f"{W}shd")
        dark_background = (highlight is not None and highlight.get(f"{W}val") not in (None, "none", "white")) or (
            shading is not None and (shading.get(f"{W}fill") or "auto").upper() not in ("AUTO", "FFFFFF")
        )
        if not dark_background:
            reasons.append("white text")
    size = rpr.find(f"{W}sz")
    if size is not None:
        try:
            if int(size.get(f"{W}val", "24")) < TINY_HALF_POINTS:
                reasons.append("tiny font")
        except ValueError:
            pass
    return reasons


def _hidden_runs(path: str) -> list[tuple[str, list[str]]]:
    try:
        with zipfile.ZipFile(path) as zf:
            if "word/document.xml" not in zf.namelist():
                return []
            if zf.getinfo("word/document.xml").file_size > 50 * 1024 * 1024:
                return []
            root = etree.fromstring(zf.read("word/document.xml"), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except (zipfile.BadZipFile, etree.XMLSyntaxError, OSError, KeyError):
        return []
    found = []
    for run in root.iter(f"{W}r"):
        text = _run_text(run).strip()
        if not text:
            continue
        rpr = run.find(f"{W}rPr")
        if rpr is None:
            continue
        reasons = _hidden_reasons(rpr)
        if reasons:
            found.append((text, reasons))
    return found


def scan_docx(path: str) -> list[dict]:
    return [{"text": text[:200], "reasons": reasons} for text, reasons in _hidden_runs(path)]


def hidden_docx_texts(path: str) -> list[str]:
    return [text for text, _ in _hidden_runs(path)]


def strip_hidden(text: str, hidden: list[str]) -> str:
    for run in sorted(hidden, key=len, reverse=True):
        text = text.replace(run, "", 1)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
