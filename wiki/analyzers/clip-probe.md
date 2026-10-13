---
type: analyzer
created: 2026-10-13
source: backend/analyzers/implementations/clip_probe.py, backend/analyzers/clip_probe_core.py, backend/analyzers/management/commands/train_clip_probe.py
---

# CLIP probe

Logistic regression over frozen CLIP ViT-B/32 image features (the UniversalFakeDetect recipe).
Joined [[concepts/tribunal]] in 1.3 at weight **2.5**.

## Why it exists

community_forensics and the retrained [[analyzers/custom_detector]] are fine-tunes of the *same*
ViT, so on generators the backbone does not see they fail together. CLIP is a different backbone
trained on a different objective; its mistakes are not their mistakes.

It is also nearly free: `process_submission` already computes and stores the 512-d CLIP
embedding (`Submission.clip_embedding`) for provenance search. The analyzer reads it back, so
inference is one dot product (`features: "stored"` in evidence); it only runs CLIP itself when
the embedding is missing or the head uses a different backbone.

## Training

```bash
uv run python backend/manage.py train_clip_probe \
  --train-dir dataset/openfake --train-dir dataset/hf \
  --eval-dir dataset/openfake_test \
  --out ~/.cache/huggingface/prooflayer-retrained/clip_probe
```

Class-balanced L2 logistic regression with LBFGS in torch (no sklearn). Output: `head.json`
(backbone, bias, weights), `training_meta.json`; `calibration.json` is written by hand from the
eval. Embeddings cache with `--cache-dir`.

## Measured (held-out `dataset/openfake_test`, 100 real / 145 AI, 20 generators)

| backbone | AUC | real max | FPR / TPR at 0.70 |
|---|---|---|---|
| CLIP ViT-B/32 | 0.980 | 0.696 | 0% / 69% |
| CLIP ViT-L/14 | 0.986 | 0.668 | 0% / 60% |

L/14 is marginally better on AUC, costs a 1.7 GB download and several times the CPU, and its
embedding is not already stored. B/32 shipped.

On the generators the rest of the bench missed: gpt-image-2 0.77, sora-2 0.83, veo-3 0.77,
flux.2-klein 0.63 (mean raw score).

## Calibration

Real photos never scored above 0.696, so the map is a step just above it:
`(0,0) (0.70,0.50) (0.71,0.85) (1,1)`. Weight and map were chosen by simulating the eval JSON
through the real `aggregate()` and checked on a generator + real-photo split both ways
(real -> fake 0 in every half; weight 3.0 was slightly better but with less margin).

## See also

- [[concepts/tribunal]] (1.3 changelog), [[concepts/detector-evaluation]]
