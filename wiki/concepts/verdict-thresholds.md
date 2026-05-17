---
type: concept
created: 2026-05-14
---

# Verdict Thresholds

Maps `final_score` (0..1) -> human label + UI color tone.

| Score range | Verdict | UI color | Meaning |
|-------------|---------|----------|---------|
| < 0.30 | `authentic` | sage green | Confidently real |
| 0.30 - 0.44 | `suspicious` | amber | Mild concern |
| 0.45 - 0.54 | `inconclusive` | gray | Insufficient signal |
| 0.55 - 0.69 | `likely_fake` | amber-red | Probable synthetic |
| >= 0.70 | `fake` | blood red | Confidently synthetic |
| special | `needs_review` | violet | Human disagreement (any score) |
| special | `error` | gray | Pipeline crash |

Constants in [[concepts/aggregation]] (`backend/analyzers/aggregator.py:106-114`).

## Per-analyzer verdicts

Individual analyzers return:
- `authentic` | `suspicious` | `fake` | `inconclusive` | `error`

No `likely_fake` / `needs_review` at analyzer level. Those only emerge from aggregation.

## Frontend color mapping

See `frontend/src/components/AnalyzerTimeline.tsx:VERDICT_TONE`:

```ts
authentic:    text-signal-sage  / bg-signal-sage/10
suspicious:   text-signal-amber / bg-signal-amber/10
fake:         text-signal-blood / bg-signal-blood/10
inconclusive: text-ink-300      / bg-ink-800
error:        text-ink-400      / bg-ink-800
```

## See also

- [[concepts/aggregation]] - how score is computed
- [[concepts/disagreement-needs-review]] - escalation rule
- [[models/AnalysisResult]] - storage schema
