---
type: analyzer
created: 2026-05-14
source: backend/analyzers/implementations/clip_detector.py
---

# AI Image Ensemble (HF classifier vote)

Two independent HuggingFace transformer classifiers vote on AI-generated probability. Pre-filtered by photographic-content check.

## MIME

`image/jpeg`, `image/png`, `image/webp`

## Models (`ENSEMBLE_MODELS`)

```python
ENSEMBLE_MODELS = [
    "dima806/ai_vs_real_image_detection",
    "umm-maybe/AI-image-detector",
]
```

> [!stale] Removed Organika
> `Organika/sdxl-detector` was in ensemble until 2026-05-09. Removed because HF model files unavailable / load failed mid-task -> OOM cascade. See [[fixes/organika-broken]].

## Cache strategy

```python
_MAX_CACHED = 1
_model_cache: dict[str, tuple]  # name -> (model, extractor)
```

Only one model resident in RAM at a time. Eviction triggers `gc.collect()` + `torch.cuda.empty_cache()` (no-op on CPU but kept for GPU portability).

## Photographic pre-filter

`_photographic_score(image)` runs first. Stats on 256x256 downscale:

```python
unique_colors = len(unique colors after //4 quantization)
entropy       = Shannon entropy of 64-bin grayscale histogram
flat_score    = mean abs diff (edge density)

is_photo = unique_colors > 4000 and entropy > 5.2 and flat_score > 5.0
```

If `is_photographic == False` -> return `(0.5, "inconclusive")` with note `"image looks like a screenshot/diagram/UI - AI photo detectors unreliable on non-photographic content"`.

> [!warning] Video frames false-negative
> AI-generated video (e.g. Veo 3) often has smooth gradients that fall below entropy threshold. Frame analyzer was returning all-inconclusive. Fix: [[concepts/skip-photo-check]] flag in metadata.

## Per-model run

```python
def _run_one(name, idx, image):
    label = f"classifier_{idx+1}"  # anonymized
    model, extractor = _load_model(name)
    inputs = extractor(images=image, return_tensors="pt")
    outputs = model(**inputs)
    probs = softmax(outputs.logits)
    ai_prob = _ai_prob_from_outputs(model, probs)
    return {classifier, ai_probability, per_label, ok}
```

`_ai_prob_from_outputs` introspects `model.config.id2label`, sums probabilities matching keywords:
- AI keys: ai, artificial, fake, synthetic, generated, ai-generated, ai_generated
- Real keys: real, human, authentic, natural, genuine

Returns normalized `ai_total / (ai_total + real_total)`.

## Verdict logic

```python
ai_avg = mean(ai_probabilities)
ai_max = max(ai_probabilities)
agreement = count(ai_prob > 0.5)

if ai_avg > 0.75 or (ai_avg > 0.6 and agreement >= 2): fake @ 0.9
elif ai_avg > 0.55 or (ai_max > 0.7 and agreement >= 1): suspicious @ 0.7
elif ai_avg < 0.25: authentic @ 0.85
elif ai_avg < 0.4:  authentic @ 0.7
else:               inconclusive @ 0.5
```

## Evidence shape

```json
{
  "ensemble_size": 2,
  "ai_probability_avg": 0.5699,
  "ai_probability_max": 0.9904,
  "ai_models_voting_fake": 1,
  "content_check": {entropy, edge_density, is_photographic, unique_colors_q4},
  "classifiers": [
    {classifier: "classifier_1", ai_probability, per_label, ok: true},
    ...
  ]
}
```

> [!key-insight] Model name stripped
> Evidence uses anonymized `classifier_1` / `classifier_2` not HF model IDs. See [[fixes/model-name-leak]].

## Memory

Each HF model ~200-500MB. With `_MAX_CACHED=1`, peak ~500MB. During eviction, brief 2x window (both models held while gc fires).

## See also

- [[analyzers/_index]]
- [[concepts/skip-photo-check]]
- [[fixes/organika-broken]]
- [[fixes/model-name-leak]]
- [[infrastructure/memory-limits]]
