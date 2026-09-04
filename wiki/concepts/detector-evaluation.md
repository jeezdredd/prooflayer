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

## Related

- [[concepts/verdict-thresholds]]
- [[fixes/audit-2026-08]]
