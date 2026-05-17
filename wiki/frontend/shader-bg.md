---
type: frontend
created: 2026-05-14
source: frontend/src/components/ui/ShaderBackground.tsx
---

# Shader Background

Animated mesh-gradient background using `@paper-design/shaders-react` `MeshGradient` component. Sits fixed `inset-0 z-0`, content z-10+.

## Variants

| Variant | Palette | Use |
|---------|---------|-----|
| `noir` | `["#000","#1a1a1a","#3a3a3a","#f0f0f0"]` | App pages, Landing |
| `paper` | cream/tan/umber/dark | Subtle light-mode (legacy) |
| `amber` | warm cream -> dark amber -> black | Decorative |
| `dawn` | dark -> tan -> cream | RegisterPage |

Speed `settle` value 0.35-0.4 per variant.

## Kickoff animation (page mount)

```ts
const KICKOFF_SPEED = 4.0;
const KICKOFF_DURATION = 3.2;  // seconds

speedMV = useMotionValue(KICKOFF_SPEED);
animate(speedMV, cfg.settle, {
  duration: KICKOFF_DURATION,
  ease: [0.16, 1, 0.3, 1]   // expo-out
});
```

Pattern: mesh blobs whip fast on mount, decelerate to ambient settle speed. Cubic ease-out curve.

## Upload boost trigger

`stores/shaderStore.ts`:

```ts
{ boostToken: number, triggerBoost: () => set(s => ({ boostToken: s.boostToken + 1 })) }
```

`UploadPage.handleFileSelect` calls `triggerBoost()`. ShaderBackground subscribes to `boostToken`:

```ts
useEffect(() => {
  if (boostToken === 0) return;
  speedMV.set(BOOST_SPEED);   // 5.5
  animate(speedMV, cfg.settle, { duration: 2.8, ease: [0.16, 1, 0.3, 1] });
}, [boostToken]);
```

Visual: user drops file -> blobs surge -> decelerate over 2.8s back to ambient. UX cue that something happened.

## Vignette layer

Radial gradient overlay on dark variants softens edges:

```css
radial-gradient(ellipse 90% 70% at 50% 50%, transparent 0%, rgba(0,0,0,0.65) 90%)
```

Plus a top-bottom linear gradient veil for content-area readability.

## Stacking

- Body bg: `transparent` (CSS)
- html bg: `var(--ink-950)` fallback
- ShaderBackground container: `fixed inset-0`, `zIndex: 0`, `pointer-events: none`
- Content (`<main>`, `<header>`, `<footer>`): `relative z-10`

## Performance

- `MeshGradient` runs in WebGL via @paper-design/shaders-react
- `paper` variant adds `blur(30px)` filter + scale 1.15 for softer look
- All shader is decorative; respects `prefers-reduced-motion` via CSS reset

## See also

- [[services/frontend]]
- [[frontend/sidebar-layout]]
