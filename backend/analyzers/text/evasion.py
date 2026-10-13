import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field

from lxml import etree

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

TOKEN_RE = re.compile(r"\S+")
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
        }


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


def scan_text(text: str) -> EvasionReport:
    report = EvasionReport()
    for ch in text:
        if ch in INVISIBLE:
            report.invisible[INVISIBLE[ch]] += 1
        elif ch in ODD_SPACES:
            report.odd_spaces += 1
        elif 0xE0000 <= ord(ch) <= 0xE007F:
            report.tag_characters += 1
        elif ch.isalpha():
            report.letters += 1
    if text.startswith("﻿"):
        report.invisible["zero-width no-break space"] -= 1
        if report.invisible["zero-width no-break space"] <= 0:
            del report.invisible["zero-width no-break space"]
    cleaned = "".join(ch for ch in text if ch not in INVISIBLE)
    for token in TOKEN_RE.findall(cleaned):
        if _is_mixed(token):
            report.mixed_script_words.append(token.strip(".,;:!?«»\"()[]"))
    return report


def _run_text(run) -> str:
    return "".join(t.text or "" for t in run.iter(f"{W}t"))


def scan_docx(path: str) -> list[dict]:
    hidden = []
    try:
        with zipfile.ZipFile(path) as zf:
            if "word/document.xml" not in zf.namelist():
                return hidden
            if zf.getinfo("word/document.xml").file_size > 50 * 1024 * 1024:
                return hidden
            root = etree.fromstring(zf.read("word/document.xml"), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except (zipfile.BadZipFile, etree.XMLSyntaxError, OSError, KeyError):
        return hidden
    for run in root.iter(f"{W}r"):
        text = _run_text(run).strip()
        if not text:
            continue
        rpr = run.find(f"{W}rPr")
        if rpr is None:
            continue
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
        if reasons:
            hidden.append({"text": text[:200], "reasons": reasons})
    return hidden
