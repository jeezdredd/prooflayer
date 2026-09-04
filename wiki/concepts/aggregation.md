---
type: concept
created: 2026-05-14
updated: 2026-09-04
source: backend/analyzers/aggregator.py
---

# Verdict Aggregation

Combines per-analyzer [[models/AnalysisResult]] into `final_score` (0..1) + `final_verdict` label.

## Analyzer types

Group membership is decided **per result, from the evidence payload** - not from a
hardcoded analyzer-name list. `_get_ai_probability()` reads the first present key of
`PROBABILITY_KEYS = ("ai_probability", "ai_probability_avg")`, clamps it to `0..1`, and
returns `None` if absent or non-numeric.

**Probabilistic** - any result carrying one of those keys:
- `community_forensics` (weight 3.5, raw score calibrated - see [[analyzers/community-forensics]])
- `custom_detector` (3.5 since Tribunal 1.1, retrained on 20 current generators - see [[analyzers/custom_detector]])
- `ai_detector` (1.0 since Tribunal 1.1, via `ai_probability_avg`)
- `video_frame` (2.0, median over sampled frames)

**Rule-based** - verdict + confidence bucket, no raw probability:
- `metadata` (1.5), `audio_spectrogram` (2.0), `llm_text` (2.5), `llm_vision` (1.5)

**Manipulation-only** - never votes on the AI axis:
- `ela` (0.75). Always returns `inconclusive`, so it is excluded from `DECISIVE_VERDICTS` and
  from the weighted mean. It contributes only through `_has_manipulation_signal`, which reads
  `evidence["manipulation_suspected"]`. Measured AUC on the AI axis was *inverted*
  (38/60 real photos flagged vs 12/60 AI) - see [[fixes/audit-2026-08]].

> [!warning] Fixed 2026-08-19
> The old name-list put `llm_vision` in the probabilistic set, but that analyzer never
> emits `ai_probability` - so it was skipped by the probability loop **and** excluded from
> the rule-based loop. It contributed **zero weight** to every score while still voting in
> the corroboration count. Conversely `custom_detector` and `ai_detector` did emit
> probabilities that were thrown away and replaced with coarse 0.0/0.5/1.0 verdict buckets.
> See [[fixes/aggregator-probability-sourcing]].

## Disagreement -> `needs_review`

```python
DISAGREEMENT_MIN_VOTERS = 2
DISAGREEMENT_MIN_MINORITY_SHARE = 0.3
```

A confident voter is any result with `|ai_probability - 0.5| * 2 >= 0.5` (or, for rule-based
results, `confidence >= 0.5`). Review fires only when **both** camps have at least two voters
**and** the lighter camp carries at least 30% of the combined voter weight.

> [!change] 2026-09-04
> Previously any 2-vs-2 head count forced review. Real NPR (weight 1.0, saturated at p<0.01 on
> everything diffusion) plus the face ViT (0.5) then outvoted CF 3.5 + custom 1.5 + ai_detector
> 1.5 into `needs_review` on 27/60 AI images. Head counts do not survive one confidently wrong
> out-of-domain detector; weight shares do.

## Lone voter -> `fake` only when dominant and certain

```python
MIN_CORROBORATING_FOR_FAKE = 2
SINGLE_VOTER_MIN_SHARE = 0.5
SINGLE_VOTER_MIN_PROB = 0.9
```

A `fake` / `likely_fake` band normally needs two confident fake voters; with one it is
downgraded to `suspicious` / `inconclusive`. Exception (2026-09-04): a **single** fake voter
carries the band when its probability is >= 0.9 *and* its weight is at least half of the
combined weight of all confident voters (fake plus authentic).

> [!change] 2026-09-04 - why not just "one voter suffices"
> After the retrain, `custom_detector` sees flux.2 / gpt-image-2 / sora-2 / veo-3 at 0.83-0.998
> while every other member is blind, so the two-voter rule capped held-out recall at 35%. Lifting
> it to "any single voter" reached 92% on one weight set but produced a real photo called fake
> in three of four candidate rosters (the retrained model puts 5% of real photos above 0.75).
> The share + certainty version reached **71% caught with 0/100 real -> fake** under the
> Tribunal 1.1 weights. See [[fixes/audit-2026-08]].

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
CF_PRIORITY_PEERS = {"custom_detector", "ai_detector", "npr_detector", "siglip_detector"}

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
