# Next.js 16 + PM2 + Nginx — VPS Deployment Reference

Production-validated patterns from AgentWA deployment on a constrained VPS.

---

## Working `ecosystem.config.js`

```javascript
module.exports = {
  apps: [{
    name: 'agentwa-web',
    script: 'node_modules/.bin/next',
    args: 'start -p 3000',
    cwd: '/home/user/agentwa/web',
    instances: 1,
    exec_mode: 'fork',        // NOT 'cluster' — Next.js handles its own concurrency
    autorestart: true,
    watch: false,
    env: {
      NODE_ENV: 'production',
      PORT: '3000'
    }
  }]
};
```

Key points:
- `exec_mode: 'fork'` (not `cluster') — Next.js's built-in server handles concurrency
- No `-H hostname` flag — causes Next.js to try binding to Cloudflare/public IPs and fail with `EADDRNOTAVAIL`
- `NODE_ENV=production` — required, Clerk middleware behaves differently in dev mode
- `PORT=3000` — Next.js listens on localhost only; nginx proxies from outside

---

## Zero-Downtime Deploy Script

```bash
#!/bin/bash
# Zero-downtime deploy — nginx ALWAYS points to port 3000
# The old deploy script used nginx port-swap which PERSISTED after deploy
# and redirected traffic to wrong apps (e.g. the auth service on 3001)
# Fix: nginx config is NEVER modified; port handoff handled entirely within PM2

set -e

APP_DIR="/home/user/agentwa/web"
NEXT_PORT=3001

echo "🚀 Starting zero-downtime deploy..."

# Step 1: Build
cd "$APP_DIR"
npm run build

# Step 2: Start new instance on NEXT_PORT
pm2 stop app-new 2>/dev/null || true
PORT=$NEXT_PORT NODE_ENV=production pm2 start ecosystem.config.js \
  --name app-new -- node_modules/.bin/next start -p $NEXT_PORT

# Step 3: Wait for new server
echo "⏳ Waiting for new server on port $NEXT_PORT..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:$NEXT_PORT/ > /dev/null 2>&1; then
    echo "✅ New server ready on port $NEXT_PORT"
    break
  fi
  sleep 1
done

# Step 4: STOP OLD INSTANCE — nginx still proxying to 127.0.0.1:3000
pm2 stop app 2>/dev/null || true
pm2 delete app 2>/dev/null || true

# Step 5: Start fresh instance on 3000 (nginx still pointing there)
pm2 start ecosystem.config.js --env production

# Step 6: Cleanup
pm2 delete app-new 2>/dev/null || true

echo "✅ Zero-downtime deploy complete!"
```

### CRITICAL: Never modify nginx config in deploy scripts

**What broke AgentWA**: The original script used `sed` to swap nginx's `proxy_pass` from port 3000 to 3001.
This PERSISTED after the deploy — when the auth service also ran on port 3001 on the same VPS,
nginx permanently redirected AgentWA traffic to the auth service until manually fixed.

**The safe pattern**: nginx `proxy_pass` stays permanently on `127.0.0.1:3000`.
Deploy script handles the port handoff entirely within PM2:
1. Start new build on 3001
2. Stop old instance on 3000 → port 3000 becomes free
3. Start fresh instance on 3000 → nginx immediately serves new build
4. Delete temporary 3001 instance

**If nginx was already corrupted** (pointing to wrong port):
```bash
# Emergency fix
sudo sed -i 's|proxy_pass http://127.0.0.1:3001|proxy_pass http://127.0.0.1:3000|' \
  /etc/nginx/sites-enabled/YOUR_DOMAIN.conf
sudo nginx -t && sudo nginx -s reload
```

---

## Orphaned Process Cleanup (Critical)

Before any PM2 restart, kill all orphaned `next-server` processes or they fight for the port:

```bash
# Kill all orphaned next-server processes
pkill -f "next-server" 2>/dev/null || true

# Verify port is free
ss -tlnp | grep 3000 || echo "Port 3000 is FREE"

# Only then start fresh
pm2 delete agentwa-web 2>/dev/null || true
pm2 start ecosystem.config.js
```

**Why**: Multiple `next-server` processes accumulate when PM2 restart fails mid-cycle. They all try to bind port 3000. Only one wins — the rest silently fail, and curl gets responses from whichever one started first (often the OLD build).

**Verification after restart**:
```bash
ss -tlnp | grep 3000
# Should show exactly ONE process listening on 127.0.0.1:3000
```

---

## Next.js 16 `allowedHosts` — What Changed

Next.js 16 deprecated `allowedHosts` in `next.config.js`. The warning:
```
⚠ Invalid next.config.js options detected:
⚠     Unrecognized key(s) in object: 'allowedHosts'
```

**What NOT to do**:
- Don't put `allowedHosts: ['domain.com']` in `next.config.js` — TypeScript accepts it but Next.js ignores it
- Don't use `-H domain.com` in PM2 `args` — Next.js tries to **bind to that hostname as an IP**, causing `EADDRNOTAVAIL` on public IPs

**What works**: Run Next.js on `127.0.0.1:3000` with no host flags. Nginx handles the Host header translation. Clerk middleware sees the original Host from nginx's `proxy_set_header Host $host`.

---

## Next.js 16 Middleware: `proxy.ts` not `middleware.ts`

Next.js 16 shows:
```
⚠ middleware (middleware.ts) is deprecated. Use proxy (proxy.ts) instead.
```

Rename:
```bash
mv src/middleware.ts src/proxy.ts
```

Clerk middleware works in `proxy.ts`:
```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isProtectedRoute = createRouteMatcher(['/dashboard(.*)', '/api/billing(.*)']);

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
};
```

---

## Clerk Auth — `useAuth` Hook (Not SignedIn/SignedOut)

For conditional rendering in client components, use the `useAuth` hook:

```typescript
// site-header.tsx
"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";

export function SiteHeader() {
  const { isSignedIn } = useAuth();

  return (
    <header>
      {isSignedIn ? (
        <>
          <Link href="/dashboard">Dashboard</Link>
          <UserButton />
        </>
      ) : (
        <Link href="/sign-in">Login</Link>
      )}
    </header>
  );
}
```

**Why not `SignedIn`/`SignedOut` components**: In `@clerk/nextjs` v7.x, these require `@clerk/clerk-react` peer dep and may conflict with the Next.js App Router server components. The `useAuth()` hook is the stable, version-agnostic approach.

---

## Healthcheck After Deploy

Always verify the deployed app, not just PM2 status:

```bash
# Test the actual HTTP response
curl -s https://your-domain.com/ | grep -o 'expected-content' | head -1

# Or check HTTP status
curl -s -o /dev/null -w "%{http_code}" https://your-domain.com/
# Should return 200, not 400/502/307

# Verify protected routes redirect properly
curl -s -o /dev/null -w "%{http_code}" https://your-domain.com/dashboard
# Should return 307 redirecting to /sign-in
```

---

## Common Failure Modes

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid Host header` from curl | Two causes: (1) Clerk Bridge — `curl` bypasses nginx, PM2 shows app running fine; (2) Orphaned Express/Node process holding port — PM2 shows errored/stopped, `curl http://127.0.0.1:3000/` returns wrong app or error JSON | For (1): ensure `NODE_ENV=production` in PM2. For (2): `fuser -k 3000/tcp` to kill orphaned process, then `pm2 delete` + `pm2 start` |
| `Cannot GET /` but 200 OK | Wrong app listening on port (orphaned next-server from old build) | `pkill -f next-server` then verify port |
| `EADDRINUSE` on port | Orphaned process still holding port after failed PM2 restart | `fuser -k PORT/tcp` + `pm2 delete` + `pm2 start` |
| PM2 restart loads stale build | PM2 restart does not re-read ecosystem config or do fresh `next start` | Use `pm2 delete` + `pm2 start` always after config changes |
