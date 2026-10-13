---
type: api
created: 2026-10-13
source: backend/content/{intake,batch_views}.py, frontend/src/pages/BatchPage.tsx
---

# Batch upload

`POST /api/v1/content/batches/` (multipart, verified users, throttle scope `batch` 10/hour):
any number of `files` and/or ZIP archives, optional `name`. Up to 100 accepted files per batch.
Works with browser sessions and API keys (each submission gets `api_key`, so webhooks fire per
file).

## Intake (`content/intake.py`)

Single source of truth for creating submissions; the single-file `SubmissionViewSet.create` and
`reanalyze` use the same `check_quota` / `create_submission`.

- Quota is checked for the **whole batch** before anything is created: 402 with
  `requested`, `used`, `limit`. No partial batches.
- Unsupported files are not an error; they come back in `skipped: [{name, reason}]`, stored on
  the batch. A batch where nothing is supported is 400.
- ZIP guards: <= 500 entries, declared total <= 512 MB, each member <= 50 MB (checked against the
  header *and* the bytes actually read), compression ratio <= 200 (a 5 MB run of zeros is
  skipped), `__MACOSX/` and dotfiles ignored, **basename only** - `../../etc/evil.jpg` is stored
  as `evil.jpg`. Corrupt archives are skipped, not 500s.

## Read

- `GET /content/batches/` (owner's), `GET /content/batches/<id>/` - `summary`
  (`total`, `done`, `by_status`, `by_verdict`) and `items` (id, filename, mime, status, verdict,
  score, tribunal_version).
- `GET /content/batches/<id>/export.csv/` - filenames are user-controlled, so every cell starting
  with `= + - @ \t \r` is prefixed with `'` (spreadsheet formula injection).

## Frontend

The Verify dropzone accepts several files or a ZIP (single file keeps the old flow) and routes to
`/batches/:id`: progress bar, flagged-first table linking to each result, skipped list, CSV.
