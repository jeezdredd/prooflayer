import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import pytest

from analyzers.implementations.text_classifier import MIN_TOKENS, load_calibration, model_dir, probability
from analyzers.implementations.text_signals import BASELINE_WORKS, CONTEXT_FLAG, PERSONAL_JUMP, STYLE_GROUPS, STYLE_HISTORY
from analyzers.text import classifier
from analyzers.text.evasion import hidden_docx_texts, scan_docx, scan_text, strip_hidden
from analyzers.text.genre import detect_genre
from analyzers.text.grade import assess
from analyzers.text.language import detect_language
from analyzers.text.style import drift, features
from classroom.management.commands.seed_demo import DATA, check_data, class_works, is_text_mime, work_mime
from common.documents import DOCX_MIME, read_text
from plagiarism.service import COMMON_AUTHORS, COMMON_MAX_WORDS, COMMON_SHARE, MIN_SHARE, MIN_SOURCE_CHARS, body_end
from plagiarism.shingles import SHINGLE, copied_pairs, covered_token_chars, matched_runs, shingle_hashes, text_chars, tokenize

ASSETS = DATA.parent / "assets"
EVASION_FLAG = 0.6
AI_LOOK = 0.45
SPREAD_ALERT = 0.5
COPIED_SHARE = 0.3
TEXT_LIMIT = 200_000


@dataclass
class Work:
    author: str
    classroom: str
    level: int | None
    prompt: str
    spec: dict
    text: str = ""
    path: Path | None = None
    mime: str = "text/plain"
    language: object = None
    tokens: list = field(default_factory=list)
    hashes: list = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.author}/{self.spec['filename']}"

    @property
    def expect(self) -> dict:
        return self.spec["expect"]


def _load() -> tuple[dict, list[Work]]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    works = []
    for org in data["organizations"]:
        for class_data in org["classes"]:
            prompt = (class_data.get("shadow") or {}).get("prompt", "")
            for email, spec in class_works(org, class_data):
                work = Work(email.split("@")[0], f"{org['slug']}/{class_data['name']}", class_data.get("level"), prompt, spec)
                work.mime = work_mime(spec)
                if spec.get("asset"):
                    work.path = ASSETS / spec["asset"]
                if is_text_mime(work.mime):
                    work.text = read_text(str(work.path), work.mime, TEXT_LIMIT) if work.path else spec["text"]
                    work.language = detect_language(work.text)
                    compared = strip_hidden(work.text, hidden_docx_texts(str(work.path))) if work.mime == DOCX_MIME else work.text
                    work.tokens = tokenize(compared)
                    work.hashes = shingle_hashes(work.tokens)
                works.append(work)
    works.sort(key=lambda w: -w.spec["days_ago"])
    return data, works


DEMO, WORKS = _load()
TEXT_WORKS = [w for w in WORKS if w.text]


def _earlier(work: Work) -> list[Work]:
    return WORKS[: WORKS.index(work)]


def _flagged(work: Work, flag: str) -> bool:
    return flag in work.expect.get("flags", [])


def _common_skip(work: Work, earlier: list[Work]) -> list[bool]:
    classmates = [w for w in earlier if w.text and w.classroom == work.classroom and w.author != work.author]
    needed = max(COMMON_AUTHORS, math.ceil(COMMON_SHARE * len({w.author for w in classmates})))
    own = set(work.hashes)
    authors = defaultdict(set)
    for other in classmates:
        for h in own.intersection(other.hashes):
            authors[h].add(other.author)
    shared = {h for h, who in authors.items() if len(who) >= needed}
    runs = [r for r in matched_runs(work.tokens, work.hashes, shared, min_len=SHINGLE) if r[1] - r[0] <= COMMON_MAX_WORDS]
    runs += matched_runs(work.tokens, work.hashes, set(shingle_hashes(tokenize(work.prompt))), min_len=SHINGLE)
    end = body_end(work.text)
    skip = [t.start >= end for t in work.tokens]
    for a, b in runs:
        for j in range(a, b):
            skip[j] = True
    return skip


def _copied_share(work: Work, source: Work, skip: list[bool]) -> float:
    pairs = copied_pairs(work.tokens, work.hashes, source.tokens, skip)
    matched = covered_token_chars(work.tokens, [own for own, _ in pairs])
    end = body_end(work.text)
    total = max(1, text_chars([t for t in work.tokens if t.start < end]))
    if matched < MIN_SOURCE_CHARS or 100 * matched / total < MIN_SHARE:
        return 0.0
    return matched / total


class TestDemoDataShape:
    def test_every_work_says_what_it_should_show(self):
        check_data(DEMO)
        missing = [w.key for w in WORKS if "expect" not in w.spec]
        assert missing == []

    def test_no_em_dash_and_no_promise_of_scans(self):
        raw = DATA.read_text(encoding="utf-8")
        assert chr(0x2014) not in raw
        batches = {w.spec.get("batch") for w in WORKS if w.spec.get("batch")}
        assert batches and not any("скан" in name.lower() for name in batches)

    def test_assets_exist(self):
        assert all(w.path.is_file() for w in WORKS if w.path)

    def test_chatbot_label_only_where_the_score_crosses_the_line(self):
        for work in TEXT_WORKS:
            assert _flagged(work, "ai_text") == (work.expect.get("ai") == "flag"), work.key

    def test_batches_mix_honest_ai_and_copied_answers(self):
        by_batch = defaultdict(list)
        for work in WORKS:
            if work.spec.get("batch"):
                by_batch[work.spec["batch"]].append(work)
        for name, items in by_batch.items():
            kinds = {"ai" if _flagged(w, "ai_text") else "copy" if _flagged(w, "copy") else "honest" for w in items}
            assert kinds == {"ai", "copy", "honest"}, name


class TestCheapSignals:
    def test_hidden_text_and_tricks(self):
        for work in TEXT_WORKS:
            report = scan_text(work.text)
            if work.mime == DOCX_MIME:
                report.hidden_runs = scan_docx(str(work.path))
            fired = set()
            if report.strength() >= EVASION_FLAG:
                fired.add("hidden_text" if report.hidden_characters else "tricks")
            expected = set(work.expect.get("flags", [])) & {"hidden_text", "tricks"}
            assert fired == expected, work.key

    def test_genre(self):
        for work in TEXT_WORKS:
            if "genre" in work.expect:
                assert detect_genre(work.text, work.language).key == work.expect["genre"], work.key

    def test_vocabulary_above_age(self):
        history = defaultdict(list)
        for work in WORKS:
            if not work.text or not work.level:
                continue
            fit = assess(work.text, work.language, work.level)
            if fit is None:
                continue
            earlier = [m for lang, m in history[work.author] if lang == work.language.code][-STYLE_HISTORY * 2:]
            fired = (
                fit.mismatch >= CONTEXT_FLAG
                and len(earlier) >= BASELINE_WORKS
                and fit.mismatch - median(earlier) >= PERSONAL_JUMP
            )
            assert fired == _flagged(work, "age"), work.key
            history[work.author].append((work.language.code, fit.mismatch))

    def test_style_drift(self):
        history = defaultdict(list)
        for work in WORKS:
            if not work.text:
                continue
            profile = features(work.text, work.language)
            if profile is None:
                assert not _flagged(work, "style"), work.key
                continue
            genre = detect_genre(work.text, work.language).key
            profile["group"] = STYLE_GROUPS.get(genre, genre)
            same = [p for p in reversed(history[work.author]) if p["language"] == profile["language"] and p["group"] == profile["group"]]
            same = same[:STYLE_HISTORY]
            fired = len(same) >= BASELINE_WORKS and drift(profile, same)["score"] >= CONTEXT_FLAG
            assert fired == _flagged(work, "style"), work.key
            history[work.author].append(profile)

    def test_copied_works_share_text_with_their_source(self):
        by_key = {w.key: w for w in WORKS}
        for work in TEXT_WORKS:
            source_key = work.expect.get("copied_from")
            if not source_key:
                continue
            source = by_key[source_key]
            assert WORKS.index(source) < WORKS.index(work), work.key
            assert _copied_share(work, source, _common_skip(work, _earlier(work))) >= COPIED_SHARE, work.key

    def test_original_works_share_no_run_of_words_with_earlier_work(self):
        for work in TEXT_WORKS:
            if work.expect.get("originality") != [100, 100]:
                continue
            earlier = [w for w in _earlier(work) if w.text and w.author != work.author]
            skip = _common_skip(work, earlier)
            shared = [w.key for w in earlier if _copied_share(work, w, skip) > 0]
            assert shared == [], work.key


def _calibration():
    directory = model_dir()
    calibration = load_calibration(directory)
    if calibration is None:
        pytest.skip(f"text classifier model not found in {directory}")
    return directory, calibration


class TestClassifier:
    def test_ai_tile_band(self):
        directory, calibration = _calibration()
        model = classifier.get_classifier(directory)
        for work in TEXT_WORKS:
            entry = calibration["languages"][work.language.code]
            result = model.score(work.text)
            if result.tokens < MIN_TOKENS:
                band = "short"
            elif entry.get("threshold_fpr1") is not None and result.score >= entry["threshold_fpr1"]:
                band = "flag"
            else:
                p = probability(result.score, entry["knots"])
                segments = classifier.split_segments(work.text)
                probs = [probability(m, entry["knots"]) for m in model.segment_margins(segments)] if len(segments) >= 2 else []
                uneven = bool(probs) and max(probs) - min(probs) >= SPREAD_ALERT
                band = "look" if p >= AI_LOOK or uneven else "clear"
            assert band == work.expect["ai"], work.key
