---
type: frontend
created: 2026-10-16
source: frontend/src/index.css, frontend/src/components/{SearchingOrb,TaskSteps,UploadProgress,AnalyzerTimeline,OriginalityPanel}.tsx, frontend/src/pages/{LandingPage,PricingPage,UploadPage,FactCheckPage}.tsx
---

# UI motion and card style

Effects are built in-house with `motion` and CSS (no paid 21st.dev code). Every CSS animation obeys the
global `prefers-reduced-motion` rule in `index.css`; `SearchingOrb` draws one still frame instead.

## Effects

| effect | where | how |
|---|---|---|
| Word blur-in | landing hero h1 | `wordBlur` variants in `LandingPage.tsx`, each word `motion.span` from `blur(14px)`, stagger 0.09 s; the gradient "or by AI" fades in as one span so `background-clip: text` survives |
| Text scanner | "or by AI" in the hero | `.scan-text` `::after` bar (skewed -12deg like the italic) + `::before` trailing band, 6.5 s cycle after a 1.6 s delay |
| Border beam | "Popular" pricing card | `.beam-border::before`, conic gradient on `@property --beam-angle`, masked to the 1 px border, 5 s per turn |
| Image scan | upload progress, image or video | `UploadProgress` `previewUrl`/`previewKind` (object URL made in `UploadPage`, revoked on change); `.scan-grid` + `.scan-line` overlay bound to the image box, cyan corners, "Analyzing image" pill |
| Live analyzer checklist | upload progress | `TaskSteps` fed by `buildSteps(submission)` from `AnalyzerTimeline` (real `expected_analyzers` + `analysis_results`); pending ring, spinner, drawn check (`.check-draw`), time per analyzer, `done/total`; replaces the old canned "worker log" tips when steps exist |
| Shimmer text | "Analyzing", "checking sources…", active fact-check stage, running analyzer | `.shimmer-text` uses `-webkit-text-fill-color: transparent` so `currentColor` keeps the element's own colour |
| Searching orb | originality "checking sources…" pill, fact-check "searching" stage | `SearchingOrb` canvas: dotted sphere (9 latitude rings), tilted 0.38 rad, spinning, a bright spot sweeping left-right through the centre; modelled on 21st.dev "thinking orbs / searching" frame by frame |

## Card style (2026-10-16 cleanup)

- `.case-card` lost its amber gradient top line and amber hover glow; hover only lightens the border.
- `.badge` is a tinted pill (`color-mix(currentColor 12%)`), no outline.
- Analyzer timeline markers are small verdict-coloured dots on the vertical thread (no boxes or
  circles with icons); running is a thin spinner, pending a hollow dot. The `#01 · CODE /` slash is gone.
- Upload progress: no frame around the preview, file-type tile is a soft fill, no pulsing halo on the
  active stage or header dot.
- Originality header aligns `items-center` while the check runs (canvas baseline would lift the pill)
  and `items-baseline` once the big percentage shows.

## Gotchas

- A Vite proxy to `prooflayer.cloud/api` returns the SPA HTML (the API lives on `api.prooflayer.cloud`);
  Chrome then caches that HTML for the API URL by `last-modified` heuristics, so a fixed proxy still
  shows empty pricing until the entry is refetched with `cache: "reload"`.
- `background-clip: text` breaks on children with their own transform or filter, so blur the gradient
  span as a whole, never per word.
