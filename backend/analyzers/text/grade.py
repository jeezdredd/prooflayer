from dataclasses import dataclass

from wordfreq import zipf_frequency

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
RARE_SHARE_ALERT = {"school": 0.07, "university": 0.12}
RU_RARE_SHARE_ALERT = {"school": 0.04, "university": 0.07}
STRESS_MARKS = str.maketrans("", "", "\u0300\u0301")
MIN_CONTENT_WORDS = 35
RU_PLAIN_RARE_ZIPF = 2.3
RU_BOOKISH_ROOTS = (
    "изац", "ифик", "ифиц", "парадигм", "детермин", "ретроспект", "социо", "трансформ", "интерпрет",
    "концепт", "идентичн", "легитим", "имманент", "дискурс", "рефлекс", "экзистенц", "когнитив",
    "метакогнит", "онтолог", "эпистем", "гносеолог", "квинтэссенц", "амбивалент", "коннотац", "имплицит",
    "эксплицит", "релевант", "превалир", "нивелир", "апеллир", "перманент", "синерг", "методолог",
    "оптимизир", "структурир", "интеграц", "верифи", "валидн", "компетенц", "автономн",
    "функциональн", "аналитическ", "системн", "фундаментальн", "целесообразн", "перспективн",
)
READABILITY_BANDS = ((4, "primary"), (9, "middle"), (11, "senior"))


def level_label(level: int | None) -> str:
    if not level:
        return "not set"
    if level <= UNIVERSITY_BASE:
        return f"school year {level}"
    return f"university year {level - UNIVERSITY_BASE}"


def readability_band(grade: float) -> str:
    for top, band in READABILITY_BANDS:
        if grade <= top:
            return band
    return "university"


def is_beyond_level(word: str, zipf: float, threshold: float, lang_code: str) -> bool:
    if not 0 < zipf < threshold:
        return False
    if lang_code != "ru":
        return True
    return zipf < RU_PLAIN_RARE_ZIPF or any(root in word for root in RU_BOOKISH_ROOTS)


def rare_threshold(level: int) -> float:
    for top, zipf in RARE_ZIPF_BY_LEVEL:
        if level <= top:
            return zipf
    return RARE_ZIPF_BY_LEVEL[-1][1]


def readability_grade(text: str, lang: Language) -> float | None:
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
    return round(max(0.0, min(grade, 20.0)), 1)


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

    def as_evidence(self) -> dict:
        return {
            "level": self.level,
            "level_label": level_label(self.level),
            "language": self.language,
            "readability_grade": self.readability_grade,
            "readability_band": None if self.readability_grade is None else readability_band(self.readability_grade),
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
    threshold = rare_threshold(level)
    seen = {}
    rare_hits = 0
    for word in content:
        zipf = seen.get(word)
        if zipf is None:
            zipf = zipf_frequency(word.replace("ё", "е"), lang.code)
            seen[word] = zipf
        if is_beyond_level(word, zipf, threshold, lang.code):
            rare_hits += 1
    rare_share = rare_hits / len(content)
    rare_words = sorted({w for w, z in seen.items() if is_beyond_level(w, z, threshold, lang.code)}, key=lambda w: seen[w])
    grade = readability_grade(text, lang)

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
        rare_threshold=threshold,
        rare_share=rare_share,
        rare_words=rare_words,
        content_words=len(content),
        mismatch=mismatch,
    )
