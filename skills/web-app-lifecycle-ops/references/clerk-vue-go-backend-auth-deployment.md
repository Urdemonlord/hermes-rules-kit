# Clerk OAuth + Go Backend Auth Deployment

**When to use:** Deploying a SPA frontend (Vue/React/Vite) that uses Clerk for OAuth sign-in and a custom Go backend that exchanges Clerk session tokens for local app JWTs.

## Architecture

```
Browser ── HTTPS ──> Nginx ── / ──────────────> /var/www/app (static SPA)
                        │                       
                        └── /v1/* ──────────────> 127.0.0.1:18081 (Go backend)
                            /healthz
```

- Frontend: Vue SPA built with Vite, Clerk JS SDK for Google sign-in
- Backend: Go HTTP server with `clerk-sdk-go` for token verification
- Auth flow: Clerk sign-in → Clerk session token → POST to backend exchange endpoint → local JWT

## Auth Flow

1. User clicks "Sign in with Google" on Clerk UI
2. Clerk handles OAuth, creates Clerk session
3. Frontend bootstrap detects existing Clerk session → calls `ensureLocalSession()`
4. `ensureLocalSession()` calls `POST /v1/auth/clerk/exchange` with Clerk session token
5. Backend verifies token with Clerk SDK, creates/finds local user, returns local JWT
6. Frontend stores JWT, routes to dashboard

## Files to Set Up

### Frontend (`frontend/`)
```
src/lib/clerk.ts       — Clerk singleton + ensureLocalSession()
src/main.ts            — Bootstrap with Clerk init + session redirect
src/views/AuthView.vue  — Clerk SignIn component mount
router.ts              — Route guard for protected routes
```

### Backend (`internal/`)
```
internal/auth/clerk_verifier.go   — Clerk SDK wrapper: VerifyToken + GetUser
internal/auth/service.go           — ExchangeClerkToken() implementation
internal/http/router.go            — POST /v1/auth/clerk/exchange route
internal/config/config.go           — CLERK_SECRET_KEY env var
```

## Env Vars

```env
# Backend
CLERK_SECRET_KEY=sk_live_xxxxx              # From Clerk dashboard — MUST be live key for prod
CLERK_AUTHORIZED_PARTIES=https://app.com    # Production URL(s) for token audience

# Frontend build-time
VITE_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx   # From Clerk dashboard — MUST be live key for prod
```

## Deployment Steps

1. **Build frontend:**
   ```bash
   VITE_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx npm run build
   ```
   The key is baked into the JS bundle at build time. For production, you must build with the live key.

2. **Deploy static:**
   ```bash
   sudo cp -a frontend/dist/. /var/www/app/
   sudo chown -R root:root /var/www/app
   sudo find /var/www/app -type d -exec chmod 755 {} +
   sudo find /var/www/app -type f -exec chmod 644 {} +
   ```

3. **Set backend env** — Add `CLERK_SECRET_KEY` and `CLERK_AUTHORIZED_PARTIES` to the backend's env file.

4. **Build Docker image:**
   ```dockerfile
   FROM golang:1.24-alpine AS builder
   # ... standard build ...
   COPY --from=builder /bin/onedock /usr/local/bin/onedock
   ```

5. **Run backend container with host network (if that's the active topology):**
   ```bash
   docker run -d --name api --network host --restart unless-stopped \
     --env-file .env.production backend-image
   ```

6. **Verify:**
   ```bash
   # Health check
   curl -s http://127.0.0.1:18081/healthz

   # Exchange endpoint responds (expect 401 with dummy token)
   curl -s -X POST http://127.0.0.1:18081/v1/auth/clerk/exchange \
     -H 'Content-Type: application/json' \
     --data '{"token":"dummy"}' | grep -q 'invalid_clerk_session' && echo "Clerk active"

   # Prod public site
   curl -s https://app.com/auth | grep -q 'Continue with Google' && echo "Auth page live"
   ```

## Pitfalls

### 1. Clerk UI bundle must be loaded manually
`@clerk/clerk-js` does **not** auto-bundle the sign-in UI component. You must mount it explicitly:
```ts
await clerk.load()
const el = document.getElementById('clerk-sign-in')
if (el) clerk.mountSignIn(el, { oauthFlow: 'redirect', redirectUrl: '/auth' })
```
Without mounting, the AuthView will render blank with no sign-in buttons.

### 2. Bootstrap redirect timing
The Clerk session exchange must happen before or at app boot, not after the landing page has mounted. Pattern:
```ts
// main.ts
const restored = await ensureLocalSession()  // Clerk init + exchange
const app = createApp(App).use(router)
app.mount('#app')
if (restored && location.pathname === '/') await router.replace('/dashboard')
```
If `ensureLocalSession()` runs after mount, the landing page renders before the redirect fires — user sees a flash of landing page then redirects to dashboard.

### 3. `CLERK_AUTHORIZED_PARTIES` must match the production domain
Clerk JWTs include an `azp` (authorized party) claim. The backend verifier checks this against `CLERK_AUTHORIZED_PARTIES`. If the deployed domain doesn't match, `VerifyToken()` returns an error. Set this to the **exact production URL** (`https://app.com`), not `localhost` or an empty list.

### 4. DNS resolution fails with `--network host`
When the backend container uses `--network host`, Docker compose service names (`postgres`, `redis`) are **not resolvable** because the container uses the host's DNS, not Docker's embedded DNS.

```
lookup onedock-postgres-1 on 203.0.113.10:53: server misbehaving
```

**Fix:** Change DATABASE_URL and REDIS_URL to use `127.0.0.1` instead of compose service names, because postgres/redis expose their ports on the host:
```env
DATABASE_URL=postgres://user:pass@127.0.0.1:5432/db
REDIS_URL=redis://127.0.0.1:6379/0
```

### 5. Prod vs test Clerk keys
The publishable key (`pk_...`) is compiled into the frontend JS at build time. The secret key (`sk_...`) is loaded by the backend at runtime. If either is a test key, production auth will fail or show "Development mode" badges. Build + deploy with live keys for production.

If a key is exposed in chat, **rotate it immediately** in the Clerk dashboard — the old key will stop working within minutes. After rotating, update both the `.env.production` and rebuild the frontend.

## Verification checklist

- [ ] `https://app.com/auth` shows "Continue with Google" with no "Development mode" badge
- [ ] Google sign-in redirect opens Google consent page with correct tenant
- [ ] `POST /v1/auth/clerk/exchange` with dummy token returns 401 `invalid_clerk_session` (not 503 `clerk_not_configured`)
- [ ] After real sign-in completes, user reaches dashboard (not stuck on landing page)
- [ ] Backend logs show no panic or nil-pointer errors on exchange
