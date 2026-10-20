# Next.js 16 + Clerk middleware rewrite trap (localhost EPROTO)

## Symptom signature
- Public routes/API return 500 with header:
  - `x-middleware-rewrite: https://localhost:<app_port>/...`
- App logs show:
  - `Failed to proxy https://localhost:<app_port> ... EPROTO ... packet length too long`
- Often appears after hardening app bind to `127.0.0.1` behind Nginx/Cloudflare.

## Root cause patterns
1. **Clerk middleware not matching route using `auth()`/`currentUser()`**
   - Error: `auth() was called but Clerk can't detect usage of clerkMiddleware()`
   - Any API route calling auth helpers without matching middleware can blow up to 500.
2. **Over-broad or misconfigured Clerk middleware causing rewrite loop to `https://localhost:<port>`**
   - Next runtime attempts TLS to local HTTP app port -> EPROTO.
3. **Absolute `CLERK_SIGN_IN_URL`/`CLERK_SIGN_UP_URL` with custom middleware redirects** can amplify wrong-origin rewrites.

## Proven recovery sequence
1. Ensure middleware file location is valid for src layout:
   - `src/middleware.ts` (not repo root middleware when app expects src placement).
2. Start from minimal safe middleware (API-focused) to kill rewrite loops:
   - Match only API first: `matcher: ['/api/(.*)']`
   - Return JSON 401 for unauthenticated API requests.
3. Keep app page auth guard in page/client logic temporarily while stabilizing middleware.
4. Normalize Clerk URLs to relative paths in env:
   - `CLERK_SIGN_IN_URL=/sign-in`
   - `CLERK_SIGN_UP_URL=/sign-up`
   - avoid localhost/proxy URL vars unless explicitly required.
5. Rebuild + restart + verify matrix:
   - `/` must be `200`
   - `/api/agents` unauth -> `401` JSON (not 500)
   - `/api/persona-presets` unauth -> `401` JSON (not 500)
   - headers must **not** show `x-middleware-rewrite: https://localhost:<port>/...`

## Verification commands
```bash
npm run build
systemctl --user restart agentwa-web.service
curl -I https://<domain>/
curl -i https://<domain>/api/agents
curl -i https://<domain>/api/persona-presets
journalctl --user -u agentwa-web.service -n 120 --no-pager
```

## Guardrails
- Treat `401 unauthorized` on unauth API as healthy auth boundary, not outage.
- When user reports "internal server error", always compare public headers + app logs in same time window before patching.
- Do not assume `curl 200` on one route proves middleware/auth health for all routes.
