import hashlib
import re
import unicodedata
from dataclasses import dataclass

SHINGLE = 5
WINDOW = 4
INVISIBLE_CLASS = "​-‏⁠-⁤﻿­͏᠎"
TOKEN_RE = re.compile(rf"[^\W_](?:[^\W_]|[{INVISIBLE_CLASS}])*", re.UNICODE)
INVISIBLE_RE = re.compile(f"[{INVISIBLE_CLASS}]")
LATIN_TO_CYRILLIC = str.maketrans("aeopcyxkmthb", "аеорсухкмтнв")
CYRILLIC_TO_LATIN = str.maketrans("аеорсухіјѕ", "aeopcyxijs")
CYRILLIC_RE = re.compile(r"[а-яё]")
LATIN_RE = re.compile(r"[a-z]")


@dataclass(frozen=True)
class Token:
    norm: str
    start: int
    end: int


def normalize_word(raw: str) -> str:
    word = INVISIBLE_RE.sub("", unicodedata.normalize("NFKC", raw)).lower().replace("ё", "е")
    cyr = len(CYRILLIC_RE.findall(word))
    lat = len(LATIN_RE.findall(word))
    if cyr and lat:
        word = word.translate(LATIN_TO_CYRILLIC) if cyr >= lat else word.translate(CYRILLIC_TO_LATIN)
    return word


def tokenize(text: str) -> list[Token]:
    return [Token(normalize_word(m.group()), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def _hash(parts: list[str]) -> int:
    digest = hashlib.blake2b(" ".join(parts).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


def shingle_hashes(tokens: list[Token], k: int = SHINGLE) -> list[int]:
    norms = [t.norm for t in tokens]
    return [_hash(norms[i:i + k]) for i in range(len(norms) - k + 1)]


def winnow(hashes: list[int], window: int = WINDOW) -> list[int]:
    if len(hashes) <= window:
        return sorted(set(hashes))
    picked = set()
    for i in range(len(hashes) - window + 1):
        chunk = hashes[i:i + window]
        picked.add(min(chunk))
    return sorted(picked)


def covered_spans(tokens: list[Token], hashes: list[int], other: set[int], k: int = SHINGLE) -> list[tuple[int, int]]:
    marked = [False] * len(tokens)
    for i, h in enumerate(hashes):
        if h in other:
            for j in range(i, min(i + k, len(tokens))):
                marked[j] = True
    spans = []
    run_start = None
    for i, flag in enumerate(marked):
        if flag and run_start is None:
            run_start = i
        if not flag and run_start is not None:
            spans.append((tokens[run_start].start, tokens[i - 1].end))
            run_start = None
    if run_start is not None:
        spans.append((tokens[run_start].start, tokens[-1].end))
    return spans


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def span_chars(spans: list[tuple[int, int]]) -> int:
    return sum(end - start for start, end in merge_spans(spans))


def text_chars(tokens: list[Token]) -> int:
    return sum(t.end - t.start for t in tokens)
