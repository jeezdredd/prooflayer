---
type: frontend
created: 2026-05-14
---

# Frontend Routes

`App.tsx` -> `<BrowserRouter>` -> `<Routes>`.

## Public

| Path | Component | Notes |
|------|-----------|-------|
| `/` | `LandingPage` | Hero + **Tribunal** section (`#tribunal`) + CTAs. Auth-aware (CTA flips to "Open Dashboard" when logged in). |
| `/login` | `LoginPage` | Email + password. JWT pair returned. |
| `/register` | `RegisterPage` | Email + username + password + confirm. |

## Authenticated (inside `<ProtectedRoute>` + `<Layout>`)

| Path | Component | Notes |
|------|-----------|-------|
| `/upload` | `UploadPage` | Drop file -> see [[concepts/submission-pipeline]] |
| `/dashboard` | `DashboardPage` | Case registry table + filters + pagination |
| `/factcheck` | `FactCheckPage` | Paste text -> spaCy NER + LLM -> Google Fact Check Tools lookup per claim |
| `/community-fakes` | `CommunityFakesPage` | Shared known-fake list |
| `/compare` | `ComparePage` | Pick two submissions -> side-by-side scores + analyzer breakdown |
| `/embed` | `EmbedPage` | Generate `<script>` widget snippet with SHA-256, live preview |
| `/review` | `ReviewQueuePage` | Staff only (`user.is_staff`). Override `needs_review` / `inconclusive` submissions |
| `/status` | `StatusPage` | Live service health probes -> [[api/system-status]] |
| `/results/:id` | `ResultPage` | Per-submission view: verdict + analyzer timeline + evidence + similar submissions + community votes |

## Landing: the Tribunal section

Rewritten 2026-09-04 (was "The Pipeline"), compacted 2026-09-15. Presents [[concepts/tribunal]]
as the product's own detection system: a four-tile "how it decides" grid and the nine seeded
checks, each row just icon + name + a 3-5 word tag. Long descriptions are hidden behind a tap
(`AnimatePresence` height reveal, one open at a time per group). Every icon carries a slow idle
loop (`IDLE`, 2.4 s, staggered) so the section moves without being noisy. The section label reads the live `services.analyzers.ensemble`
string from `/system/status/` (`useQuery`, 5-minute stale time, no retry) and falls back to
`TRIBUNAL_FALLBACK` when the API is unreachable, so the version on the landing page cannot drift
from the backend. The old list advertised NPR and SigLIP, which are no longer seeded, and listed
C2PA under "more to come" although it ships inside the metadata check.

## Fallback

`*` -> `<Navigate to="/" replace />`.

## Auth flow

`ProtectedRoute` checks `useAuthStore().isAuthenticated`. Redirects to `/login` if not. Sync init from `localStorage` prevents flash. See [[frontend/auth-flow]].

## Nav

Sidebar shows 7 numbered items (01-07: Verify, Dashboard, Fact Check, Community, Compare, Embed, Status). Staff sees additional item 08: Review. Logo links to `/`. Landing escape link separate. See [[frontend/sidebar-layout]].

## See also

- [[frontend/sidebar-layout]]
- [[frontend/auth-flow]]
- [[services/frontend]]
