import random
import re

SENTENCE_STOP = re.compile(r"\. (?=\w)")
CLAUSE_PUNCT = re.compile(r"[,;:]")


def typos(text: str, rng: random.Random, rate: float = 0.04) -> str:
    words = text.split(" ")
    for i, word in enumerate(words):
        if len(word) < 4 or not word.isalpha() or rng.random() >= rate:
            continue
        pos = rng.randrange(1, len(word) - 1)
        op = rng.randrange(3)
        if op == 0:
            word = word[:pos] + word[pos + 1] + word[pos] + word[pos + 2 :]
        elif op == 1:
            word = word[:pos] + word[pos + 1 :]
        else:
            word = word[:pos] + word[pos] + word[pos:]
        words[i] = word
    return " ".join(words)


def lowercase(text: str, rng: random.Random) -> str:
    return text.lower()


def strip_punct(text: str, rng: random.Random) -> str:
    text = CLAUSE_PUNCT.sub("", text)
    return SENTENCE_STOP.sub(lambda m: " " if rng.random() < 0.3 else m.group(0), text)


NOISES = {"typos": typos, "lowercase": lowercase, "strip_punct": strip_punct}


def add_noise(text: str, rng: random.Random) -> str:
    return NOISES[rng.choice(sorted(NOISES))](text, rng)
