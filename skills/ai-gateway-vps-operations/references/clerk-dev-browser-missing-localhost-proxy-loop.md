# Clerk `dev-browser-missing` after localhost-only hardening (Next.js)

## Symptom
- App listens correctly on `127.0.0.1:<port>` after security hardening.
- `curl http://127.0.0.1:<port>/sign-in` hangs, then returns `500`.
- Response headers include:
  - `x-clerk-auth-reason: dev-browser-missing`
  - `x-middleware-rewrite: http://localhost:<port>/sign-in`
- Logs may show `Failed to proxy http://localhost:<port>/sign-in` + `ECONNRESET`.

## Interpretation
- This is usually **Clerk dev/test mode behavior**, not a bind/listen failure.
- Local curl from server is not equivalent to real browser flow through public domain.

## Fast triage sequence
1. Verify socket bind first:
   - `ss -tulpen | egrep ':(port)\\b'`
2. Verify process health separately:
   - systemd/pm2 status
3. Test public route via Nginx/domain (browser or `curl -I https://domain/sign-in`) instead of localhost-only curl.
4. Check Clerk key type:
   - `pk_test`/`sk_test` => dev behavior possible
   - prefer `pk_live`/`sk_live` for production domain
5. Ensure Clerk URLs are explicit in env:
   - `CLERK_SIGN_IN_URL=https://<domain>/sign-in`
   - `CLERK_SIGN_UP_URL=https://<domain>/sign-up`
   - `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`
   - `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`

## Guardrail
- Do not conclude "service down" from localhost sign-in curl alone when Clerk middleware is active.
- Treat this as an auth/runtime-mode issue unless socket binding or process health also fails.
