import json

import numpy as np
import pytest
from PIL import Image

from analyzers.clip_probe_core import load_head, predict, save_head, train_logreg
from analyzers.implementations import clip_probe
from content.tests.factories import SubmissionFactory


@pytest.fixture(autouse=True)
def _reset():
    clip_probe._state.update(head=None, calibration=None, dir=None)
    yield
    clip_probe._state.update(head=None, calibration=None, dir=None)


@pytest.fixture
def jpeg(tmp_path):
    path = tmp_path / "x.jpg"
    Image.new("RGB", (16, 16), (1, 2, 3)).save(path)
    return str(path)


def _head(directory, weights, bias, backbone="openai/clip-vit-base-patch32"):
    save_head(str(directory), backbone, np.asarray(weights, dtype=np.float64), bias, {"note": "test"})


class TestLogReg:
    def test_separable_data_is_learned(self):
        rng = np.random.default_rng(0)
        x = np.vstack([rng.normal(-1, 0.3, (50, 4)), rng.normal(1, 0.3, (50, 4))])
        y = np.array([0] * 50 + [1] * 50, dtype=np.float64)
        w, b = train_logreg(x, y, l2=1e-3)
        p = predict(x, w, b)
        assert (p[:50] < 0.5).all() and (p[50:] > 0.5).all()

    def test_head_round_trip(self, tmp_path):
        _head(tmp_path, [0.5, -0.25], 0.1)
        head = load_head(str(tmp_path))
        assert head["backbone"] == "openai/clip-vit-base-patch32"
        assert head["weights"].tolist() == [0.5, -0.25]
        assert json.loads((tmp_path / "training_meta.json").read_text())["note"] == "test"

    def test_missing_head_is_none(self, tmp_path):
        assert load_head(str(tmp_path)) is None


@pytest.mark.django_db
class TestCLIPProbeAnalyzer:
    def test_no_head_is_error(self, tmp_path, jpeg, monkeypatch):
        monkeypatch.setattr(clip_probe, "probe_dir", lambda: str(tmp_path / "missing"))
        out = clip_probe.CLIPProbeDetector().analyze(jpeg, {})
        assert out.verdict == "error"

    def test_uses_stored_embedding_and_scores(self, tmp_path, jpeg, monkeypatch):
        dim = 512
        weights = np.zeros(dim)
        weights[0] = 10.0
        _head(tmp_path, weights, -1.0)
        monkeypatch.setattr(clip_probe, "probe_dir", lambda: str(tmp_path))
        embedding = [0.0] * dim
        embedding[0] = 1.0
        sub = SubmissionFactory(clip_embedding=embedding)
        out = clip_probe.CLIPProbeDetector().analyze(jpeg, {"submission_id": str(sub.id)})
        assert out.evidence["features"] == "stored"
        assert out.evidence["raw_probability"] == pytest.approx(1 / (1 + np.exp(-9.0)), abs=1e-4)
        assert out.verdict == "fake"

    def test_dimension_mismatch_is_error(self, tmp_path, jpeg, monkeypatch):
        _head(tmp_path, [1.0, 2.0], 0.0)
        monkeypatch.setattr(clip_probe, "probe_dir", lambda: str(tmp_path))
        sub = SubmissionFactory(clip_embedding=[0.1] * 512)
        out = clip_probe.CLIPProbeDetector().analyze(jpeg, {"submission_id": str(sub.id)})
        assert out.verdict == "error"

    def test_calibration_file_is_applied(self, tmp_path, jpeg, monkeypatch):
        dim = 512
        _head(tmp_path, np.zeros(dim), 0.0)
        (tmp_path / "calibration.json").write_text(json.dumps({"knots": [[0, 0], [0.5, 0.1], [1, 1]]}))
        monkeypatch.setattr(clip_probe, "probe_dir", lambda: str(tmp_path))
        sub = SubmissionFactory(clip_embedding=[0.0] * dim)
        out = clip_probe.CLIPProbeDetector().analyze(jpeg, {"submission_id": str(sub.id)})
        assert out.evidence["raw_probability"] == pytest.approx(0.5)
        assert out.evidence["ai_probability"] == pytest.approx(0.1)
        assert out.verdict == "authentic"
