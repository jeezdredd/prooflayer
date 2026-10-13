import math
from statistics import mean, pstdev

from wordfreq import zipf_frequency

from .language import Language, sentences, words

LLM_PHRASES: dict[str, tuple[str, ...]] = {
    "ru": (
        "играет важную роль", "играет ключевую роль", "является ключевым", "является важным", "таким образом",
        "в заключение", "следует отметить", "важно отметить", "стоит отметить", "необходимо подчеркнуть",
        "следует подчеркнуть", "в современном мире", "в современном обществе", "представляет собой",
        "неотъемлемой частью", "неотъемлемая часть", "широкий спектр", "многогранн", "немаловажн", "в эпоху",
        "в контексте", "способствует развитию", "позволяет не только", "в целом,", "подводя итог",
        "кроме того,", "более того,", "в свою очередь", "данный подход", "данной работе", "является одним из",
    ),
    "en": (
        "delve", "it is important to note", "it's important to note", "in conclusion", "plays a crucial role",
        "plays a vital role", "plays a pivotal role", "in today's", "furthermore", "moreover", "tapestry",
        "a testament to", "navigate the complexities", "multifaceted", "in summary", "underscore", "pivotal",
        "foster", "landscape of", "in the realm of", "embark", "intricate", "nuanced", "ever-evolving",
        "shed light on", "a myriad of", "additionally", "overall,", "serves as a",
    ),
    "fr": (
        "il est important de noter", "en conclusion", "joue un rôle crucial", "joue un rôle essentiel",
        "joue un rôle clé", "de nos jours", "par ailleurs", "en outre", "dans le monde d'aujourd'hui",
        "il convient de souligner", "en somme", "multifacette", "incontournable", "au cœur de",
        "en définitive", "force est de constater", "il est essentiel de",
        "un large éventail", "permet de mieux", "s'avère", "dans un monde en constante",
    ),
}

PUNCT = {"comma": ",", "semicolon": ";", "colon": ":", "dash": "—–", "question": "?", "exclaim": "!", "paren": "("}
SCALAR_FLOOR = {
    "sentence_mean": 3.0, "sentence_std": 2.0, "word_length": 0.35, "ttr": 0.05, "rare_share": 0.03,
    "comma": 0.03, "semicolon": 0.005, "colon": 0.005, "dash": 0.008, "question": 0.005, "exclaim": 0.005, "paren": 0.005,
}
MIN_WORDS = 60


def phrasebook(text: str, lang: Language) -> dict:
    lowered = text.lower().replace("ё", "е")
    hits = {}
    for phrase in LLM_PHRASES.get(lang.code, ()):
        count = lowered.count(phrase.replace("ё", "е"))
        if count:
            hits[phrase] = count
    total_words = max(1, len(words(text)))
    return {"hits": hits, "per_1000_words": round(1000 * sum(hits.values()) / total_words, 2)}


def _mattr(tokens: list[str], window: int = 50) -> float:
    if len(tokens) <= window:
        return len(set(tokens)) / max(1, len(tokens))
    ratios = [len(set(tokens[i:i + window])) / window for i in range(0, len(tokens) - window + 1, 5)]
    return mean(ratios)


def features(text: str, lang: Language) -> dict | None:
    tokens = [w.lower() for w in words(text)]
    if len(tokens) < MIN_WORDS:
        return None
    lengths = [len(words(s)) for s in sentences(text)]
    lengths = [n for n in lengths if n] or [len(tokens)]
    n = len(tokens)
    out = {
        "language": lang.code,
        "sentence_mean": mean(lengths),
        "sentence_std": pstdev(lengths) if len(lengths) > 1 else 0.0,
        "word_length": mean(len(t) for t in tokens),
        "ttr": _mattr(tokens),
        "rare_share": sum(1 for t in tokens if len(t) > 3 and 0 < zipf_frequency(t.replace("ё", "е"), lang.code) < 3.0) / n,
    }
    for key, chars in PUNCT.items():
        out[key] = sum(text.count(c) for c in chars) / n
    counts = {fw: 0 for fw in lang.function_words}
    for t in tokens:
        if t in counts:
            counts[t] += 1
    out["function_words"] = [counts[fw] / n for fw in lang.function_words]
    return out


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return 1 - dot / (na * nb)


def drift(current: dict, history: list[dict]) -> dict:
    deviations = {}
    for key, floor in SCALAR_FLOOR.items():
        values = [h[key] for h in history]
        spread = max(pstdev(values) if len(values) > 1 else 0.0, floor)
        deviations[key] = round(abs(current[key] - mean(values)) / spread, 2)
    profile = [mean(col) for col in zip(*(h["function_words"] for h in history))]
    fw_distance = _cosine_distance(current["function_words"], profile)
    score = mean(sorted(deviations.values(), reverse=True)[:4])
    drift_score = max(0.0, min(1.0, (score - 1.5) / 3.0)) * 0.7 + max(0.0, min(1.0, (fw_distance - 0.15) / 0.35)) * 0.3
    return {
        "score": round(drift_score, 3),
        "top_deviations": dict(sorted(deviations.items(), key=lambda kv: -kv[1])[:5]),
        "function_word_distance": round(fw_distance, 3),
        "history_size": len(history),
    }
