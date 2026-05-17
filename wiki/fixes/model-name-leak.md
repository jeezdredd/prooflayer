---
type: fix
created: 2026-05-09
---

# Fix: model names stripped from evidence + UI

**Issue:** Evidence JSON exposed concrete model identifiers ("moondream", "qwen2.5:3b", HF repo names). User flagged - UI should not name specific models.

## Changes

**backend/content/serializers.py** - `ANALYZER_DESCRIPTIONS`:
- `"Vision LLM (moondream). Examines..."` -> `"Vision LLM. Examines..."`
- `"Text LLM (qwen2.5:3b). Classifies..."` -> `"Text LLM. Classifies..."`
- AI ensemble: "Ensemble of 3 image classifiers (Organika SDXL detector, dima806 BeiT, umm-maybe ViT). ..." -> "Ensemble of independent image classifiers. ..."

**backend/analyzers/implementations/llm_image_analyzer.py:124** - dropped `"model": vision_model` from evidence dict.

**backend/analyzers/implementations/llm_analyzer.py:71** - dropped `"model": model` from evidence dict.

**backend/analyzers/implementations/clip_detector.py:** - HF model name `name` replaced with anonymized `classifier_N` index in evidence:

```python
def _run_one(name, idx, image):
    label = f"classifier_{idx + 1}"
    return {"classifier": label, ...}
```

Top-level evidence key renamed `models` -> `classifiers`.

## Caveat

Vision LLM cold-load latency varies dramatically by model (3b: 10-15s, 7b: 60s+). UI shows generic "Cold-loading vision model..." tip via UploadProgress rotating tip cycle, without naming model.
