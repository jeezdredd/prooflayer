---
updated: 2026-09-04
type: analyzer
created: 2026-05-29
source: backend/analyzers/implementations/community_forensics.py
---

# Community Forensics Detector

Best published zero-shot generalist for deepfake detection per detection plan. The "Park et al. (2024) Community Forensics" NeurIPS paper - trained on 2.7M images from 4803 generators. 75% mean accuracy across 12 datasets - dramatically better than detectors trained on a single generator family.

## Calibration (2026-09-04)

The model **ranks** 2026 generators almost as well as 2022 ones - AUC 0.977 on 20 OpenFake
generators vs 1.000 on diffusiondb - but its raw sigmoid sits far lower on them:

| set | real max | real p99 | AI p25 | AI median |
|---|---|---|---|---|
| diffusiondb (60/60) | | | 0.53 (p10) | 0.997 |
| OpenFake (150/236) | | | 0.012 | 0.323 |
| all 210 real | **0.147** | **0.0045** | | |

With the old fixed bands (fake >= 0.85, authentic < 0.35) the OpenFake median read as
*authentic*. Real photos never exceed 0.147 raw, so the low range can be lifted without
manufacturing false positives. `calibrate()` in `community_forensics.py` is a monotone
piecewise-linear map applied before the bands and before aggregation:

```python
CALIBRATION_KNOTS = ((0.0, 0.0), (0.005, 0.20), (0.10, 0.55), (0.50, 0.75), (1.0, 1.0))
```

Anchors: real p99 -> 0.20 (stays below `suspicious`), AI p25 -> 0.55, fit-set AI median
(raw ~0.50, diffusiondb + OpenFake) -> 0.75. Evidence keeps `raw_probability` next to the
calibrated `ai_probability`.

**Validation**: fitted on half the OpenFake generators + diffusiondb, tested on the other half,
both directions. Held-out AI-called-authentic fell 41% -> 31% and 38% -> 16%; real -> fake stayed
0/150 in every split; diffusiondb stayed at 0 AI-called-authentic. The shipped knots sit between
the two held-out fits rather than at the more aggressive full-data fit.

**Ceiling**: on flux.2-klein-9b, sora-2, gpt-image-2 and midjourney-7 the raw score is ~0 for
most images (flux.2 mean 0.003). No monotone map can separate what the model scores identically
to real photos; those generators need a different detector or a retrain. Measured numbers in
[[fixes/audit-2026-08]] and [[concepts/detector-evaluation]].

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
