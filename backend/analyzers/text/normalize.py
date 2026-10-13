import re
import unicodedata
from collections import Counter

from analyzers.text.evasion import INVISIBLE, ODD_SPACES

CYR_TO_LAT = dict(zip("аеорсухіјѕԁԛԝАВЕНІЈКМОРСТХЅ", "aeopcyxijsdqwABEHIJKMOPCTXS"))
LAT_TO_CYR = {v: k for k, v in CYR_TO_LAT.items() if k in "аеорсухАВЕКМНОРСТХ"}
PUNCT = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "‛": "'",
        "′": "'",
        "`": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "«": '"',
        "»": '"',
        "–": "-",
        "—": "-",
        "―": "-",
        "‒": "-",
        "−": "-",
        "…": "...",
    }
)
TOKEN = re.compile(r"\S+")
SPACES = re.compile(r"\s+")


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    if name.startswith("CYRILLIC"):
        return "cyrillic"
    if name.startswith("LATIN"):
        return "latin"
    return None


def _repair_token(token: str) -> str:
    scripts = Counter(s for s in map(_script, token) if s)
    if len(scripts) < 2:
        return token
    major = scripts.most_common(1)[0][0]
    table = LAT_TO_CYR if major == "cyrillic" else CYR_TO_LAT
    return "".join(table.get(c, c) if _script(c) and _script(c) != major else c for c in token)


def normalize_for_model(text: str) -> str:
    text = "".join(" " if ch in ODD_SPACES else ch for ch in text if ch not in INVISIBLE and not 0xE0000 <= ord(ch) <= 0xE007F)
    text = unicodedata.normalize("NFKC", text).translate(PUNCT)
    text = TOKEN.sub(lambda m: _repair_token(m.group(0)), text)
    return SPACES.sub(" ", text).strip()
