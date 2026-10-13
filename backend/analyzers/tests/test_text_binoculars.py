import json
import math
from types import SimpleNamespace
from unittest import mock

import pytest
import torch

from analyzers.implementations import text_binoculars
from analyzers.implementations.text_binoculars import TextBinocularsAnalyzer, load_calibration, probability
from analyzers.management.commands.eval_text_detectors import auc, knots, quantile
from analyzers.text import binoculars
from analyzers.text.binoculars import BinocularsScore, BinocularsScorer

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
    "observer": "obs",
    "performer": "perf",
    "languages": {
        "en": {"threshold_fpr1": 0.80, "threshold_fpr5": 0.85, "knots": [[0.70, 0.95], [0.80, 0.8], [0.85, 0.55], [0.95, 0.15], [1.05, 0.05]]},
    },
}


class FixedLogits(torch.nn.Module):
    def __init__(self, logits):
        super().__init__()
        self.logits = logits

    def forward(self, input_ids):
        return SimpleNamespace(logits=self.logits.expand(input_ids.shape[0], input_ids.shape[1], -1))


def _scorer(observer_logits, performer_logits, length):
    scorer = BinocularsScorer.__new__(BinocularsScorer)
    scorer.device = "cpu"
    scorer.observer = FixedLogits(observer_logits)
    scorer.performer = FixedLogits(performer_logits)
    scorer.tokenizer = lambda text, **kwargs: SimpleNamespace(input_ids=torch.zeros((1, length), dtype=torch.long))
    return scorer


class TestScorer:
    def test_identical_models_give_ce_over_entropy(self):
        logits = torch.tensor([[[2.0, 0.0, 0.0, 0.0]]])
        result = _scorer(logits, logits, 40).score("x")
        log_probs = torch.log_softmax(logits[0, 0], dim=-1)
        expected = float(-log_probs[0] / -(log_probs.exp() * log_probs).sum())
        assert math.isclose(result.score, expected, rel_tol=1e-5)
        assert result.tokens == 39

    def test_long_text_is_windowed_and_short_tail_dropped(self):
        logits = torch.tensor([[[1.0, 0.5, 0.0]]])
        result = _scorer(logits, logits, binoculars.WINDOW_TOKENS * 2 + 10).score("x")
        assert len(result.windows) == 2

    def test_too_short_text_raises(self):
        logits = torch.tensor([[[1.0, 0.5, 0.0]]])
        with pytest.raises(ValueError):
            _scorer(logits, logits, 10).score("x")


class TestCalibration:
    def test_probability_interpolates_and_clamps(self):
        points = [(0.7, 0.95), (0.8, 0.8), (1.0, 0.1)]
        assert probability(0.5, points) == 0.95
        assert probability(1.3, points) == 0.1
        assert math.isclose(probability(0.9, points), 0.45)

    def test_rejects_non_monotone_knots(self, tmp_path):
        path = tmp_path / "cal.json"
        path.write_text(json.dumps({**CALIBRATION, "languages": {"en": {"knots": [[0.7, 0.2], [0.9, 0.8]]}}}))
        with mock.patch.dict(text_binoculars._state, {"path": None}):
            assert load_calibration(str(path)) is None

    def test_eval_knots_are_monotone(self):
        human = [0.9 + i * 0.002 for i in range(100)]
        ai = [0.6 + i * 0.002 for i in range(100)]
        points = knots(quantile(human, 0.01), quantile(human, 0.05), human, ai)
        scores, probs = [s for s, _ in points], [p for _, p in points]
        assert scores == sorted(scores)
        assert probs == sorted(probs, reverse=True)

    def test_auc_lower_is_ai(self):
        assert auc([0.6, 0.7], [0.9, 1.0]) == 1.0
        assert auc([0.9, 1.0], [0.6, 0.7]) == 0.0


@pytest.fixture
def calibration_path(tmp_path):
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(CALIBRATION))
    with mock.patch.object(text_binoculars, "CALIBRATION_PATH", str(path)), mock.patch.dict(text_binoculars._state, {"path": None}):
        yield path


def _essay(tmp_path, text=ESSAY_EN):
    path = tmp_path / "essay.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _run(tmp_path, score, tokens=300, text=ESSAY_EN):
    scorer = mock.Mock()
    scorer.score.return_value = BinocularsScore(score=score, tokens=tokens, windows=[score])
    with mock.patch.object(binoculars, "get_scorer", return_value=scorer):
        return TextBinocularsAnalyzer().analyze(_essay(tmp_path, text), {"mime_type": "text/plain"})


@pytest.mark.usefixtures("calibration_path")
class TestAnalyzer:
    def test_low_score_is_fake(self, tmp_path):
        out = _run(tmp_path, 0.72)
        assert out.verdict == "fake"
        assert out.evidence["ai_probability"] > 0.9

    def test_human_range_is_authentic(self, tmp_path):
        out = _run(tmp_path, 1.0)
        assert out.verdict == "authentic"
        assert out.evidence["ai_probability"] < 0.15

    def test_between_thresholds_is_suspicious(self, tmp_path):
        assert _run(tmp_path, 0.83).verdict == "suspicious"

    def test_short_text_gives_no_probability(self, tmp_path):
        out = _run(tmp_path, 0.7, tokens=60)
        assert out.verdict == "inconclusive"
        assert "ai_probability" not in out.evidence

    def test_uncalibrated_language_is_inconclusive(self, tmp_path):
        out = _run(tmp_path, 0.7, text=ESSAY_RU)
        assert out.verdict == "inconclusive"
        assert out.evidence["reason"] == "language not calibrated"

    def test_missing_models_is_error(self, tmp_path):
        with mock.patch.object(binoculars, "get_scorer", side_effect=binoculars.BinocularsUnavailable("no torch")):
            out = TextBinocularsAnalyzer().analyze(_essay(tmp_path), {"mime_type": "text/plain"})
        assert out.verdict == "error"


def test_missing_calibration_is_error(tmp_path):
    with mock.patch.object(text_binoculars, "CALIBRATION_PATH", str(tmp_path / "missing.json")), mock.patch.dict(text_binoculars._state, {"path": None}):
        out = TextBinocularsAnalyzer().analyze(_essay(tmp_path), {"mime_type": "text/plain"})
    assert out.verdict == "error"
