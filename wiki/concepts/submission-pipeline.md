---
type: concept
created: 2026-05-14
---

# Submission Pipeline

End-to-end flow from user upload to final verdict.

## 1. Upload (HTTP)

`POST /api/v1/content/submissions/` (multipart, JWT auth)

- `content/views.py` view creates [[models/Submission]] row, status=`pending`
- File saved to MinIO via `default_storage` (`storage_utils.local_file` later pulls back to local fs for analyzer access)
- `content/services.py` computes:
  - `sha256_hash` (deduplication / known-fake check)
  - `phash`, `dhash` (perceptual hashes for similarity)
  - `mime_type`, `file_size`
  - `thumbnail` if image/video
- Frontend redirects to `/results/:id`, polls via [[api/endpoints|content.detail]]

## 2. Dispatch (Celery)

`content/tasks.py:process_submission` queued by post-save signal:

```python
# pseudo
def process_submission(submission_id):
    submission.status = "processing"
    analyzers.tasks.dispatch_analysis.delay(submission_id)
```

`analyzers/tasks.py:dispatch_analysis`:

```python
configs = AnalyzerConfig.objects.filter(is_active=True)
tasks = [run_analyzer.s(submission_id, c.id).set(queue=c.queue, soft_time_limit=c.timeout, time_limit=c.timeout + 30) for c in configs]
chord(group(tasks))(aggregate_verdicts.s(submission_id))
```

> [!key-insight] Celery chord
> All analyzers fan out in parallel. When ALL complete (success or failure), `aggregate_verdicts` callback fires once. See [[concepts/aggregation]].

## 3. Per-analyzer (run_analyzer)

For each `AnalyzerConfig`:

1. Load analyzer class via `analyzers/registry.py:load_analyzer_class`
2. MIME guard: `analyzer.supported_mime_types()` -> skip if not supported (logs `"Analyzer X does not support Y, skipping"`)
3. Set `submission.status_message` to user-facing label from `ANALYZER_STATUS_MESSAGES`
4. `with local_file(submission.file) as path:` (pulls from MinIO to tmpfs)
5. Call `analyzer.analyze(path, submission.metadata)` -> returns [[concepts/AnalysisOutput]]
6. Save [[models/AnalysisResult]] row with verdict + confidence + evidence + execution_time

> [!note] Failure isolation
> If a single analyzer raises, it logs and creates an `AnalysisResult` with verdict=`error`. Chord still resolves; aggregator filters errors.

## 4. Aggregate (chord callback)

`analyzers/tasks.py:aggregate_verdicts` runs after all `run_analyzer` complete:

1. Collect all `AnalysisResult` for the submission
2. Call `analyzers/aggregator.py:aggregate(results)` -> `(final_score, final_verdict)`. See [[concepts/aggregation]]
3. Update submission: `final_score`, `final_verdict`, `status=completed`, `status_message=""`

## 5. Display

Frontend `ResultPage` polls `GET /api/v1/content/submissions/:id/` via tanstack query. When status flips to `completed`, [[frontend/sidebar-layout|UI]] renders [[analyzers/_index|AnalyzerTimeline]] with collapsible per-analyzer evidence cards.

## 6. Community + override

Optional follow-ups (not blocking pipeline):

- Crowdsource votes via `/api/v1/crowdsource/` (Real / Fake / Uncertain)
- Staff override via [[models/VerdictOverride]] from `/review` queue

## Failure modes seen

- Worker SIGKILL during HF model load -> [[fixes/oom-sigkill]]
- Frame analyzer all-inconclusive -> photo_check false-negative on AI video, fixed by [[concepts/skip-photo-check]]
- Organika HF model unable to load -> dropped, see [[fixes/organika-broken]]
