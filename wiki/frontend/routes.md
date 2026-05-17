---
type: frontend
created: 2026-05-14
---

# Frontend Routes

`App.tsx` -> `<BrowserRouter>` -> `<Routes>`.

## Public

| Path | Component | Notes |
|------|-----------|-------|
| `/` | `LandingPage` | Hero + analyzer overview + CTAs. Auth-aware (CTA flips to "Open Dashboard" when logged in). |
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
