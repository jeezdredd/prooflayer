---
type: fix
created: 2026-05-13
---

# Em-dash purge

**Rule:** Never use long em-dash `—` anywhere. Only ASCII hyphen `-`.

Reason: user preference. Annoyed by AI-style em-dash overuse.

## Applied

Batch sed across 15 files:

```bash
for f in <files>; do sed -i '' 's/—/-/g' "$f"; done
```

Files touched:
- `frontend/index.html`
- `frontend/src/index.css`
- `frontend/src/components/{UploadForm,ResultCard,SubmissionTable}.tsx`
- `frontend/src/pages/{LandingPage,StatusPage,ComparePage}.tsx`
- `backend/analyzers/implementations/{metadata,clip_detector,llm_image,ela}_analyzer.py`
- `backend/content/tasks.py`
- `backend/provenance/models.py`
- `backend/templates/content/report.html`

README clean already.

## Going forward

Apply to all new text. Watch out for autocomplete inserting them in chat replies, commit messages, UI copy, docstrings.

## See also

- Memory entry: `/Users/sevastyan0107/.claude/projects/-Users-sevastyan0107-PycharmProjects-prooflayer/memory/feedback_no_em_dash.md`
