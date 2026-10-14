import logging
import random
import re
from datetime import timedelta

import numpy as np
import requests
from django.conf import settings
from django.utils import timezone

from analyzers.text.language import CYRILLIC_RE, LATIN_RE, detect_language
from plagiarism.embeddings import embed
from plagiarism.service import sentence_spans

from .models import ShadowAnswer, ShadowSet

logger = logging.getLogger(__name__)

MAX_TARGET = 12
DAILY_SETS = 3
SHADOW_DAYS = 120
MIN_SENTENCES = 4
SHADOW_SIMILARITY = 0.9
FLAG_SHARE = 0.5
FLAG_IN_ORDER = 0.7
TIMEOUT = 240

GRADES = {
    "en": ("a 7th-grade student", "a 9th-grade student", "an 11th-grade student", "a first-year university student"),
    "ru": ("ученик 7 класса", "ученик 9 класса", "ученик 11 класса", "студент первого курса"),
    "fr": ("un élève de cinquième", "un élève de troisième", "un élève de terminale", "un étudiant de première année"),
}
STYLES = {
    "en": ("plain and simple", "confident and structured", "personal, with an example from life", "careful and formal"),
    "ru": ("просто и понятно", "уверенно и по плану", "лично, с примером из жизни", "аккуратно и официально"),
    "fr": ("simple et clair", "assuré et structuré", "personnel, avec un exemple vécu", "soigné et formel"),
}
TEMPLATES = {
    "en": "You are {grade}. Write your answer to this assignment, {style}, about {words} words. Only the text of the answer.\n\nAssignment: {prompt}",
    "ru": "Ты {grade}. Напиши свой ответ на это задание, {style}, примерно {words} слов. Только текст ответа.\n\nЗадание: {prompt}",
    "fr": "Tu es {grade}. Écris ta réponse à ce devoir, {style}, environ {words} mots. Uniquement le texte de la réponse.\n\nDevoir : {prompt}",
}


FRENCH_HINT = re.compile(r"[éèêàçùœ]|\b(le|la|les|des|une|est|pour|dans|que)\b", re.IGNORECASE)


def prompt_language(prompt: str, default: str = "en") -> str:
    lang = detect_language(prompt)
    if lang and lang.code in TEMPLATES:
        return lang.code
    cyrillic, latin = len(CYRILLIC_RE.findall(prompt)), len(LATIN_RE.findall(prompt))
    if cyrillic > latin:
        return "ru"
    if latin > cyrillic:
        return "fr" if FRENCH_HINT.search(prompt) else "en"
    return default


def variants(language: str, count: int, seed: str) -> list[dict]:
    rng = random.Random(seed)
    return [
        {
            "grade": GRADES[language][i % len(GRADES[language])],
            "style": rng.choice(STYLES[language]),
            "words": rng.choice((250, 350, 450)),
            "temperature": rng.choice((0.6, 0.8, 1.0)),
        }
        for i in range(count)
    ]


def _generate(prompt: str, temperature: float, words: int) -> str:
    response = requests.post(
        f"{settings.OLLAMA_URL}/api/generate",
        json={
            "model": getattr(settings, "SHADOW_MODEL", "") or settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "top_p": 0.95, "num_predict": int(words * 3)},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def sentence_vectors(text: str) -> list[list[float]]:
    return embed([s for _, _, s in sentence_spans(text)])


def build(shadow: ShadowSet) -> int:
    written = 0
    for i, v in enumerate(variants(shadow.language, shadow.target, str(shadow.id))):
        prompt = TEMPLATES[shadow.language].format(prompt=shadow.prompt, **v)
        try:
            text = _generate(prompt, v["temperature"], v["words"])
        except Exception as exc:
            logger.warning("shadow %s answer %d failed: %s", shadow.id, i, exc)
            continue
        vectors = sentence_vectors(text)
        if len(vectors) < MIN_SENTENCES:
            continue
        ShadowAnswer.objects.create(shadow_set=shadow, text=text, variant=f'{v["grade"]}, {v["style"]}', vectors=vectors)
        written += 1
    return written


def sets_today(classroom) -> int:
    return ShadowSet.objects.filter(classroom=classroom, created_at__gte=timezone.now() - timedelta(days=1)).count()


def active_answers(classroom) -> list[ShadowAnswer]:
    since = timezone.now() - timedelta(days=SHADOW_DAYS)
    return list(
        ShadowAnswer.objects.filter(
            shadow_set__classroom=classroom, shadow_set__status=ShadowSet.Status.DONE, shadow_set__created_at__gte=since
        ).select_related("shadow_set")
    )


def compare(sentences: list[str], vectors: np.ndarray, answer: ShadowAnswer) -> dict:
    other = np.asarray(answer.vectors, dtype=np.float32)
    sims = vectors @ other.T
    best = sims.max(axis=1)
    targets = sims.argmax(axis=1)
    aligned = [i for i in range(len(sentences)) if best[i] >= SHADOW_SIMILARITY]
    order = [int(targets[i]) for i in aligned]
    in_order = sum(1 for x, y in zip(order, order[1:]) if y >= x) / (len(order) - 1) if len(order) > 1 else 0.0
    answer_sentences = [s for _, _, s in sentence_spans(answer.text)]
    pairs = [
        {
            "student": sentences[i],
            "ai": answer_sentences[int(targets[i])] if int(targets[i]) < len(answer_sentences) else "",
            "similarity": round(float(best[i]), 3),
        }
        for i in sorted(aligned, key=lambda k: -best[k])[:3]
    ]
    return {"share": round(len(aligned) / len(sentences), 3), "in_order": round(in_order, 3), "pairs": pairs}


def best_match(text: str, answers: list[ShadowAnswer]) -> dict | None:
    sentences = [s for _, _, s in sentence_spans(text)]
    if len(sentences) < MIN_SENTENCES or not answers:
        return None
    vectors = np.asarray(embed(sentences), dtype=np.float32)
    best = None
    for answer in answers:
        result = compare(sentences, vectors, answer)
        if best is None or (result["share"], result["in_order"]) > (best["share"], best["in_order"]):
            best = {**result, "shadow_set": str(answer.shadow_set_id), "prompt": answer.shadow_set.prompt[:300], "variant": answer.variant}
    best["answers_compared"] = len(answers)
    best["flagged"] = best["share"] >= FLAG_SHARE and best["in_order"] >= FLAG_IN_ORDER
    return best
