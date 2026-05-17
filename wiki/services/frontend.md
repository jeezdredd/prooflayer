---
type: service
created: 2026-05-14
---

# Frontend (Vite + React)

React 18 + Vite 6 + Tailwind 3 + TypeScript 5. Port 5173.

## Container

```yaml
frontend:
  build: frontend/Dockerfile
  command: pnpm dev --host 0.0.0.0
  ports: ["5173:5173"]
  volumes:
    - ./frontend:/app
    - /app/node_modules    # anon volume preserves container pnpm install
```

Package manager: `pnpm` (via corepack). Frozen lockfile install with `pnpm install --frozen-lockfile || pnpm install`.

## Key deps

- `react` 18.3.1
- `react-router-dom` 7.1.0
- `motion` 12.38 (formerly framer-motion)
- `@tanstack/react-query` 5.62
- `zustand` 5.0
- `axios` 1.7
- `@paper-design/shaders-react` 0.0.76 -> [[frontend/shader-bg]]
- `lucide-react` (icon library)
- `clsx`

Dev: Tailwind 3.4, TypeScript 5.6, Vite 6, autoprefixer, postcss, @vitejs/plugin-react, eslint.

## Layout

`frontend/src/components/Layout.tsx` - sidebar nav (240px left rail) + `<main>` area + mobile drawer. See [[frontend/sidebar-layout]].

## Routes

See [[frontend/routes]].

## State stores

- `stores/authStore.ts` - user + tokens. Sync init from localStorage. -> [[frontend/auth-flow]]
- `stores/uploadStore.ts` - status / progress / submissionId / reset
- `stores/shaderStore.ts` - `boostToken` counter; bump triggers MeshGradient speed surge

## Hooks

- `hooks/useAuth.ts` - useRegister, useLogin (tanstack mutations)
- `hooks/useUpload.ts` - useUploadFile (mutation w/ progress callback), useSubmissionDetail (polling query)
- `hooks/useDashboard.ts` - paginated list query

## API client

`api/client.ts` - axios instance, base URL from `VITE_API_URL` (default `/api/v1`). JWT interceptor reads `localStorage.tokens.access`.

`api/endpoints.ts` - typed wrappers:

```ts
auth.login, auth.register, auth.me, auth.refresh
content.list, content.detail, content.upload, content.override
analyzers.list
crowdsource.vote
factcheck.run
system.status
```

## UI primitives

`components/ui/`:
- `Toast.tsx` + `ToastContainer` - top-right notifications
- `ShaderBackground.tsx` - background mesh ([[frontend/shader-bg]])
- `Skeleton.tsx`
- `Spinner.tsx`

## See also

- [[frontend/routes]]
- [[frontend/auth-flow]]
- [[frontend/shader-bg]]
- [[frontend/sidebar-layout]]
