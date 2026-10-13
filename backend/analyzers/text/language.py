import re
from dataclasses import dataclass, field

WORD_RE = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?…])[\"»”)\]]*\s+(?=[\"«“(\[]?[A-ZА-ЯЁÀ-Ý0-9])")


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    vowels: str
    stopwords: frozenset[str]
    function_words: tuple[str, ...]
    script: str
    readability: str
    extra_letters: str = ""
    abbreviations: frozenset[str] = field(default_factory=frozenset)


RU = Language(
    code="ru",
    name="Russian",
    vowels="аеёиоуыэюя",
    script="cyrillic",
    readability="oborneva",
    stopwords=frozenset(
        "и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от "
        "меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж "
        "вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без "
        "будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один "
        "почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после "
        "над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед "
        "иногда лучше чуть том нельзя такой им более всегда конечно всю между это также является".split()
    ),
    function_words=(
        "и", "в", "не", "на", "что", "с", "как", "а", "но", "по", "к", "из", "за", "от", "для", "о", "же", "бы",
        "это", "так", "также", "который", "которые", "при", "если", "чтобы", "или", "уже", "ещё", "еще", "даже",
        "тоже", "ведь", "вот", "потому", "поэтому", "однако", "является", "таким", "образом", "кроме", "того",
    ),
)

EN = Language(
    code="en",
    name="English",
    vowels="aeiouy",
    script="latin",
    readability="flesch_kincaid",
    stopwords=frozenset(
        "the a an and or but if of to in on at by for with from as is are was were be been being it its this that "
        "these those he she they we you i me my our your his her their them not no do does did have has had will "
        "would can could should may might must there here what which who whom when where why how all any each "
        "some such than then so too very just also into about over after before because while".split()
    ),
    function_words=(
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "as", "is", "was", "that",
        "this", "it", "not", "be", "by", "from", "at", "which", "however", "moreover", "furthermore", "therefore",
        "additionally", "overall", "also", "thus", "while", "although", "because", "so", "very", "really",
    ),
)

FR = Language(
    code="fr",
    name="French",
    vowels="aeiouyàâäéèêëîïôöùûüÿœæ",
    script="latin",
    readability="kandel_moles",
    extra_letters="àâäçéèêëîïôöùûüÿœæ",
    stopwords=frozenset(
        "le la les un une des du de d l et ou mais donc or ni car que qui quoi dont où à au aux en dans par pour sur "
        "avec sans sous chez ce cet cette ces il elle ils elles on nous vous je tu me te se lui leur leurs mon ma mes "
        "ton ta tes son sa ses notre nos votre vos est sont était être avoir a ont avait fait plus pas ne n y aussi "
        "très comme si tout tous toute toutes".split()
    ),
    function_words=(
        "le", "la", "les", "de", "des", "du", "et", "à", "en", "un", "une", "que", "qui", "dans", "pour", "par",
        "sur", "pas", "ne", "est", "il", "ce", "avec", "plus", "mais", "ou", "donc", "ainsi", "cependant",
        "néanmoins", "toutefois", "également", "aussi", "car", "lorsque", "puisque", "afin",
    ),
)

LANGUAGES: dict[str, Language] = {lang.code: lang for lang in (RU, EN, FR)}

CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def sentences(text: str) -> list[str]:
    parts = []
    for block in re.split(r"\n\s*\n|\r\n\s*\r\n", text):
        block = " ".join(block.split())
        if not block:
            continue
        parts.extend(s.strip() for s in SENTENCE_RE.split(block) if s.strip())
    return parts


def detect_language(text: str) -> Language | None:
    tokens = [w.lower() for w in words(text[:20000])]
    if len(tokens) < 8:
        return None
    sample = "".join(tokens)
    cyr = len(CYRILLIC_RE.findall(sample))
    lat = len(LATIN_RE.findall(sample))
    candidates = [lang for lang in LANGUAGES.values() if (lang.script == "cyrillic") == (cyr > lat)]
    if not candidates:
        return None
    scores = {lang.code: sum(1 for t in tokens if t in lang.stopwords) for lang in candidates}
    best = max(scores, key=scores.get)
    if scores[best] < max(2, len(tokens) * 0.03):
        return None
    return LANGUAGES[best]


def syllables(word: str, lang: Language) -> int:
    lowered = word.lower()
    if lang.code == "ru":
        return max(1, sum(1 for ch in lowered if ch in lang.vowels))
    groups = re.findall(f"[{lang.vowels}]+", lowered)
    count = len(groups)
    if lang.code == "en" and lowered.endswith("e") and not lowered.endswith(("le", "ee")) and count > 1:
        count -= 1
    if lang.code == "fr" and lowered.endswith(("e", "es", "ent")) and count > 1:
        count -= 1
    return max(1, count)
