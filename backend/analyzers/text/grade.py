import math
from dataclasses import dataclass
from functools import lru_cache

from wordfreq import word_frequency, zipf_frequency

from .language import Language, sentences, syllables, words
from .normalize import normalize_for_model

UNIVERSITY_BASE = 11

RARE_ZIPF_BY_LEVEL = [
    (4, 3.6),
    (7, 3.1),
    (9, 2.8),
    (11, 2.5),
    (99, 2.1),
]
RU_BOOKISH_ZIPF_BY_LEVEL = [
    (4, 4.4),
    (7, 4.2),
    (9, 4.0),
    (11, 3.7),
    (99, 3.0),
]
RU_PLAIN_RARE_ZIPF_BY_LEVEL = [
    (7, 2.1),
    (11, 2.0),
    (99, 1.6),
]
RARE_SHARE_ALERT = {"school": 0.07, "university": 0.12}
RU_RARE_SHARE_ALERT = {"school": 0.04, "university": 0.07}
STRESS_MARKS = str.maketrans("", "", "̀́")
MIN_CONTENT_WORDS = 35
RU_BOOKISH_ROOTS = (
    "парадигм", "детермин", "ретроспект", "социо", "интерпрет", "декомпоз", "концепт", "идентичн", "легитим",
    "имманент", "дискурс", "рефлекси", "экзистенц", "когнитив", "метакогнит", "онтолог", "эпистем", "гносеолог",
    "квинтэссенц", "амбивалент", "коннотац", "имплицит", "эксплицит", "релевант", "превалир", "нивелир", "апеллир",
    "перманент", "синерг", "методолог", "оптимизир", "структурир", "верифи", "валидн",
)
RU_NOUN_ENDINGS = (
    "", "а", "я", "о", "е", "ь", "ы", "и", "у", "ю", "ой", "ей", "ою", "ею", "ом", "ем", "ам", "ям", "ами", "ями",
    "ах", "ях", "ов", "ев", "ью", "ие", "ия", "ии", "ию", "ием", "ий", "иям", "иями", "иях", "ье", "ья", "ьи", "ьем",
)
RU_ADJECTIVE_ENDINGS = (
    "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие", "ого", "его", "ому", "ему", "ым", "им", "ую", "юю",
    "ых", "их", "ыми", "ими",
)
RU_VERB_ENDINGS = (
    "ть", "ться", "л", "ла", "ло", "ли", "лся", "лась", "лись", "ет", "ют", "ут", "ит", "ят", "ешь", "ишь", "ете",
    "ите", "ется", "ются", "ится", "ятся", "ать", "ять", "ить", "еть", "овать", "ировать", "ую", "уют", "ует", "уя",
)
RU_ENDINGS = tuple(sorted(set(RU_NOUN_ENDINGS + RU_ADJECTIVE_ENDINGS + RU_VERB_ENDINGS), key=len, reverse=True))
RU_MIN_STEM = 4
READABILITY_BANDS = ((4, "primary"), (9, "middle"), (11, "senior"))
RU_READABILITY_BANDS = ((10, "plain"), (15, "textbook"))


def level_label(level: int | None) -> str:
    if not level:
        return "not set"
    if level <= UNIVERSITY_BASE:
        return f"school year {level}"
    return f"university year {level - UNIVERSITY_BASE}"


def readability_band(grade: float, lang_code: str | None = None) -> str:
    if lang_code == "ru":
        for top, band in RU_READABILITY_BANDS:
            if grade <= top:
                return band
        return "adult"
    for top, band in READABILITY_BANDS:
        if grade <= top:
            return band
    return "university"


def _by_level(table: list[tuple[int, float]], level: int) -> float:
    for top, value in table:
        if level <= top:
            return value
    return table[-1][1]


def rare_threshold(level: int, lang_code: str = "") -> float:
    if lang_code == "ru":
        return _by_level(RU_BOOKISH_ZIPF_BY_LEVEL, level)
    return _by_level(RARE_ZIPF_BY_LEVEL, level)


def _ru_stems(word: str) -> set[str]:
    stems = {word}
    for ending in RU_ENDINGS:
        if ending and word.endswith(ending) and len(word) - len(ending) >= RU_MIN_STEM:
            stems.add(word[: -len(ending)])
    return stems


@lru_cache(maxsize=50_000)
def lexeme_zipf(word: str) -> float:
    word = word.replace("ё", "е")
    best = word_frequency(word, "ru")
    for stem in _ru_stems(word):
        best = max(best, sum(word_frequency(stem + ending, "ru") for ending in RU_ENDINGS))
    return round(math.log10(best * 1e9), 2) if best > 0 else 0.0


def word_zipf(word: str, lang_code: str) -> float:
    if lang_code == "ru":
        return lexeme_zipf(word)
    return zipf_frequency(word, lang_code)


def is_beyond_level(word: str, zipf: float, level: int, lang_code: str) -> bool:
    if zipf <= 0:
        return False
    if lang_code != "ru":
        return zipf < rare_threshold(level, lang_code)
    if zipf < _by_level(RU_PLAIN_RARE_ZIPF_BY_LEVEL, level):
        return True
    return zipf < rare_threshold(level, lang_code) and any(root in word for root in RU_BOOKISH_ROOTS)


@dataclass
class Readability:
    grade: float
    words_per_sentence: float
    syllables_per_word: float


def readability(text: str, lang: Language) -> Readability | None:
    sents = sentences(text)
    tokens = words(text)
    if len(sents) < 3 or len(tokens) < 50:
        return None
    asl = len(tokens) / len(sents)
    asw = sum(syllables(w, lang) for w in tokens) / len(tokens)
    if lang.readability == "flesch_kincaid":
        grade = 0.39 * asl + 11.8 * asw - 15.59
    elif lang.readability == "oborneva":
        grade = 0.5 * asl + 8.4 * asw - 15.59
    else:
        fre = 207 - 1.015 * asl - 73.6 * asw
        grade = (100 - fre) / 6.0 + 1
    return Readability(round(max(0.0, grade), 1), round(asl, 1), round(asw, 1))


def readability_grade(text: str, lang: Language) -> float | None:
    found = readability(text, lang)
    return None if found is None else found.grade


@dataclass
class GradeFit:
    level: int
    language: str
    readability_grade: float | None
    rare_threshold: float
    rare_share: float
    rare_words: list[str]
    content_words: int
    mismatch: float
    words_per_sentence: float | None = None
    syllables_per_word: float | None = None

    def as_evidence(self) -> dict:
        return {
            "level": self.level,
            "level_label": level_label(self.level),
            "language": self.language,
            "readability_grade": self.readability_grade,
            "readability_band": None if self.readability_grade is None else readability_band(self.readability_grade, self.language),
            "words_per_sentence": self.words_per_sentence,
            "syllables_per_word": self.syllables_per_word,
            "rare_zipf_threshold": self.rare_threshold,
            "rare_word_share": round(self.rare_share, 4),
            "beyond_level_words": self.rare_words[:25],
            "content_words": self.content_words,
            "mismatch": round(self.mismatch, 3),
        }


def _content_words(text: str, lang: Language) -> list[str]:
    out = []
    for sentence in sentences(text):
        for i, token in enumerate(words(sentence)):
            lowered = token.lower()
            if lowered in lang.stopwords or len(lowered) < 4:
                continue
            if i > 0 and token[:1].isupper():
                continue
            out.append(lowered)
    return out


def assess(text: str, lang: Language, level: int) -> GradeFit | None:
    text = normalize_for_model(text).translate(STRESS_MARKS)
    content = _content_words(text, lang)
    if len(content) < MIN_CONTENT_WORDS:
        return None
    seen = {}
    rare_hits = 0
    for word in content:
        zipf = seen.get(word)
        if zipf is None:
            zipf = word_zipf(word.replace("ё", "е"), lang.code)
            seen[word] = zipf
        if is_beyond_level(word, zipf, level, lang.code):
            rare_hits += 1
    rare_share = rare_hits / len(content)
    rare_words = sorted({w for w, z in seen.items() if is_beyond_level(w, z, level, lang.code)}, key=lambda w: seen[w])
    found = readability(text, lang)
    grade = None if found is None else found.grade

    band = "school" if level <= UNIVERSITY_BASE else "university"
    alert = (RU_RARE_SHARE_ALERT if lang.code == "ru" else RARE_SHARE_ALERT)[band]
    share_excess = max(0.0, rare_share - alert) / alert
    expected_grade = min(level, 16)
    grade_excess = 0.0 if grade is None else max(0.0, grade - (expected_grade + 4)) / 4
    mismatch = min(1.0, 0.6 * min(share_excess, 1.5) / 1.5 + 0.4 * min(grade_excess, 1.0))
    if len(rare_words) < 4:
        mismatch = min(mismatch, 0.3)
    return GradeFit(
        level=level,
        language=lang.code,
        readability_grade=grade,
        rare_threshold=rare_threshold(level, lang.code),
        rare_share=rare_share,
        rare_words=rare_words,
        content_words=len(content),
        mismatch=mismatch,
        words_per_sentence=None if found is None else found.words_per_sentence,
        syllables_per_word=None if found is None else found.syllables_per_word,
    )
