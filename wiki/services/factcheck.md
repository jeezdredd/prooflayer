# factcheck

Async text fact-check pipeline. Extracts claims via NER, gathers DuckDuckGo + Wikipedia context, assesses with Ollama, cross-references Google Fact Check API, attaches sources.

## Pipeline (Celery task `run_factcheck`)

1. **extracting** (10%) - spaCy NER pulls claim sentences. Falls back to regex split if < 2 found.
2. **searching** (30%) - DuckDuckGo top-5 results + Wikipedia lookup for first 4 claims.
3. **assessing** (55%) - Ollama (`qwen2.5:3b` default, `qwen2.5:7b` optional) returns `{claim, assessment, confidence, explanation}` per claim. Aliases normalize stray values, confidence clamped 0-100.
4. **cross_referencing** (80%) - Google Fact Check API per claim, top-3 web sources attached, matched Wikipedia entry attached.
5. **done** (100%) - Result cached in Redis `fc:{task_id}` for 600s.

Stage TTL 600s. Soft limit 300s, hard 330s.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/factcheck/check/` | Dispatch `run_factcheck.delay(text)`. Returns `{task_id}`. |
| `GET` | `/api/v1/factcheck/status/{task_id}/` | Poll stage + progress + result. |
| `POST` | `/api/v1/factcheck/export/` | Render result + original text to PDF via WeasyPrint. |
| `POST` | `/api/v1/factcheck/fetch-url/` | SSRF-guarded fetch of article URL, Trafilatura extract. |
| `POST` | `/api/v1/factcheck/extract-doc/` | Multipart PDF/DOCX upload, returns extracted text. |

All endpoints require `IsVerifiedUser`. URL fetch capped at 1 MB, DOC upload at 10 MB.

## Claim shape

```python
{
  "claim": str,
  "assessment": "likely_true" | "likely_false" | "uncertain",
  "confidence": int,                       # 0-100
  "explanation": str,
  "sources": [{"title", "url"}, ...],      # DuckDuckGo top 3
  "wikipedia": {"title", "extract", "url"} | None,
  "fact_checks": [{"publisher", "rating", "url", "claim_text"}, ...]  # Google FCT
}
```

## Modules

- `backend/factcheck/services.py` - `lookup_wikipedia`, `search_web`, `_build_assessed_claims`, `_normalize_assessment`, `_normalize_confidence`, `format_search_context`, `match_wiki`.
- `backend/factcheck/tasks.py` - `run_factcheck` Celery task with stage cache writes.
- `backend/factcheck/views.py` - 5 views: Check, Status, Export, FetchUrl, ExtractDoc.
- `backend/factcheck/pdf.py` - `render_factcheck_pdf` (WeasyPrint).
- `backend/templates/factcheck/report.html` - print-friendly PDF template.
- `backend/common/url_safety.py` - `validate_public_url` (shared SSRF guard, also used by `content/views.py:AnalyzeUrlView`).

## Frontend

- `frontend/src/pages/FactCheckPage.tsx` - 3 input modes (text/url/document), claim cards with confidence bars + Wikipedia + sources, claim->source highlight panel, PDF export button.
- `frontend/src/hooks/useFactCheck.ts` - polls status every 1500ms, 5-min timeout.

## Dependencies

Added in `pyproject.toml`: `trafilatura`, `pypdf`, `python-docx`.

`docker-compose.yml` `ollama_init` pulls `qwen2.5:3b`, `qwen2.5vl:3b`, and `qwen2.5:7b` (best effort, `|| true` for VRAM-limited hosts).

## Switching to qwen2.5:7b

Set `OLLAMA_MODEL=qwen2.5:7b` on backend + worker containers. Needs ~6 GB VRAM; homelab currently OOMs on 12 GB ceiling. Keep `qwen2.5:3b` as default.

## Caveats

- DuckDuckGo is unauthenticated and rate-limits aggressively. Failures degrade silently (empty sources).
- Wikipedia lookup uses 8s timeout per query, up to 4 claims = ~32s worst case.
- LLM sometimes returns blank claim text; tasks.py pads any missing claim with the original NER sentence + `uncertain` fallback.
- Redis cache backend required for cross-process stage reads (LocMemCache was a bug, fixed 2026-06-18).
