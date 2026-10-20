# Next.js 16 + Clerk + PM2 Deployment on Cloudflare-proxied VPS

## Key Learnings from AgentWA Production Debug

### Architecture
```
Client → Cloudflare (orange cloud, SSL termination) → nginx → PM2 (Next.js 16 standalone) → Clerk middleware (proxy.ts)
```

### The "Invalid Host header" Error — Root Cause

The error `"Invalid Host header. Bridge accepts loopback hosts only."` has **two distinct sources** that look identical but require different fixes:

#### Source 1: Orphaned processes fighting for the same port (THIS SESSION)
```
ps aux | grep next-server  # Found multiple orphaned next-server processes
ss -tlnp | grep 3000       # Port 3000 bound by multiple PIDs
```
**Fix:** Kill ALL orphaned next-server processes, restart clean:
```bash
pkill -f "next-server" 2>/dev/null || true
sleep 2
pm2 delete agentwa-web 2>/dev/null; pm2 flush agentwa-web
ss -tlnp | grep 3000 || echo "Port FREE"
pm2 start ecosystem.config.js
```

#### Source 2: Clerk middleware + Next.js `-H` hostname flag misconfiguration
If you pass `-H domain.com` to `next start`, Next.js 16 tries to **bind to that hostname's resolved IP**, not `0.0.0.0`. On a Cloudflare-proxied VPS, this resolves to Cloudflare's public IPs, causing `EADDRNOTAVAIL` because those IPs aren't local interfaces.

**Fix:** DO NOT use `-H` flag with `next start` for reverse-proxy setups. Next.js should bind to `0.0.0.0` (default), and nginx handles Host header routing.

```js
// ecosystem.config.js — CORRECT
module.exports = {
  apps: [{
    name: 'agentwa-web',
    script: 'node_modules/.bin/next',
    args: 'start -p 3000',  // NO -H flag
    cwd: '/home/user/agentwa/web',
    instances: 1,
    exec_mode: 'fork',       // Use fork, not cluster, for single-port apps
    autorestart: true,
    env: {
      NODE_ENV: 'production',
      PORT: '3000'
    }
  }]
};
```

### Next.js 16 Middleware → Proxy Convention

Next.js 16 deprecated `src/middleware.ts` in favor of `src/proxy.ts`. Clerk's `clerkMiddleware` works in both but the framework emits a warning:
```
⚠ The "middleware" file convention is deprecated. Please use "proxy" instead.
```

**Rename pattern:**
```bash
mv src/middleware.ts src/proxy.ts
```

The Clerk middleware pattern remains the same:
```typescript
// src/proxy.ts
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

### Clerk Auth in Header — useAuth Hook Pattern

For Clerk v7+ with Next.js App Router, use `useAuth` hook instead of `SignedIn`/`SignedOut` components (avoids import path conflicts between `@clerk/nextjs` and `@clerk/clerk-react`):

```typescript
// components/site-header.tsx
"use client";
import { UserButton, SignInButton, useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";

export function SiteHeader() {
  const { isSignedIn } = useAuth();
  // Render Login or Dashboard+UserButton based on auth state
}
```

### Zero-Downtime Deploy Script Pattern

See `scripts/zero-downtime-deploy.sh` in the same directory as this reference.

**The pattern:**
1. Build (without starting server)
2. Start new instance on alternate port (3001)
3. Hot-swap nginx proxy_pass to new port
4. Reload nginx
5. Stop old instance
6. Rename new to current

### PM2 Process Management — Fork vs Cluster

- **fork mode**: Single instance, binds directly to port 3000. Use for apps behind nginx reverse proxy.
- **cluster mode**: Multiple instances, each gets own port. Use when app handles its own load balancing.

For a Next.js app behind nginx: **always use `exec_mode: 'fork'`**.

### nginx Proxy Configuration for Next.js + Clerk

```nginx
server {
    server_name agentwa.meowlabs.id;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Clerk's auth redirect URLs need proper Host header
    location /sign-in/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }

    listen 443 ssl;
    ssl_certificate ...;
}
```

### Verification Sequence After Deploy

```bash
# 1. Check PM2 status
pm2 status

# 2. Check port binding
ss -tlnp | grep 3000

# 3. Verify no orphaned next-server processes
ps aux | grep next-server | grep -v grep

# 4. Test via public domain
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" https://agentwa.meowlabs.id/dashboard

# 5. Check for Login button in HTML
curl -s https://agentwa.meowlabs.id/ | grep -o 'Login\|Dashboard' | sort | uniq -c
```

### Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `EADDRNOTAVAIL` on startup | `-H` flag with Cloudflare-proxied domain | Remove `-H` flag, bind to `0.0.0.0` |
| `Invalid Host header` persists after nginx change | Orphaned next-server still running on port | `pkill -f next-server`, restart PM2 |
| "Bridge accepts loopback" on public domain | Cloudflare IPs conflicting with loopback-only binding | Remove `-H`, ensure nginx sends `Host: agentwa.meowlabs.id` |
| PM2 app keeps restarting with SIGINT | Cluster mode trying to bind multiple instances to same port | Change to `exec_mode: 'fork'` |
| Old code still served after rebuild | Multiple next-server processes, nginx round-robins to old one | Kill all orphans, single fresh start |
