# Clerk middleware-free API auth and route prefix corruption recovery

## Context
Next.js App Router API routes behind proxy/rewrite where `clerkMiddleware()` was intentionally not used on API request path.

## Symptom set
- Runtime errors: `auth() was called but Clerk can't detect usage of clerkMiddleware()`
- API endpoints (persona/rag/usage/observability) returning 400/500 intermittently.
- Build errors: Turbopack `Import is not allowed here` on route files.

## Root causes
1. Auth helper allowed fallback path without request context (e.g., `requireAuthUser(req?)` calling `auth()` when `req` missing).
2. Ownership helper retained legacy signature (e.g., `requireOwnedAgent(agentId)`), so some callsites never passed `req`.
3. Route files accidentally polluted with line-number prefixes (`1|`, `12|`) from pasted output.

## Proven fix pattern
1. Make auth helper request-only:
   - `requireAuthUser(req: Request)` (required param)
   - Remove fallback `auth()`/`currentUser()` branch in API path.
2. Update ownership helper contract:
   - `requireOwnedAgent(req: Request, agentId: string)`
   - Refactor all callsites.
3. Validate no legacy usage remains:
   - search for `await auth(`, `currentUser(` in `src/lib`
   - search for `requireOwnedAgent(agentId)` old call form.
4. If Turbopack import parse errors appear, mass-clean route files:
   - remove repeated `^\s*\d+\|\s*` prefixes.
5. Re-verify deployment path:
   - `npm run build`
   - restart service manager
   - check `is-active` + fresh logs.

## Verification evidence checklist
- Build completes successfully (warnings acceptable if non-blocking).
- Service state active after restart.
- Route manifest includes affected API endpoints.
- Re-test previously failing dashboard/API calls after hard refresh.

## Pitfalls
- Fixing helper signatures without updating all route callsites leaves hidden failures.
- Assuming build parser error is TypeScript logic issue can waste time; first inspect for text corruption markers (`N|`).
