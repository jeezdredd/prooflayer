---
type: analyzer
created: 2026-06-20
updated: 2026-09-04
source: backend/analyzers/implementations/custom_detector.py
---

# custom_detector

The member of [[concepts/tribunal]] that learns. Loads a fine-tuned image classifier from
`RETRAIN_MODEL_DIR/image` when one exists, otherwise falls back to `Nahrawy/AIorNot`.
Weight **3.5** since Tribunal 1.1 (was 1.5; was 3.5 before the first audit, when the weight was
a guess rather than a measurement).

Source: `backend/analyzers/implementations/custom_detector.py`. Seeded in `seed_analyzers.py`
(queue `ml`, timeout 180).

## Model source

- `RETRAIN_MODEL_DIR/image` (default `/root/.cache/huggingface/prooflayer-retrained/image`,
  the `hf_cache` volume on the worker) when a `config.json` exists there. The in-process cache
  keys on the path, so a new model is picked up on the next inference without a restart.
- Fallback `Nahrawy/AIorNot` (Swin, 2022-era). Measured AUC 0.920 on diffusiondb, **0.711** on
  current generators - the fallback is the weak member, not the strong one.
- Loads with `use_safetensors=True`, runs on the GPU when there is one (`_device`), reads
  `id2label` instead of trusting index order (a retrain with a different label order used to
  invert it silently).
- Evidence: `ai_probability`, `retrained`, and when retrained a `training` block from
  `training_meta.json` (base model, trained_at, epochs, class counts, number of sources,
  held-out accuracy) so a verdict names the exact model that produced it.

## The 2026-09-04 retrain

First retrain that was actually measured. Base model switched from AIorNot to the
[[community-forensics]] backbone (`buildborderless/CommunityForensics-DeepfakeDet-ViT`, 2.7M
images / 4,803 generators); the 1-logit head is replaced by a fresh 2-class head, the backbone
is fine-tuned end to end.

| | |
|---|---|
| training data | `dataset/openfake` (150 real LAION + 236 AI, 20 generators) + `dataset/hf` (250 real flickr + 500 diffusiondb) = 400 real / 736 AI |
| held-out inside the run | 114 images by source group, accuracy 1.000 |
| recipe | 3 epochs, batch 16, lr 2e-5, inverse-frequency class weights (1.41 / 0.77), horizontal flip, MPS, **130 s** |
| artefact | 83 MB safetensors, sha256 `719fc0d51962a0a6…`, `training_meta.json` alongside |

**Honest test**: `dataset/openfake_test` - a second OpenFake pull at a different row-group
offset, then `dedupe_dataset` against the training tree (13 exact perceptual-hash duplicates
removed; the offset alone does not guarantee disjointness). 100 real / 145 AI, 20 generators.

| detector on openfake_test | AUC | acc@0.5 | mean_real | mean_ai |
|---|---|---|---|---|
| custom_detector, AIorNot fallback | 0.711 | 0.653 | 0.329 | 0.606 |
| custom_detector, **retrained** | **0.993** | **0.943** | 0.092 | 0.962 |
| community_forensics (calibrated) | 0.965 | 0.776 | 0.011 | 0.536 |

Per generator the retrained model scores flux.2-klein-9b 0.91, gpt-image-2 0.998, sora-2 0.83,
veo-3 0.83 - the four the rest of the bench is blind to. diffusiondb (in-sample) 1.000.

Caveat that goes with the number: on the 100 held-out real photos its score reaches 0.975 at
the top (p99 0.967) and **5 photos sit at >= 0.75**. It is a strong ranker, not a calibrated
one, which is exactly why the aggregation rule for a lone voter demands p >= 0.9 *and* a
dominant weight share - see [[concepts/aggregation]].

## How it gets trained

1. **Review queue.** Staff override verdicts; `VerdictOverrideView` sets
   `submission.approved_for_training=True` + `verified_label=real|fake`.
2. **Bootstrap corpora on disk.** `manage.py retrain_detector --extra-dir <tree>` (repeatable)
   adds any `real/` + `ai_generated/` (or `fake/`) tree, symlinked into the training set and
   counted toward `--min-samples`. Unreadable files are skipped rather than crashing the Trainer
   (`dataset/hf/real` carries 250 zero-byte macOS stubs). If the Submission table is unavailable
   and extra dirs are given, it trains on the extra dirs alone.
3. `--base-model` picks the backbone (default still AIorNot; the measured recipe uses the CF id).
4. Split is by source group (`_sample_group`), so the 8 frames of one video never straddle
   train and eval. Inverse-frequency class weights unless `--no-class-weights`.
5. Output goes to `RETRAIN_MODEL_DIR/<media_type>` with `training_meta.json`; the Celery path
   (`POST /api/v1/analyzers/retrain/`, `run_weekly_retrain`) calls the same command.

```bash
RETRAIN_MODEL_DIR=~/.cache/huggingface/prooflayer-retrained \
uv run python backend/manage.py retrain_detector --media-type image --epochs 3 --min-samples 10 \
  --base-model buildborderless/CommunityForensics-DeepfakeDet-ViT \
  --extra-dir dataset/openfake --extra-dir dataset/hf
```

## Shipping a retrained model to the worker

The worker reads `/root/.cache/huggingface/prooflayer-retrained/image` inside the `hf_cache`
volume. `make ship-retrained` (untested against the server as of writing) rsyncs the local
model dir to the server and copies it into the volume through a throwaway alpine container;
the worker reloads on the next inference. Then `make seed-analyzers-server` if the weights in
`seed_analyzers.py` changed with the model, and check `/status` shows the new
[[concepts/tribunal]] version.

## Notes

- Video and audio retrains write to `RETRAIN_MODEL_DIR/video|audio`, which nothing loads yet.
- The retrained model shares its backbone with community_forensics, so their errors are
  correlated on anything CF already sees; the value is on the generators CF does not.
