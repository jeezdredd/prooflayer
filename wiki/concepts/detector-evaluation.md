---
type: concept
created: 2026-08-19
source: backend/analyzers/management/commands/eval_detectors.py
---

# Detector Evaluation

Offline harness for measuring what the image analyzers actually do on labelled data, instead of
trusting the thresholds baked into each analyzer.

```bash
uv run python backend/manage.py eval_detectors \
  --dataset dataset/hf \
  --limit 60 \
  --json-out /tmp/eval.json
```

## Layout

The dataset dir needs class subdirectories. `real/` is label 0, `ai_generated/` and `fake/` are
label 1.

```
dataset/hf/
  real/            <- label 0
  ai_generated/    <- label 1
```

## What it does

For each image it calls `extract_metadata` once, then runs every analyzer in `DEFAULT_ANALYZERS`
and feeds the outputs through the **real** [[concepts/aggregation]] `aggregate()` using
lightweight stand-in result objects, so the ensemble number reflects production weights.

Reported per analyzer:

| column | meaning |
|---|---|
| `n` | results that carried an `ai_probability` (or `ai_probability_avg`) |
| `AUC` | rank-based, tie-corrected; threshold-independent |
| `acc@0.5` | accuracy using the naive 0.5 cut |
| `mean_real` / `mean_ai` | mean score per true class - the separation gap |
| `err` | analyzer returned `error` or raised |
| `s/img` | wall-clock per image |

`AUC` and `acc@0.5` diverging is the signal that a detector **ranks** well but is
**miscalibrated** - the fix is the threshold, not the model.

## Gotchas

- Analyzers with no probability (`metadata`, `ela`) show `-` in the score columns. They still
  contribute to the ensemble row through the verdict-bucket path.
- Unreadable files are skipped and counted. Half of `dataset/hf/real` is 212-byte macOS
  quarantine stubs rather than JPEGs, so the effective real-class size is 250, not 500.
- `--skip llm_vision` is implicit: the LLM analyzers are not in `DEFAULT_ANALYZERS` because they
  need a reachable Ollama.
- `DEFAULT_ANALYZERS` mirrors the seeded image roster. `npr_detector` (real NPR) is deliberately
  absent: it measured AUC 0.499 here and is not seeded. Add it back to the list to re-measure.
- The ensemble row runs the real `aggregate()` including the weighted-disagreement rule, so a
  detector that is confidently wrong shows up twice: in its own AUC and in the
  `needs_review` count.
- Set `PROOFLAYER_FORCE_CPU=1` to run without a GPU.

## Modern-generator sample: `fetch_openfake`

`dataset/hf` is diffusiondb (2022 SD 1.x) vs flickr - every current detector separates it
perfectly, which says nothing about 2026 generators. [OpenFake](https://huggingface.co/datasets/ComplexDataLab/OpenFake)
(`ComplexDataLab/OpenFake`, **CC-BY-NC-4.0** - local evaluation only, never redistribute)
has 20+ current generators with a `model` column and 3M real LAION images.

```bash
uv run python backend/manage.py fetch_openfake \
  --out dataset/openfake --per-model 12 --real 150
```

Writes `real/real__NNNN.png` and `ai_generated/<model-slug>__NNN.png`; `eval_detectors` reads the
`<generator>__` prefix and prints a per-generator table (share of AI images the ensemble called
`fake`/`likely_fake`, plus mean `ai_probability` per detector).

> [!warning] Shards are ~5 GB each
> `datasets.load_dataset(..., streaming=True)` materialises whole row groups of image bytes and
> was OOM-killed on the first shard. The command reads parquet **row groups** through
> `HfFileSystem` + `pyarrow`, fetching `label`/`model` first and decoding only the rows it keeps,
> and round-robins across the 13 test shards so one shard's ordering cannot skew the model mix.
> First run yielded 150 real + 236 AI over 20 generators (11-12 each).

## Held-out protocol for retrains

A retrain must never be scored on images it trained on. The protocol used for Tribunal 1.1:

1. Train on `dataset/openfake` + `dataset/hf` (everything in those trees is training data now).
2. Pull a **second** OpenFake sample with a different offset:
   `fetch_openfake --out dataset/openfake_test --per-model 8 --real 100 --start-row-group 6`.
3. `dedupe_dataset --target dataset/openfake_test --against dataset/openfake` - the offset does
   not guarantee disjointness (13 exact duplicates the first time). Run once at distance 0 and
   once at `--max-distance 4` for re-encodes.
4. Baseline `eval_detectors --dataset dataset/openfake_test` with the model dir **unset**, then
   the same with `RETRAIN_MODEL_DIR` pointing at the new model. Same images, same everything
   else, so the diff is the model.
5. `dataset/hf` afterwards is an in-sample sanity check only; label it as such.

Any weight or rule change is then simulated offline from the eval JSON with the real
`aggregate()` (stand-in result objects) before touching `seed_analyzers.py`, with
real -> fake = 0 on every held-out real photo as a hard constraint. Simulations have matched
the subsequent real reruns exactly every time so far.

## Related

- [[concepts/verdict-thresholds]]
- [[fixes/audit-2026-08]]
