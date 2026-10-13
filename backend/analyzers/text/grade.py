from dataclasses import dataclass

from wordfreq import zipf_frequency

from .language import Language, sentences, syllables, words

UNIVERSITY_BASE = 11

RARE_ZIPF_BY_LEVEL = [
    (4, 3.6),
    (7, 3.1),
    (9, 2.8),
    (11, 2.5),
    (99, 2.1),
]
RARE_SHARE_ALERT = {"school": 0.07, "university": 0.12}
MIN_CONTENT_WORDS = 35


def level_label(level: int | None) -> str:
    if not level:
        return "not set"
    if level <= UNIVERSITY_BASE:
        return f"school year {level}"
    return f"university year {level - UNIVERSITY_BASE}"


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
        if 0 < zipf < threshold:
            rare_hits += 1
    rare_share = rare_hits / len(content)
    rare_words = sorted({w for w, z in seen.items() if 0 < z < threshold}, key=lambda w: seen[w])
    grade = readability_grade(text, lang)

    band = "school" if level <= UNIVERSITY_BASE else "university"
    share_excess = max(0.0, rare_share - RARE_SHARE_ALERT[band]) / RARE_SHARE_ALERT[band]
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
