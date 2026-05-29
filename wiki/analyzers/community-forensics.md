---
type: analyzer
created: 2026-05-29
source: backend/analyzers/implementations/community_forensics.py
---

# Community Forensics Detector

Best published zero-shot generalist for deepfake detection per detection plan. The "Park et al. (2024) Community Forensics" NeurIPS paper - trained on 2.7M images from 4803 generators. 75% mean accuracy across 12 datasets - dramatically better than detectors trained on a single generator family.

## Model

- HF: `buildborderless/CommunityForensics-DeepfakeDet-ViT`
- Architecture: ViT-Small/16 at 384x384 (~22M params)
- Output: single sigmoid head (binary fake vs real)
- License: MIT
- Size: ~85 MB safetensors
- CPU latency: ~300-600ms per image
- Downloads on HF: 794k+ (well-validated by community)

## Why this matters

Plan section "Image detection" picked Community Forensics as the strongest single zero-shot generalist - because training-data diversity (4803 generators) drives generalisation, not architecture. This solves the right problem.

Other detectors collapse on new generators (Flux, Firefly v4, MJ v7 -> 18-30% acc per arXiv 2602.07814). Community Forensics holds 75% mean across 12 OOD benchmarks.

## Verdict thresholds

```python
ai_prob >= 0.85  -> fake, conf 0.85
ai_prob >= 0.65  -> suspicious, conf 0.65
ai_prob <  0.15  -> authentic, conf 0.85
ai_prob <  0.35  -> authentic, conf 0.65
else             -> inconclusive, conf 0.4
```

Wider trustable range than [[siglip-detector]] because the model is more reliable on OOD.

## Weight in registry

`AnalyzerConfig.weight = 3.0` (highest among AI detectors because it is the most defensible against generator drift).

## Pipeline impact

Adding this gives the aggregator three independent AI detectors:
- `ai_detector` (dima806 + umm-maybe ensemble) - older, weight 1.0
- `siglip_detector` (SigLIP-v2, weight 2.0)
- `community_forensics` (this, weight 3.0) - main authority

Three voters provides corroboration the aggregator now requires (>=2 fake votes) without relying on a single noisy detector.

## Evidence shape

```json
{
  "model": "community-forensics-vit-s16-384",
  "ai_probability": 0.13,
  "training_corpus": "2.7M images from 4803 generators (NeurIPS 2024)"
}
```

## See also

- [[ai-ensemble]] - dima806 + umm-maybe
- [[siglip-detector]] - second AI signal
- [[aggregator]] - corroboration policy
- [[detection-strategy-2026]] - parent plan
