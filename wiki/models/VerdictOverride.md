---
type: model
created: 2026-05-14
source: backend/content/models.py
---

# VerdictOverride

Human review trail. Staff override of automated `final_verdict` on a [[models/Submission]].

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `submission` | FK -> Submission | CASCADE |
| `reviewer` | FK -> User | SET_NULL nullable |
| `previous_verdict` | CharField | snapshot at override time |
| `new_verdict` | CharField | reviewer choice |
| `reason` | TextField | optional explanation |
| `created_at` | DateTime | auto |

## Flow

1. Submission lands in [[frontend/routes|/review queue]] when `final_verdict == "needs_review"` or `"inconclusive"`
2. Staff (`User.is_staff`) opens entry, picks `authentic` / `suspicious` / `likely_fake` / `fake` / `inconclusive`
3. POST to `/api/v1/content/submissions/:id/override/` creates VerdictOverride + updates Submission
4. `submission.verdict_overrides.count()` exposed via `ReviewQueueSerializer.override_count`

## See also

- [[models/Submission]]
- [[concepts/aggregation]] - needs_review escalation
- [[frontend/routes]] - /review page
