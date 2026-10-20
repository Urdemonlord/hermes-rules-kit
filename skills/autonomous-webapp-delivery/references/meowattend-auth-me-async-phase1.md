# MeowAttend auth/me async migration (Phase 1)

## Context
Edge-case debt: protected routes (notably `attendance`) could crash or render error when session expired because route/shell code touched `me.role` before robust auth check, while `me()` performed sync XHR to `/api/v1/me`.

## Durable pattern
1. Keep `me()` cache-only and side-effect free for sync reads.
2. Add `meAsync({ force })` for server validation:
   - call `/api/v1/me` via `fetch`
   - if `401/403`: clear token + clear cached auth, return `unauthenticated=true`
   - if network/server error: return non-auth failure without crashing UI
3. In route/shell bootstrap for protected routes:
   - show lightweight loading state (`Memuat sesi...`)
   - `await meAsync({ force: true })`
   - if no user result -> redirect `#login` and render public login safely
4. Null safety rule: never read `me.role`/`me.name` before successful auth bootstrap.

## Minimal acceptance checks
- Expired session on protected route -> redirects to `#login`, no runtime crash.
- Non-auth routes still render without auth bootstrap.
- `401/403` path removes stale token/auth cache.
- Cache-bust version bumped and served HTML points to new `app.js/api.js` marker.

## Implementation notes
- This phase can be low-risk by limiting async migration to `auth/me` only.
- Keep other APIs unchanged initially; migrate gradually after route auth stability is confirmed.
