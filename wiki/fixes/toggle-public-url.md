---
type: fix
date: 2026-06-18
---

# Fix: toggle-public 404

## Symptom

Toggling submission visibility (private -> public) returned 404.

## Root cause

Frontend called `/content/submissions/{id}/toggle_public/` (underscore). Django DRF router registered it as `toggle-public` (hyphen) via `url_path="toggle-public"` on the `@action`.

## Fix

`frontend/src/api/endpoints.ts`:

```ts
// before
client.post(`/content/submissions/${id}/toggle_public/`, {})
// after
client.post(`/content/submissions/${id}/toggle-public/`, {})
```

## Rule

DRF `@action(url_path=...)` values use hyphens by convention. Frontend must match exactly.
