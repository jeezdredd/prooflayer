import re
from dataclasses import dataclass
from statistics import median

from analyzers.text.citations import bibliography_entries
from analyzers.text.language import Language, words

CUES = {
    "thesis": {
        "ru": ("я считаю", "я думаю", "на мой взгляд", "по моему мнению", "по-моему", "я уверен", "я убежден", "мне кажется", "я согласен", "я не согласен"),
        "en": ("i believe", "i think", "in my opinion", "in my view", "i agree", "i disagree", "i am convinced", "it seems to me", "i would argue"),
        "fr": ("je pense", "je crois", "à mon avis", "selon moi", "je suis convaincu", "il me semble", "je suis d'accord", "je ne suis pas d'accord"),
    },
    "connector": {
        "ru": ("во-первых", "во-вторых", "в-третьих", "кроме того", "например", "следовательно", "с одной стороны", "с другой стороны", "докажу", "аргумент"),
        "en": ("firstly", "secondly", "thirdly", "furthermore", "moreover", "for example", "for instance", "on the one hand", "on the other hand", "therefore"),
        "fr": ("premièrement", "deuxièmement", "d'abord", "ensuite", "de plus", "par exemple", "d'une part", "d'autre part", "en effet", "donc"),
    },
    "conclusion": {
        "ru": ("таким образом", "в заключение", "подводя итог", "итак", "в итоге", "можно сделать вывод"),
        "en": ("in conclusion", "to conclude", "to sum up", "in summary", "all in all", "overall"),
        "fr": ("en conclusion", "pour conclure", "en somme", "en résumé", "finalement", "pour finir"),
    },
    "sequence": {
        "ru": ("однажды", "потом", "затем", "вдруг", "через некоторое время", "на следующий день", "после этого", "в тот день"),
        "en": ("once upon", "one day", "then", "suddenly", "after that", "the next day", "later", "that day"),
        "fr": ("un jour", "puis", "soudain", "tout à coup", "le lendemain", "plus tard", "ce jour-là", "il était une fois"),
    },
    "work": {
        "ru": ("в рассказе", "в повести", "в романе", "в сказке", "в произведении", "в стихотворении", "главный герой", "главная героиня", "героиня", "персонаж"),
        "en": ("the story", "the novel", "the tale", "the poem", "the book", "the main character", "the protagonist", "the hero", "the character"),
        "fr": ("le récit", "le roman", "le conte", "la nouvelle", "le poème", "le personnage", "le héros", "l'héroïne", "le protagoniste"),
    },
    "analysis": {
        "ru": ("автор показывает", "автор использует", "автор хочет", "тема", "темы", "тему", "идея", "идею", "образ", "образа", "символ*", "композиц*", "эпитет*", "метафор*", "художественн*"),
        "en": ("the author shows", "the author uses", "the writer", "theme*", "symbol*", "imagery", "metaphor*", "the message", "represents", "conveys"),
        "fr": ("l'auteur montre", "l'auteur utilise", "l'écrivain", "thème*", "symbol*", "métaphor*", "le message", "représente", "exprime"),
    },
    "spatial": {
        "ru": ("на переднем плане", "на заднем плане", "на картине", "слева", "справа", "вдали", "посередине", "изображен*", "художник"),
        "en": ("in the foreground", "in the background", "in the picture", "on the left", "on the right", "in the distance", "in the middle", "the painting", "the artist"),
        "fr": ("au premier plan", "à l'arrière-plan", "sur le tableau", "à gauche", "à droite", "au loin", "au milieu", "le peintre", "le tableau"),
    },
    "greeting": {
        "ru": ("дорогой", "дорогая", "здравствуй", "уважаемый", "уважаемая", "привет"),
        "en": ("dear", "hello", "hi"),
        "fr": ("cher", "chère", "bonjour", "salut", "madame", "monsieur"),
    },
    "signoff": {
        "ru": ("с уважением", "твой друг", "твоя подруга", "до встречи", "пиши", "обнимаю", "целую"),
        "en": ("best regards", "yours sincerely", "yours truly", "kind regards", "love,", "your friend", "best wishes", "see you"),
        "fr": ("cordialement", "bien à vous", "je t'embrasse", "bisous", "ton ami", "ton amie", "à bientôt", "amicalement"),
    },
    "section": {
        "ru": ("введение", "заключение", "основная часть", "содержание", "глава", "цель работы", "задачи", "актуальность"),
        "en": ("introduction", "conclusion", "abstract", "methods", "results", "discussion", "chapter", "background"),
        "fr": ("introduction", "conclusion", "sommaire", "chapitre", "problématique", "plan", "résumé"),
    },
}
FIRST_PERSON = {
    "ru": re.compile(r"(?<!\w)(я|мне|меня|мной|мой|моя|мое|мои|мы|нас|нам)(?!\w)"),
    "en": re.compile(r"\b(i|me|my|mine|we|us|our)\b"),
    "fr": re.compile(r"(?<!\w)(je|j'|moi|mon|ma|mes|nous|nos|notre)(?!\w)"),
}
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\s?%|\b(?:1[89]|20)\d{2}\b")
DIALOGUE = re.compile(r"^\s*[—–-]\s?\S|^\s*[«\"“]", re.MULTILINE)

LABELS = {
    "argument": {"en": "argumentative essay", "ru": "сочинение-рассуждение", "fr": "dissertation argumentative"},
    "narrative": {"en": "narrative", "ru": "сочинение-повествование", "fr": "récit"},
    "retelling": {"en": "retelling of a story", "ru": "пересказ / изложение", "fr": "résumé d'un récit"},
    "analysis": {"en": "literary analysis", "ru": "анализ произведения", "fr": "commentaire littéraire"},
    "description": {"en": "description", "ru": "сочинение-описание", "fr": "description"},
    "report": {"en": "research paper or report", "ru": "реферат / доклад", "fr": "exposé ou rapport"},
    "letter": {"en": "letter", "ru": "письмо", "fr": "lettre"},
    "poem": {"en": "poem", "ru": "стихотворение", "fr": "poème"},
    "other": {"en": "general text", "ru": "текст общего типа", "fr": "texte général"},
}
EXPECTS_SOURCES = {"report"}
MIN_SCORE = 1.5
GENRE_CUES = {
    "argument": ("thesis", "connector", "conclusion"),
    "narrative": ("sequence",),
    "retelling": ("work", "sequence"),
    "analysis": ("analysis", "work"),
    "description": ("spatial",),
    "report": ("section",),
}
FIRST_PERSON_CUE = {"ru": "рассказ от первого лица", "en": "first-person account", "fr": "récit à la première personne"}
DIALOGUE_CUE = {"ru": "диалог", "en": "dialogue", "fr": "dialogue"}
FIRST_PERSON_RATE = 1.0


@dataclass
class Genre:
    key: str
    lang: str
    confidence: float
    runner_up: str | None
    cues: list[str]
    scores: dict

    @property
    def label(self) -> str:
        return LABELS[self.key]["en"]

    @property
    def local_label(self) -> str:
        return LABELS[self.key][self.lang]

    @property
    def expects_sources(self) -> bool:
        return self.key in EXPECTS_SOURCES

    def as_evidence(self) -> dict:
        return {
            "genre": self.key,
            "label": self.label,
            "local_label": self.local_label,
            "confidence": self.confidence,
            "runner_up": self.runner_up,
            "cues": self.cues,
            "scores": self.scores,
        }


def _pattern(cue: str) -> str:
    if cue.endswith("*"):
        return rf"(?<!\w){re.escape(cue[:-1])}"
    return rf"(?<!\w){re.escape(cue)}(?!\w)"


def _hits(lowered: str, group: str, lang: str) -> list[str]:
    return [cue.rstrip("*") for cue in CUES[group][lang] if re.search(_pattern(cue), lowered)]


def _rate(count: int, n_words: int) -> float:
    return min(3.0, 100 * count / max(n_words, 1))


def _is_poem(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 8:
        return False
    lengths = [len(ln.split()) for ln in lines]
    return median(lengths) <= 8 and sum(n <= 10 for n in lengths) / len(lengths) >= 0.8


def _headings(text: str, lang: str) -> int:
    lines = [ln.strip().lower().rstrip(":") for ln in text.splitlines() if ln.strip()]
    return sum(1 for ln in lines if len(ln.split()) <= 5 and any(ln.startswith(c) for c in CUES["section"][lang]))


def detect_genre(text: str, lang: Language) -> Genre:
    code = lang.code
    lowered = text.lower().replace("ё", "е") if code == "ru" else text.lower()
    lines = [ln for ln in lowered.splitlines() if ln.strip()]
    n = len(words(text))
    found = {group: _hits(lowered, group, code) for group in CUES}
    first_person = _rate(len(FIRST_PERSON[code].findall(lowered)), n)
    head, tail = "\n".join(lines[:2]), "\n".join(lines[-3:])
    greeting = any(re.search(_pattern(c.strip()), head) for c in CUES["greeting"][code])
    signoff = any(re.search(_pattern(c), tail) for c in CUES["signoff"][code])
    dialogue = min(len(DIALOGUE.findall(text)), 5)
    scores = {
        "argument": 1.2 * len(found["thesis"]) + 0.8 * len(found["connector"]) + 1.0 * len(found["conclusion"]),
        "narrative": 0.8 * len(found["sequence"]) + 0.4 * dialogue + 0.6 * first_person,
        "retelling": 1.0 * len(found["work"]) + 0.6 * len(found["sequence"]) - 0.5 * first_person,
        "analysis": 1.0 * len(found["analysis"]) + 0.6 * len(found["work"]),
        "description": 1.2 * len(found["spatial"]),
        "report": 1.5 * min(_headings(text, code), 4) + min(len(bibliography_entries(text)), 4) + 0.5 * _rate(len(NUMBER.findall(text)), n),
        "letter": (3.0 if greeting else 0.0) + (2.0 if signoff else 0.0),
        "poem": 6.0 if _is_poem(text) else 0.0,
    }
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (best, top), (second, runner) = ranked[0], ranked[1]
    if top < MIN_SCORE:
        best, second, confidence = "other", best if top > 0 else None, 0.0
    else:
        confidence = round(min(0.95, 0.5 + (top - runner) / (2 * top)), 3)
    cues = [c for group in GENRE_CUES.get(best, ()) for c in found[group]]
    if best == "narrative":
        if dialogue:
            cues.append(DIALOGUE_CUE[code])
        if first_person >= FIRST_PERSON_RATE:
            cues.append(FIRST_PERSON_CUE[code])
    return Genre(best, code, confidence, second, cues[:12], {k: round(v, 2) for k, v in scores.items()})
