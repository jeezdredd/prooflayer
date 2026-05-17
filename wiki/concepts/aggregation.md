---
type: concept
created: 2026-05-14
source: backend/analyzers/aggregator.py
---

# Verdict Aggregation

Combines per-analyzer [[models/AnalysisResult]] into `final_score` (0..1) + `final_verdict` label.

## Verdict -> score map

```python
VERDICT_SCORES = {
    AUTHENTIC:     0.0,   # not fake
    SUSPICIOUS:    0.5,
    FAKE:          1.0,   # fake
    INCONCLUSIVE:  0.5,
}
```

Higher = more "fake".

## Filter passes

1. Drop `ERROR` verdicts (analyzer crashed)
2. If no valid results at all -> return `(0.5, "inconclusive")`
3. If all valid results are `INCONCLUSIVE` -> return `(0.5, "inconclusive")` (decisive empty)

## Weighted mean

For each surviving result:

```python
effective_weight = analyzer.weight * result.confidence
weighted_score += VERDICT_SCORES[result.verdict] * effective_weight
total_weight   += effective_weight
final_score = weighted_score / total_weight
```

`AnalyzerConfig.weight` is admin-tunable. Default 1.0. Larger weight on stronger analyzers (e.g. AI ensemble or VLM may carry more vote than ELA).

## Disagreement detection (needs_review)

After scoring, check if any two HIGH-confidence (>= 0.6) results disagree:

```python
confident = [r for r in valid if r.confidence >= 0.6]
verdicts = {r.verdict for r in confident}
has_disagreement = (
    AUTHENTIC in verdicts
    and (FAKE in verdicts or SUSPICIOUS in verdicts)
)
if has_disagreement:
    return (score, "needs_review")
```

> [!key-insight] Escalation rule
> When ELA says "authentic" with 0.7 confidence but AI ensemble says "fake" with 0.9, we DO NOT silently average. We flag `needs_review` so a human inspects. See [[fixes/disagreement-rule]].

## Score -> verdict thresholds

```
score < 0.30  -> authentic
score < 0.45  -> suspicious
score < 0.55  -> inconclusive
score < 0.70  -> likely_fake
score >= 0.70 -> fake
```

See [[concepts/verdict-thresholds]] for buckets + UI tone mapping.

## Output

Returns `(round(final_score, 4), final_verdict)`. Stored on [[models/Submission]] fields.
