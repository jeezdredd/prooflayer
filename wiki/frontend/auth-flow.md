---
type: frontend
created: 2026-05-14
source: frontend/src/stores/authStore.ts
---

# Auth Flow (JWT)

JWT-based, stored in localStorage. Synchronous hydration prevents flash.

## Store

`stores/authStore.ts` (zustand):

```ts
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser(user): void;       // persists user to localStorage
  setTokens(access, refresh): void;  // persists tokens
  logout(): void;            // clears storage
  hydrate(): void;           // re-reads from storage
}
```

Init via `loadFromStorage()` IIFE inside `create((set) => ({ ...loadFromStorage(), ... }))` - **synchronous on first render**. Both `tokens` AND `user` must be present in localStorage to set `isAuthenticated: true`.

## Login

`useLogin()` (tanstack mutation):

```ts
POST /api/v1/auth/login/ { email, password }
-> { access, refresh, user }
-> setTokens(access, refresh); setUser(user)
-> navigate("/upload")
```

## Register

`useRegister()`:

```ts
POST /api/v1/auth/register/ { email, username, password, password_confirm }
-> { access, refresh, user }
-> setTokens + setUser
-> navigate("/upload")
```

## Refresh

`api/client.ts` axios interceptor on 401:

```ts
if (response.status === 401 && !retry) {
  POST /api/v1/auth/refresh/ { refresh }
  -> { access }
  -> setTokens(access, refresh)
  -> retry original request
}
```

If refresh fails -> logout + redirect to /login.

## Logout

`authStore.logout()` clears localStorage + sets `user=null`. Layout's logout button calls this + navigates to /login.

## ProtectedRoute

```tsx
function ProtectedRoute() {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated);
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
```

## Landing auth-aware CTA

`LandingPage` reads `useAuthStore(s => s.user)` and conditionally renders:
- Header: `Sign in` link OR `agent: email` label
- Hero CTA: `Begin Investigation -> /register` OR `Open Dashboard -> /upload`
- All bottom CTAs swap target similarly

## See also

- [[models/User]]
- [[frontend/routes]]
