---
type: model
created: 2026-05-14
source: backend/users/
---

# User (custom)

Custom Django auth user. Email-based login.

## Settings

`AUTH_USER_MODEL = "users.User"` in `config/settings/base.py`.

## Likely fields (standard layout)

- `email` (USERNAME_FIELD)
- `username`
- `password` (hashed)
- `is_staff` (gates [[frontend/routes|/review queue]] nav item)
- `is_active`
- `date_joined`

## Endpoints

`/api/v1/auth/` from `users.urls`:

- `POST /register` -> create User, return JWT pair
- `POST /login` -> JWT pair (access + refresh)
- `POST /refresh` -> rotate access via refresh
- `GET /me` -> current user
- `POST /logout` (optional)
- `GET /health` -> public ping

JWT via `djangorestframework-simplejwt`. Tokens stored in localStorage by frontend `authStore`.

## Frontend store

`frontend/src/stores/authStore.ts` (zustand):

```ts
{
  user: User | null,
  isAuthenticated: boolean,
  setUser, setTokens, logout, hydrate
}
```

Synchronous init from `localStorage.tokens` + `localStorage.user`. See [[frontend/auth-flow]].
