---
type: concept
created: 2026-05-14
updated: 2026-06-03
source: backend/analyzers/aggregator.py
---

# Verdict Aggregation

Combines per-analyzer [[models/AnalysisResult]] into `final_score` (0..1) + `final_verdict` label.

## Analyzer types

Analyzers split into two groups based on what they expose in `evidence`:

**Probabilistic** (ML detectors) - emit `evidence["ai_probability"]` as a calibrated float:
- `community_forensics` (weight 3.0)
- `npr_detector` (weight 2.5)
- `siglip_detector` (weight 1.5)
- `llm_vision` (weight varies, when it returns `ai_probability`)

**Rule-based** (heuristic analyzers) - emit verdict + confidence bucket, no raw probability:
- `metadata`, `ela`, `audio_spectrogram`, `llm_text`

## Hybrid weighted mean

For each decisive result (`AUTHENTIC | SUSPICIOUS | FAKE`):

```python
# probabilistic voter - use raw probability directly
if "ai_probability" in evidence and analyzer.name in PROBABILISTIC_ANALYZERS:
    effective_weight = analyzer.weight
    score_contribution = ai_probability * effective_weight

# rule-based voter - use VERDICT_SCORES bucket
else:
    VERDICT_SCORES = {AUTHENTIC: 0.0, SUSPICIOUS: 0.5, FAKE: 1.0}
    effective_weight = analyzer.weight * confidence
    score_contribution = VERDICT_SCORES[verdict] * effective_weight

final_score = sum(score_contributions) / sum(effective_weights)
```

This preserves signal granularity from ML models. `ai_probability=0.66` and `ai_probability=0.92` now produce different final scores instead of both mapping to `FAKE=1.0`.

## CF priority override

Before banding, check for high-confidence CommunityForensics:

```python
CF_PRIORITY_THRESHOLD = 0.92
CF_PRIORITY_PEERS = {"npr_detector", "siglip_detector"}

if cf.ai_probability >= 0.92 and any peer agrees (fake/suspicious):
    return (max(final_score, 0.85), "fake")
```

CF is the most defensible single signal (NeurIPS 2024, trained on 4803 generators).

## Corroboration

Fake verdict requires at least 2 confident voters (prevents single-detector conviction):

```python
MIN_CORROBORATING_FOR_FAKE = 2
CORROBORATION_CONFIDENCE_FLOOR = 0.5

# probabilistic voter counts if abs(ai_prob - 0.5) * 2 >= 0.5
# rule-based voter counts if confidence >= 0.5
```

## Disagreement detection (needs_review)

If `>= 2 fake-leaning` AND `>= 2 authentic-leaning` confident voters:
```python
return (final_score, "needs_review")
```

Forces human review instead of silently averaging contradicting signals.

## Score -> verdict bands

```python
def _band(score):
    if score < 0.35:  return "authentic"
    if score < 0.50:  return "suspicious"
    if score < 0.60:  return "inconclusive"
    if score < 0.75:  return "likely_fake"
    return "fake"
```

See [[concepts/verdict-thresholds]] for UI tone mapping.

## Output

Returns `(round(final_score, 4), final_verdict)`. Stored on [[models/Submission]].

Tests: `backend/analyzers/tests/test_aggregator.py` - 18 tests including hybrid math regression.
