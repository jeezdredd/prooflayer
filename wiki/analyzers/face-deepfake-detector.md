---
type: analyzer
created: 2026-09-04
source: backend/analyzers/implementations/face_deepfake_detector.py
---

# Face Deepfake Detector

The ViT that used to run under the name `npr_detector`. Renamed 2026-09-04 when the real
[[npr-detector]] was implemented, because the old name was a lie: this is a face-swap
classifier, not Neighboring Pixel Relationships.

## Model

- HF: `Wvolf/ViT_Deepfake_Detection`
- Architecture: ViT base/16 at 224x224, 2-class softmax (`Real` / `Fake`)
- Trained on face deepfake data; the model card reports 98.7% on its own test split

## Measured

On the 120-image flickr-vs-diffusiondb set (landscapes, art, no portraits):

| AUC | acc@0.5 | mean_real | mean_ai |
|---|---|---|---|
| 0.688 | 0.608 | 0.104 | 0.273 |

Weak outside portrait imagery, which is why it sits at **weight 0.5**. It stays in the
registry because the product claims face-swap detection and nothing else in the ensemble is
trained on that. There is no labelled face-swap set in `dataset/` yet, so its real strength on
its home domain is unmeasured. See [[fixes/audit-2026-08]].

## Verdict thresholds

```python
ai_prob >= 0.85  -> fake, conf 0.8
ai_prob >= 0.65  -> suspicious, conf 0.6
ai_prob <  0.15  -> authentic, conf 0.8
ai_prob <  0.35  -> authentic, conf 0.6
else             -> inconclusive, conf 0.4
```

## Evidence shape

```json
{
  "model": "Wvolf/ViT_Deepfake_Detection",
  "ai_probability": 0.13,
  "training_corpus": "ViT fine-tuned on face deepfakes - weak outside portrait imagery (AUC 0.688 on general imagery)"
}
```

## See also

- [[npr-detector]] - the analyzer that now owns the `npr_detector` name
- [[siglip-detector]] - the other face-trained model, also at 0.5
- [[concepts/aggregation]]
