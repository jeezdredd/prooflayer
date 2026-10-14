import json
from pathlib import Path
from unittest.mock import patch

import pytest

from analyzers import auto_retrain as ar
from analyzers.implementations.custom_detector import load_calibration
from analyzers.models import RetrainRun
from analyzers.tasks import run_weekly_retrain


@pytest.fixture
def layout(tmp_path, monkeypatch):
    paths = {
        "LIVE": tmp_path / "image",
        "CANDIDATE": tmp_path / "image.candidate",
        "PREVIOUS": tmp_path / "image.previous",
        "AUTO": tmp_path / "auto",
        "POOL": tmp_path / "auto" / "pool",
        "CALIBRATION": tmp_path / "auto" / "calibration",
        "HOLDOUT": tmp_path / "auto" / "holdout",
        "STATE": tmp_path / "auto" / "state.json",
    }
    for name, value in paths.items():
        monkeypatch.setattr(ar, name, value)
    return paths


def _model(path: Path, tag: str):
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(json.dumps({"tag": tag}))


def _image(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpg")


class TestFitKnots:
    def test_knots_pass_the_detector_check(self, tmp_path):
        knots = ar.fit_knots([0.1, 0.4, 0.92], [0.95, 0.99, 0.999])
        (tmp_path / "calibration.json").write_text(json.dumps({"knots": knots}))
        assert load_calibration(str(tmp_path)) is not None
        assert knots[1] == [0.92, 0.5]

    def test_no_real_scores_no_knots(self):
        assert ar.fit_knots([], [0.9]) is None


class TestGate:
    def test_real_photo_called_ai_blocks(self):
        live = ar.HoldoutMetrics(ai_caught=100)
        candidate = ar.HoldoutMetrics(ai_caught=110, real_fake=1)
        assert any("real photos called AI" in p for p in ar.gate(live, candidate))

    def test_fewer_caught_blocks(self):
        assert ar.gate(ar.HoldoutMetrics(ai_caught=100), ar.HoldoutMetrics(ai_caught=99))

    def test_same_numbers_are_not_worth_promoting(self):
        assert ar.gate(ar.HoldoutMetrics(ai_caught=100), ar.HoldoutMetrics(ai_caught=100)) == ["no improvement over the live model"]

    def test_better_candidate_passes(self):
        live = ar.HoldoutMetrics(ai_caught=100, ai_authentic=6, real_suspicious=1)
        assert ar.gate(live, ar.HoldoutMetrics(ai_caught=103, ai_authentic=5, real_suspicious=0)) == []


class TestFiles:
    def test_distribute_splits_and_skips_existing(self, layout, tmp_path):
        source = tmp_path / "fetched"
        for i in range(20):
            path = source / "ai_generated" / "gen" / f"{i}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"img{i}".encode())
        (source / "real").mkdir(parents=True, exist_ok=True)
        (source / "real" / "r.jpg").write_bytes(b"real")
        assert ar.distribute(source) == 21
        assert ar.image_count(layout["POOL"]) + ar.image_count(layout["CALIBRATION"]) == 21
        assert ar.image_count(layout["CALIBRATION"]) > 0

    def test_same_file_name_from_a_later_fetch_is_not_lost(self, layout, tmp_path):
        first = tmp_path / "first"
        second = tmp_path / "second"
        (first / "real").mkdir(parents=True)
        (second / "real").mkdir(parents=True)
        (first / "real" / "real__0001.png").write_bytes(b"one")
        (second / "real" / "real__0001.png").write_bytes(b"two")
        assert ar.distribute(first) == 1
        assert ar.distribute(second) == 1
        assert ar.image_count(layout["POOL"]) + ar.image_count(layout["CALIBRATION"]) == 2

    def test_trim_pool_drops_oldest(self, layout):
        for i in range(5):
            _image(layout["POOL"] / "real" / f"{i}.jpg")
        assert ar.trim_pool(limit=3) == 2
        assert ar.image_count(layout["POOL"]) == 3

    def test_promote_and_rollback(self, layout):
        _model(layout["LIVE"], "old")
        _model(layout["CANDIDATE"], "new")
        ar.promote()
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "new"
        assert json.loads((layout["PREVIOUS"] / "config.json").read_text())["tag"] == "old"
        ar.rollback()
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "old"
        assert json.loads((layout["PREVIOUS"] / "config.json").read_text())["tag"] == "new"


class TestRun:
    def test_skips_without_holdout(self, layout):
        assert ar.run(0, 1).reason == "held-out set is missing"

    def _ready(self, layout):
        _model(layout["LIVE"], "old")
        _image(layout["HOLDOUT"] / "real" / "h.jpg")
        _image(layout["CALIBRATION"] / "real" / "c.jpg")

    def test_promotes_a_better_candidate(self, layout, settings):
        settings.RETRAIN_MIN_NEW_SAMPLES = 50
        self._ready(layout)
        with (
            patch.object(ar, "fetch_new", return_value=60),
            patch.object(ar, "train_candidate", side_effect=lambda epochs: _model(layout["CANDIDATE"], "new") or "rev"),
            patch.object(ar, "calibrate_candidate", return_value=[[0, 0], [0.9, 0.5], [0.95, 0.8], [1, 1]]),
            patch.object(ar, "holdout_metrics", return_value=[ar.HoldoutMetrics(ai_caught=100), ar.HoldoutMetrics(ai_caught=104)]),
        ):
            outcome = ar.run(0, 1)
        assert outcome.status == "success"
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "new"

    def test_rejects_a_worse_candidate_and_keeps_live(self, layout, settings):
        settings.RETRAIN_MIN_NEW_SAMPLES = 50
        self._ready(layout)
        with (
            patch.object(ar, "fetch_new", return_value=60),
            patch.object(ar, "train_candidate", side_effect=lambda epochs: _model(layout["CANDIDATE"], "new") or "rev"),
            patch.object(ar, "calibrate_candidate", return_value=None),
            patch.object(ar, "holdout_metrics", return_value=[ar.HoldoutMetrics(ai_caught=100), ar.HoldoutMetrics(ai_caught=104, real_fake=1)]),
        ):
            outcome = ar.run(0, 1)
        assert outcome.status == "rejected"
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "old"
        assert not layout["CANDIDATE"].exists()

    def test_too_few_new_samples_skips(self, layout, settings):
        settings.RETRAIN_MIN_NEW_SAMPLES = 50
        self._ready(layout)
        with patch.object(ar, "fetch_new", return_value=10):
            outcome = ar.run(5, 1)
        assert outcome.status == "skipped"
        assert outcome.reason == "only 15 new approved samples, need 50"


@pytest.mark.django_db
class TestWeeklyTask:
    def test_records_rejection_with_metrics(self):
        outcome = ar.Outcome("rejected", "AI caught 100 -> 99", 70, "rev", {"live": {}, "candidate": {}})
        with patch.object(ar, "run", return_value=outcome), patch("analyzers.tasks._notify_retrain"), patch("analyzers.tasks._email_retrain"):
            run_id = run_weekly_retrain("image")
        run = RetrainRun.objects.get(pk=run_id)
        assert run.status == RetrainRun.Status.REJECTED
        assert run.error == "AI caught 100 -> 99"
        assert run.metrics == {"live": {}, "candidate": {}}
