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

    def test_reasoning_is_asked_in_russian_and_kept_as_is(self, post, image_path):
        reasoning = "У девушки на левой руке шесть пальцев, надпись на вывеске не читается."
        post.return_value = _reply("ai_generated", reasoning)
        out = LLMImageAnalyzer().analyze(image_path, {})
        assert "Russian" in post.call_args.kwargs["json"]["prompt"]
        assert out.evidence["reasoning"] == reasoning
        assert out.evidence["weak_reasoning"] is False
        assert "note" not in out.evidence

    def test_short_reasoning_is_flagged_not_rewritten_in_english(self, post, image_path):
        post.return_value = _reply("ai_generated", "Похоже на ИИ.")
        out = LLMImageAnalyzer().analyze(image_path, {})
        assert out.verdict == "inconclusive"
        assert out.evidence["weak_reasoning"] is True
        assert out.evidence["reasoning"] == "Похоже на ИИ."


@patch("analyzers.implementations.llm_image_analyzer.http_requests.post")
def test_request_is_deterministic_and_names_model(post, image_path, settings):
    settings.OLLAMA_VISION_MODEL = "qwen2.5vl:7b"
    post.return_value = _reply("human_photo", "No concrete defects are visible and the image looks like a normal photograph.")
    out = LLMImageAnalyzer().analyze(image_path, {})
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "qwen2.5vl:7b"
    assert payload["options"] == {"temperature": 0}
    assert out.evidence["model"] == "qwen2.5vl:7b"
