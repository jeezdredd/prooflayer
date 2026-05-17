---
type: analyzer
created: 2026-05-14
source: backend/analyzers/implementations/llm_analyzer.py
---

# Text LLM Analyzer

Classifies whether input text was likely AI-generated based on stylistic and structural cues.

## MIME

`text/plain`

## Model

Reads `settings.OLLAMA_MODEL`. Current dev: `qwen2.5:3b`. ~1.9 GB.

## Prompt

Instructs model to inspect:
- Sentence rhythm variety (humans vary length; LLMs tend to flatten)
- Lexical diversity vs token-level repetition
- Idiomatic vs templated phrasing
- Hallucinations / overconfident generalizations
- Boilerplate transitions ("In conclusion,", "It's important to note")

Response forced to JSON:

```json
{"verdict": "ai_generated|human_written|uncertain", "confidence": 0.0-1.0, "reasoning": "..."}
```

## HTTP call

`POST {OLLAMA_URL}/api/generate` with `format: "json"`, `stream: False`. Timeout 300s.

## Verdict mapping

```
ai_generated  -> fake
human_written -> authentic
uncertain     -> inconclusive
parse failure -> error
```

## Evidence shape

```json
{
  "llm_verdict": "ai_generated" | "human_written" | "uncertain",
  "reasoning": "..."
}
```

> [!key-insight] Model name stripped
> Used to include `"model": "qwen2.5:3b"`. Removed - see [[fixes/model-name-leak]].

## Memory

Stays in Ollama. Celery worker only HTTP-calls. With `OLLAMA_MAX_LOADED_MODELS=1`, text and vision models swap (cannot coexist).

## See also

- [[services/ollama]]
- [[analyzers/llm-vision]] - same Ollama, different model
- [[infrastructure/env-vars]] - OLLAMA_MODEL
