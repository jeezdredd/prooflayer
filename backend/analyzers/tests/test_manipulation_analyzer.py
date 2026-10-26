from unittest import mock

import numpy as np
import pytest
from PIL import Image

from analyzers.implementations import manipulation_map as mm
from analyzers.manipulation.fusion import ManipulationMap, Region
from analyzers.models import AnalysisResult
from analyzers.serializers import AnalysisResultSerializer
from content.tests.factories import SubmissionFactory

from .factories import AnalysisResultFactory, AnalyzerConfigFactory


@pytest.fixture
def photo(tmp_path):
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (800, 600), (90, 120, 150)).save(path, format="JPEG", quality=92)
    return str(path)


def found(confidence="high"):
    fmap = np.zeros((300, 400), dtype=np.float32)
    fmap[50:100, 60:160] = 0.9
    region = Region(bbox=(120, 100, 320, 200), kind="inconsistent", confidence=confidence, methods=["catnet"], score=0.95, area_share=0.04)
    result = ManipulationMap(
        status="regions_found", abstain=False, reason="regions_accepted", score=0.9,
        regions=[region], map=fmap, method_scores={"catnet": 0.95}, input_class="jpeg",
    )
    return result, mock.Mock(timings={"catnet": (2.0, 1.5)})


class TestOrientation:
    @pytest.mark.parametrize("orientation, expected", [
        (1, [10, 20, 30, 60]),
        (3, [70, 40, 90, 80]),
        (6, [40, 10, 80, 30]),
        (8, [20, 70, 60, 90]),
    ])
    def test_boxes_follow_the_photo_rotation(self, orientation, expected):
        assert mm.orient_bbox([10, 20, 30, 60], (100, 100), orientation) == expected

    def test_portrait_phone_photo_swaps_the_size(self):
        assert mm.shown_size((4032, 3024), 6) == [3024, 4032]


@pytest.mark.django_db
class TestManipulationMapAnalyzer:
    def test_missing_weights_keep_the_map_quiet(self, photo, settings, tmp_path):
        settings.MANIPULATION_WEIGHTS_DIR = str(tmp_path / "none")
        mm._state["models"] = None
        out = mm.ManipulationMapAnalyzer().analyze(photo, {})
        assert out.verdict == "inconclusive"
        assert out.evidence["status"] == "abstain"
        assert out.evidence["reason"] == "unavailable"

    def test_huge_photo_is_not_queued_for_minutes(self, photo, settings):
        settings.MANIPULATION_MAX_PIXELS = 1000
        out = mm.ManipulationMapAnalyzer().analyze(photo, {})
        assert out.evidence["reason"] == "too_large"

    def test_found_region_is_saved_and_never_votes(self, photo, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        with mock.patch.object(mm, "_models", return_value=mock.Mock(safire=None)), \
                mock.patch.object(mm, "analyze_bytes", return_value=found()):
            out = mm.ManipulationMapAnalyzer().analyze(photo, {"submission_id": "abc"})
        assert out.verdict == "inconclusive"
        assert out.confidence == 0.0
        assert "ai_probability" not in out.evidence
        assert out.evidence["status"] == "regions_found"
        assert out.evidence["manipulation_suspected"] is True
        assert out.evidence["regions"][0]["bbox"] == [120, 100, 320, 200]
        assert out.evidence["map_path"].startswith("manipulation/abc")
        assert out.evidence["map_size"] == [400, 300]

    def test_medium_region_is_shown_but_not_suspected(self, photo, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        with mock.patch.object(mm, "_models", return_value=mock.Mock(safire=None)), \
                mock.patch.object(mm, "analyze_bytes", return_value=found("medium")):
            out = mm.ManipulationMapAnalyzer().analyze(photo, {"submission_id": "abd"})
        assert out.evidence["manipulation_suspected"] is False
        assert len(out.evidence["regions"]) == 1


@pytest.mark.django_db
class TestMapInResults:
    def _result(self, verdict):
        sub = SubmissionFactory(final_verdict=verdict)
        evidence = {"status": "regions_found", "reason": "regions_accepted", "regions": [{"bbox": [1, 2, 3, 4]}], "map_path": "manipulation/x.png"}
        return AnalysisResultFactory(
            submission=sub,
            analyzer=AnalyzerConfigFactory(name="manipulation_map", weight=0.0),
            verdict=AnalysisResult.Verdict.INCONCLUSIVE,
            confidence=0.0,
            evidence=evidence,
        )

    def test_map_link_is_signed_for_a_real_photo(self):
        data = AnalysisResultSerializer(self._result("authentic")).data
        assert data["evidence"]["map_url"]
        assert data["evidence"]["regions"]

    def test_whole_ai_picture_gets_no_map(self):
        data = AnalysisResultSerializer(self._result("likely_fake")).data
        assert "map_url" not in data["evidence"]
        assert data["evidence"]["regions"] == []
        assert data["evidence"]["reason"] == "whole_image_ai"
