import json
import logging

import requests as http_requests
from django.conf import settings

from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

LLM_PROMPT = """You are an AI content detection expert. Analyze the following text and determine if it was written by an AI or a human.

Consider:
- Repetitive or formulaic sentence structures
- Lack of personal voice or lived experience
- Overly neutral, balanced, or generic phrasing
- Absence of specific details, humor, or emotion
- Perfect grammar with no natural errors

Respond ONLY with JSON:
{{"verdict": "ai_generated|human_written|uncertain", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

Text:
{text}"""


class LLMTextAnalyzer(BaseAnalyzer):
    name = "llm_text"
    version = "1.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["text/plain"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(5000)
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})

        if len(text.strip()) < 50:
            return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence={"reason": "text too short"})

        ollama_url = getattr(settings, "OLLAMA_URL", "http://ollama:11434")
        model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")

        try:
            response = http_requests.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": LLM_PROMPT.format(text=text), "stream": False, "format": "json"},
                timeout=120,
            )
            response.raise_for_status()
            raw = response.json().get("response", "{}")
            data = json.loads(raw)

            llm_verdict = data.get("verdict", "uncertain")
            llm_confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            if llm_verdict == "ai_generated":
                verdict = "fake"
            elif llm_verdict == "human_written":
                verdict = "authentic"
            else:
                verdict = "inconclusive"

            return AnalysisOutput(
                confidence=llm_confidence,
                verdict=verdict,
                evidence={"llm_verdict": llm_verdict, "reasoning": reasoning, "model": model},
            )
        except Exception as exc:
            logger.warning("LLM text analysis failed: %s", exc)
            return AnalysisOutput(confidence=0.5, verdict="inconclusive", evidence={"error": str(exc)})
