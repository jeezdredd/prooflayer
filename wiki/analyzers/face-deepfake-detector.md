---
type: analyzer
created: 2026-09-04
source: backend/analyzers/implementations/face_deepfake_detector.py
status: not seeded (removed 2026-09-04)
---

# Face Deepfake Detector

The ViT that used to run under the name `npr_detector`. Renamed 2026-09-04 when the real
[[npr-detector]] was implemented, because the old name was a lie: this is a face-swap
classifier, not Neighboring Pixel Relationships.

> [!warning] Removed from the active roster 2026-09-04
> On 150 real / 236 AI OpenFake images across 20 current generators it scored **AUC 0.181** -
> strongly anti-correlated (mean 0.359 on real vs 0.138 on AI). Re-simulating the ensemble
> without it changed nothing on the AI side and nothing on real photos, so it was pure noise at
> weight 0.5. Same reasoning as [[siglip-detector]]: a face-trained model with no face-swap set
> to justify it. Module and tests stay; re-add to `seed_analyzers.ANALYZERS` to re-enable.

## Model

- HF: `Wvolf/ViT_Deepfake_Detection`
- Architecture: ViT base/16 at 224x224, 2-class softmax (`Real` / `Fake`)
- Trained on face deepfake data; the model card reports 98.7% on its own test split

## Measured

On the 120-image flickr-vs-diffusiondb set (landscapes, art, no portraits):

| AUC | acc@0.5 | mean_real | mean_ai |
|---|---|---|---|
| 0.688 | 0.608 | 0.104 | 0.273 |

Weak outside portrait imagery. It was kept at weight 0.5 for two weeks because the product
claims face-swap detection and nothing else in the ensemble is trained on that; the OpenFake
numbers above ended that. There is no labelled face-swap set in `dataset/` yet, so its real strength on
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
