# Clerk live recovery after localhost-only hardening (Next.js)

## Trigger
- Domain returns `HTTP 500` after binding Next.js/Node services to `127.0.0.1`.
- Response headers show Clerk/middleware hints like:
  - `x-clerk-auth-reason: dev-browser-missing` or `session-token-and-uat-missing`
  - `x-middleware-rewrite: https://localhost:<port>/...`

## Proven recovery sequence
1. Keep localhost-only bind (do **not** reopen public app ports).
2. Ensure production Clerk env is present in app runtime:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...`
   - `CLERK_SECRET_KEY=sk_live_...`
   - `CLERK_SIGN_IN_URL=https://<public-domain>/sign-in`
   - `CLERK_SIGN_UP_URL=https://<public-domain>/sign-up`
   - `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`
   - `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`
   - `CLERK_PROXY_URL=https://<public-domain>`
   - `NEXT_PUBLIC_CLERK_PROXY_URL=https://<public-domain>`
3. Scope middleware matcher to protected surfaces only (e.g. `/dashboard(.*)`, protected API groups) so public/sign-in routes are not rewritten through localhost proxy logic.
4. Build + restart app service.
5. Verify with explicit probes:
   - `curl -I https://<public-domain>` -> expect `200`
   - `curl -i https://<public-domain>/sign-in` -> expect `200`
   - Confirm no `x-middleware-rewrite: https://localhost:...` on these public routes.

## Pitfalls
- Treating localhost curl timeout right after restart as permanent failure; retry after worker bind completes.
- Fixating only on keys; matcher scope can still force bad rewrites even with correct live keys.
- Reopening public app ports as a workaround; this weakens security and is unnecessary.

## Security note
If live keys were pasted in chat/logs, rotate and redeploy immediately; confirm using masked fingerprints only.