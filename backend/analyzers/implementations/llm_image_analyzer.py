import base64
import json
import logging

import requests as http_requests
from django.conf import settings

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

LLM_IMAGE_PROMPT = """You are an expert forensic image analyst specializing in detecting AI-generated images.

Carefully examine this image and analyze:
1. Lighting consistency — does light source make physical sense everywhere?
2. Texture coherence — skin, hair, fabric, backgrounds look natural or overly smooth/repetitive?
3. Fine details — fingers, teeth, eyes, ears, text — AI often fails these
4. Background — blurry, warped, inconsistent patterns?
5. Overall aesthetic — too perfect, dreamlike, uncanny valley?

Based on your analysis, respond ONLY with JSON:
{"verdict": "ai_generated|human_photo|uncertain", "confidence": 0.0-1.0, "reasoning": "2-3 sentences explaining key artifacts found or absent"}"""


class LLMImageAnalyzer(BaseAnalyzer):
    name = "llm_vision"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        ollama_url = getattr(settings, "OLLAMA_URL", "http://ollama:11434")
        vision_model = getattr(settings, "OLLAMA_VISION_MODEL", "llava:7b")

        try:
            with open(file_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})

        try:
            response = http_requests.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": vision_model,
                    "prompt": LLM_IMAGE_PROMPT,
                    "images": [image_b64],
                    "stream": False,
                    "format": "json",
                },
                timeout=300,
            )
            response.raise_for_status()
            raw = response.json().get("response", "{}")
            data = json.loads(raw)

            llm_verdict = data.get("verdict", "uncertain")
            llm_confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            if llm_verdict == "ai_generated":
                verdict = "fake"
            elif llm_verdict == "human_photo":
                verdict = "authentic"
            else:
                verdict = "inconclusive"

            return AnalysisOutput(
                confidence=llm_confidence,
                verdict=verdict,
                evidence={"llm_verdict": llm_verdict, "reasoning": reasoning, "model": vision_model},
            )
        except Exception as exc:
            logger.warning("LLM vision analysis failed: %s", exc)
            return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence={"error": str(exc)})
