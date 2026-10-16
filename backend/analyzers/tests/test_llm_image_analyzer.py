import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from analyzers.implementations.llm_image_analyzer import LLMImageAnalyzer


@pytest.fixture
def image_path():
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    Image.new("RGB", (64, 64), (200, 150, 120)).save(f, format="JPEG")
    f.close()
    return f.name


def _reply(verdict: str, reasoning: str) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"response": json.dumps({"verdict": verdict, "confidence": 0.8, "reasoning": reasoning})}
    return response


@patch("analyzers.implementations.llm_image_analyzer.http_requests.post")
class TestVisionVerdicts:
    def test_no_defect_found_abstains(self, post, image_path):
        post.return_value = _reply("human_photo", "No concrete defects are visible and the image looks like a normal photograph.")
        out = LLMImageAnalyzer().analyze(image_path, {})
        assert out.verdict == "inconclusive"
        assert out.evidence["llm_verdict"] == "human_photo"

    def test_named_defect_votes_fake(self, post, image_path):
        post.return_value = _reply("ai_generated", "The left hand in the lower corner has six fingers and the sign text is not a word.")
        out = LLMImageAnalyzer().analyze(image_path, {})
        assert out.verdict == "fake"


@patch("analyzers.implementations.llm_image_analyzer.http_requests.post")
def test_request_is_deterministic_and_names_model(post, image_path, settings):
    settings.OLLAMA_VISION_MODEL = "qwen2.5vl:7b"
    post.return_value = _reply("human_photo", "No concrete defects are visible and the image looks like a normal photograph.")
    out = LLMImageAnalyzer().analyze(image_path, {})
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "qwen2.5vl:7b"
    assert payload["options"] == {"temperature": 0}
    assert out.evidence["model"] == "qwen2.5vl:7b"
