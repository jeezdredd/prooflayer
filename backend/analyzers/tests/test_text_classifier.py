import json
import math
from unittest import mock

import pytest

from analyzers.implementations import text_classifier
from analyzers.implementations.text_classifier import TextClassifierAnalyzer, load_calibration, probability
from analyzers.management.commands.build_text_train import latin_share, strip_hint
from analyzers.management.commands.train_text_classifier import auc_high, knots
from analyzers.text import classifier
from analyzers.text.classifier import ClassifierScore, TextClassifier, pick_windows
from analyzers.text.normalize import normalize_for_model

ESSAY_EN = (
    "Last summer I went to my grandma house in the village. It was really fun. Me and my brother went to the "
    "river every day and we caught fish. One time we caught a big one and grandma cooked it for dinner. My "
    "grandpa showed us how to fix a bike and we rode it all around the field. At night we sat by the fire and "
    "looked at the stars. I love the village because you can run all day and nobody gets mad at you."
)
ESSAY_RU = (
    "Летом я ездил к бабушке в деревню. Там было очень весело. Мы с братом ходили на речку и ловили рыбу. "
    "Один раз мы поймали большую щуку. Бабушка пекла пироги с яблоками, а дедушка показывал нам, как чинить "
    "велосипед. Вечером мы сидели у костра и смотрели на звёзды."
)
CALIBRATION = {
    "base": "intfloat/multilingual-e5-small",
    "languages": {
        "en": {
            "threshold_fpr1": 2.0,
            "threshold_fpr5": 1.0,
            "threshold_strict": 3.0,
            "knots": [[-4.0, 0.05], [1.0, 0.45], [2.0, 0.75], [3.0, 0.89], [5.0, 0.97]],
        },
    },
}


class TestNormalize:
    def test_repairs_homoglyphs_both_ways(self):
        assert normalize_for_model("мoлоко") == "молоко"
        assert normalize_for_model("hеllo") == "hello"

    def test_strips_invisible_and_unifies_punctuation(self):
        assert normalize_for_model("It’s​ «fine» — ok…\n\nnext") == "It's \"fine\" - ok... next"

    def test_keeps_genuine_mixed_text(self):
        assert normalize_for_model("Я люблю Python и Django") == "Я люблю Python и Django"


class TestWindows:
    def test_pick_windows_spreads_over_text(self):
        assert pick_windows(list(range(10)), 4) == [0, 3, 6, 9]
        assert pick_windows([1, 2], 4) == [1, 2]

    def test_short_tail_is_dropped(self):
        scorer = TextClassifier.__new__(TextClassifier)
        scorer.max_tokens = 66
        parts = scorer.chunks(list(range(64 + 10)))
        assert [len(p) for p in parts] == [64]

    def test_short_text_keeps_single_window(self):
        scorer = TextClassifier.__new__(TextClassifier)
        scorer.max_tokens = 512
        assert [len(p) for p in scorer.chunks(list(range(10)))] == [10]


class TestTrainingHelpers:
    def test_knots_are_increasing(self):
        human = [i / 20 - 5 for i in range(100)]
        ai = [i / 20 + 2 for i in range(100)]
        for strict in (None, 0.2):
            points = knots(0.0, -0.4, human, ai, strict)
            scores, probs = [s for s, _ in points], [p for _, p in points]
            assert scores == sorted(scores) and len(set(scores)) == len(scores)
            assert probs == sorted(probs)

    def test_without_strict_classifier_alone_stays_below_single_voter_floor(self):
        points = knots(1.0, 0.5, [-3.0, -2.0, -1.0], [4.0, 5.0, 6.0])
        assert max(p for _, p in points) == 0.89

    def test_strict_threshold_gates_high_probability(self):
        points = knots(1.0, 0.5, [-3.0, -2.0, -1.0], [2.0, 2.5, 3.0], strict=2.8)
        assert probability(2.79, points) < 0.9
        assert probability(3.3, points) == 0.97

    def test_score_is_logit_margin(self):
        assert ClassifierScore(score=0.0, windows=[], tokens=1).probability == 0.5

    def test_auc_higher_is_ai(self):
        assert auc_high([0.8, 0.9], [0.1, 0.2]) == 1.0
        assert auc_high([0.1, 0.2], [0.8, 0.9]) == 0.0
        assert auc_high([0.5], [0.5]) == 0.5

    def test_strip_hint_removes_copied_opening(self):
        hint = "Автор книг о Гарри Поттере британская писательница Джоан Роулинг обратилась в суд"
        text = f"{hint} с иском против газеты. Дальше идёт уже сгенерированный текст."
        assert strip_hint(text, hint) == "Дальше идёт уже сгенерированный текст."
        assert strip_hint("Совсем другое начало. И продолжение.", hint) == "Совсем другое начало. И продолжение."


    def test_latin_share_flags_transliterated_russian(self):
        assert latin_share("Privet, kak dela? Vse horosho.") == 1.0
        assert latin_share("Привет, как дела? Всё хорошо.") == 0.0
        assert latin_share("123 !!") == 0.0


class TestCalibration:
    def test_probability_interpolates_and_clamps(self):
        points = [(0.1, 0.05), (0.9, 0.75)]
        assert probability(0.0, points) == 0.05
        assert probability(1.0, points) == 0.75
        assert math.isclose(probability(0.5, points), 0.4)

    def test_rejects_decreasing_knots(self, tmp_path):
        (tmp_path / "calibration.json").write_text(json.dumps({"languages": {"en": {"knots": [[0.1, 0.9], [0.9, 0.1]]}}}))
        with mock.patch.dict(text_classifier._state, {"dir": None}):
            assert load_calibration(str(tmp_path)) is None


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    directory = tmp_path / "text"
    directory.mkdir()
    (directory / "calibration.json").write_text(json.dumps(CALIBRATION))
    monkeypatch.setenv("TEXT_CLASSIFIER_DIR", str(directory))
    with mock.patch.dict(text_classifier._state, {"dir": None, "calibration": None}):
        yield directory


def _essay(tmp_path, text=ESSAY_EN):
    path = tmp_path / "essay.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _run(tmp_path, score, tokens=300, text=ESSAY_EN):
    model = mock.Mock()
    model.score.return_value = ClassifierScore(score=score, windows=[score], tokens=tokens)
    with mock.patch.object(classifier, "get_classifier", return_value=model):
        return TextClassifierAnalyzer().analyze(_essay(tmp_path, text), {"mime_type": "text/plain"})


@pytest.mark.usefixtures("model_dir")
class TestAnalyzer:
    def test_above_strict_threshold_is_fake(self, tmp_path):
        out = _run(tmp_path, 4.0)
        assert out.verdict == "fake"
        assert out.evidence["ai_probability"] > 0.9

    def test_between_fpr1_and_strict_is_suspicious_below_single_voter_floor(self, tmp_path):
        out = _run(tmp_path, 2.5)
        assert out.verdict == "suspicious"
        assert out.evidence["ai_probability"] < 0.9

    def test_human_range_is_authentic(self, tmp_path):
        out = _run(tmp_path, -5.0)
        assert out.verdict == "authentic"
        assert out.evidence["ai_probability"] == 0.05

    def test_leaning_score_is_suspicious(self, tmp_path):
        assert _run(tmp_path, 1.5).verdict == "suspicious"

    def test_short_text_gives_no_probability(self, tmp_path):
        out = _run(tmp_path, 9.0, tokens=60)
        assert out.verdict == "inconclusive"
        assert "ai_probability" not in out.evidence

    def test_uncalibrated_language_is_inconclusive(self, tmp_path):
        out = _run(tmp_path, 9.0, text=ESSAY_RU)
        assert out.verdict == "inconclusive"
        assert out.evidence["reason"] == "language not calibrated"

    def test_missing_model_is_error(self, tmp_path):
        with mock.patch.object(classifier, "get_classifier", side_effect=OSError("no weights")):
            out = TextClassifierAnalyzer().analyze(_essay(tmp_path), {"mime_type": "text/plain"})
        assert out.verdict == "error"


def test_missing_calibration_is_error(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXT_CLASSIFIER_DIR", str(tmp_path / "missing"))
    with mock.patch.dict(text_classifier._state, {"dir": None}):
        out = TextClassifierAnalyzer().analyze(_essay(tmp_path), {"mime_type": "text/plain"})
    assert out.verdict == "error"
