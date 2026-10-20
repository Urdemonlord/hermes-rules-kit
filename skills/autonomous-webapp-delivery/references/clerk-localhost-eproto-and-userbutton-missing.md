# Clerk localhost EPROTO + UserButton missing (AgentWA)

## Symptom cluster
- Authenticated API calls return `500`.
- Response header shows `x-middleware-rewrite: https://localhost:20128/api/...`.
- Server log shows `Failed to proxy https://localhost:20128/...` + `EPROTO ... packet length too long`.
- Dashboard profile bubble/logout (`UserButton`) disappears intermittently.

## Confirm quickly
1. Probe API with session cookie and inspect headers:
   - if rewrite points to `https://localhost:<app-port>`, this is the bug.
2. Check app logs for `EPROTO` on same timestamp.
3. Fetch rendered dashboard HTML and inspect Clerk script source.

## Root cause found in this incident
- Clerk proxy config drift forced frontend API/script path via app domain, while internal app upstream runs plain HTTP on localhost.
- This caused HTTPS self-proxy attempts to local HTTP port.
- Same misconfig also broke/emptied Clerk UI mount points (UserButton container rendered empty).

## Working fix sequence
1. Remove incorrect Clerk proxy env on app runtime:
   - `CLERK_PROXY_URL`
   - `NEXT_PUBLIC_CLERK_PROXY_URL`
2. Keep `ClerkProvider` with `signInUrl`/`signUpUrl` only (no forced empty proxyUrl hack).
3. Rebuild + restart service.
4. Verify Clerk script source resolves to Clerk domain (`https://clerk.<domain>/npm/@clerk/clerk-js...`), not app domain.
5. Re-test:
   - signed-out API should be `401` JSON,
   - signed-in should no longer emit `x-middleware-rewrite: https://localhost...` nor EPROTO.

## UI handling lesson
- During auth/runtime incident response, avoid changing dashboard account UX (manual logout button rewrite) unless user explicitly asks.
- First restore Clerk runtime integrity; only then evaluate UI component behavior.

## Evidence patterns to capture in handoff
- `x-middleware-rewrite` header value.
- exact `journalctl` EPROTO lines with timestamp.
- Clerk script URL from `/dashboard` HTML.
- post-fix HTTP status shape (`401` unauth vs `500`).
