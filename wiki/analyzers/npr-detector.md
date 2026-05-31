---
type: analyzer
created: 2026-05-31
source: backend/analyzers/implementations/npr_detector.py
---

# NPR Detector

ViT-based deepfake detector. Replaces the dropped `ai_detector` (dima806 + umm-maybe) ensemble. Second corroborating signal alongside [[community-forensics]] and [[siglip-detector]].

## Model

- HF: `Wvolf/ViT_Deepfake_Detection`
- Architecture: ViT base/16 at 224x224
- Output: 2-class softmax (real / fake)
- License: see HF model card

## Why this matters

dima806 was the noise generator on the previous ensemble (false-positives on real photographs). NPR detector is part of [[detection-strategy-2026]] - it ships a more defensible signal for the corroboration rule in the aggregator.

## Verdict thresholds

```python
ai_prob >= 0.85  -> fake, conf 0.8
ai_prob >= 0.65  -> suspicious, conf 0.6
ai_prob <  0.15  -> authentic, conf 0.8
ai_prob <  0.35  -> authentic, conf 0.6
else             -> inconclusive, conf 0.4
```

## Weight in registry

`AnalyzerConfig.weight = 2.5`. Lower than CommunityForensics (3.0) - CF remains the main authority. Sits in the `CF_PRIORITY_PEERS` set so it can rubber-stamp a CF high-confidence verdict via the aggregator override.

## Evidence shape

```json
{
  "model": "vit-deepfake-detector",
  "ai_probability": 0.13,
  "training_corpus": "ViT fine-tuned for deepfake detection"
}
```

## See also

- [[community-forensics]] - main authority
- [[siglip-detector]] - corroborator
- [[aggregator]] - CF priority override rule
- [[detection-strategy-2026]] - parent plan
