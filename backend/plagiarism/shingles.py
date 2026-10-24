import hashlib
import re
import unicodedata
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass

SHINGLE = 5
WINDOW = 4
MIN_RUN_WORDS = SHINGLE + WINDOW - 1
INVISIBLE_CLASS = "​-‏⁠-⁤﻿­͏᠎"
TOKEN_RE = re.compile(rf"[^\W_](?:[^\W_]|[{INVISIBLE_CLASS}])*", re.UNICODE)
INVISIBLE_RE = re.compile(f"[{INVISIBLE_CLASS}]")
LINK_RE = re.compile(r"(?:https?://|www\.|doi\.org/|doi:\s*|\b10\.\d{4,9}/)\S+", re.IGNORECASE)
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
    links = [(m.start(), m.end()) for m in LINK_RE.finditer(text)]
    tokens = []
    link = 0
    for m in TOKEN_RE.finditer(text):
        while link < len(links) and links[link][1] <= m.start():
            link += 1
        if link < len(links) and links[link][0] <= m.start():
            continue
        tokens.append(Token(normalize_word(m.group()), m.start(), m.end()))
    return tokens


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


def marked_runs(marked: list[bool], min_len: int = MIN_RUN_WORDS) -> list[tuple[int, int]]:
    runs = []
    run_start = None
    for i, flag in enumerate([*marked, False]):
        if flag and run_start is None:
            run_start = i
        elif not flag and run_start is not None:
            if i - run_start >= min_len:
                runs.append((run_start, i))
            run_start = None
    return runs


def matched_runs(
    tokens: list[Token], hashes: list[int], other: set[int], skip: list[bool] | None = None,
    k: int = SHINGLE, min_len: int = MIN_RUN_WORDS,
) -> list[tuple[int, int]]:
    marked = [False] * len(tokens)
    for i, h in enumerate(hashes):
        if h in other:
            for j in range(i, min(i + k, len(tokens))):
                marked[j] = True
    if skip is not None:
        marked = [flag and not skipped for flag, skipped in zip(marked, skip)]
    return marked_runs(marked, min_len)


def char_span(tokens: list[Token], run: tuple[int, int]) -> tuple[int, int]:
    return tokens[run[0]].start, tokens[run[1] - 1].end


def covered_spans(tokens: list[Token], hashes: list[int], other: set[int], k: int = SHINGLE) -> list[tuple[int, int]]:
    return [char_span(tokens, run) for run in matched_runs(tokens, hashes, other, k=k)]


def positions(hashes: list[int]) -> dict[int, list[int]]:
    where: dict[int, list[int]] = {}
    for i, h in enumerate(hashes):
        where.setdefault(h, []).append(i)
    return where


def align(run: tuple[int, int], hashes: list[int], where: dict[int, list[int]], size: int, k: int = SHINGLE) -> tuple[int, int] | None:
    votes: Counter = Counter()
    for i in range(max(0, run[0] - k + 1), min(run[1], len(hashes))):
        for p in where.get(hashes[i], ()):
            votes[p - i] += 1
    if not votes:
        return None
    shift = votes.most_common(1)[0][0]
    start, end = max(0, run[0] + shift), min(size, run[1] + shift)
    return (start, end) if start < end else None


def copied_pairs(
    tokens: list[Token], hashes: list[int], other_tokens: list[Token], skip: list[bool] | None = None,
) -> list[tuple[tuple[int, int], tuple[int, int] | None]]:
    other_hashes = shingle_hashes(other_tokens)
    where = positions(other_hashes)
    pairs = []
    for run in matched_runs(tokens, hashes, set(other_hashes), skip):
        source = align(run, hashes, where, len(other_tokens))
        pairs.append((char_span(tokens, run), char_span(other_tokens, source) if source else None))
    return pairs


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(tuple(s) for s in spans):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def covered_token_chars(tokens: list[Token], spans: list[tuple[int, int]]) -> int:
    merged = merge_spans(spans)
    total = 0
    i = 0
    for t in tokens:
        while i < len(merged) and merged[i][1] < t.end:
            i += 1
        if i == len(merged):
            break
        if merged[i][0] <= t.start:
            total += t.end - t.start
    return total


def tokens_in(starts: list[int], span: tuple[int, int]) -> range:
    return range(bisect_left(starts, span[0]), bisect_left(starts, span[1]))


def text_chars(tokens: list[Token]) -> int:
    return sum(t.end - t.start for t in tokens)
