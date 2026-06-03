---
type: analyzer
created: 2026-05-28
source: backend/analyzers/implementations/siglip_detector.py
---

# SigLIP Deepfake Detector

Binary classifier built on SigLIP-base backbone. Standalone signal-quality detector - `siglip_detector` analyzer.

## Model

- HF: `prithivMLmods/Deep-Fake-Detector-v2-Model`
- Architecture: SigLIP-base patch16 (Google), fine-tuned binary head fake/real
- License: Apache-2.0 (commercial OK)
- Size: ~360 MB safetensors
- CPU latency: ~400-800ms per image

## Verdict thresholds

```python
ai_prob >= 0.88  -> fake, conf 0.85
ai_prob >= 0.70  -> suspicious, conf 0.65
ai_prob <  0.15  -> authentic, conf 0.85
ai_prob <  0.30  -> authentic, conf 0.65
else             -> inconclusive, conf 0.4
```

Conservative on both sides: refuses to commit between 0.30 and 0.70. Pairs well with the existing `ai_detector` ensemble (dima806 + umm-maybe) - together they form the multi-voter corroboration the aggregator now requires for `fake` verdict.

## Weight in registry

`AnalyzerConfig.weight = 2.0` (heavier than `ai_detector` ensemble at 1.0 because SigLIP-base is the modern arch + higher reported accuracy).

## Loading

Module-level singleton (`_state`) lazy-loaded on first inference. ~360 MB resident in worker RAM after first request. Stays warm.

## Evidence shape

```json
{
  "model": "siglip-deepfake-v2",
  "ai_probability": 0.13,
  "per_label": {
    "Realism": 0.87,
    "Deepfake": 0.13
  }
}
```

Label keys vary by model card - `_ai_probability` aggregates by substring match (fake/ai/synthetic vs real/human/authentic).

## See also

- [[ai-ensemble]] - first AI detector (dima806 + umm-maybe)
- [[aggregator]] - corroboration-required logic
- [[detection-strategy-2026]] - Week 1-4 plan parent
