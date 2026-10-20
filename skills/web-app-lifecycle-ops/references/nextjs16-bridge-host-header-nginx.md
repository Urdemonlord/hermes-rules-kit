# Next.js 16 Bridge: Invalid Host Header Behind Nginx

## Problem

Next.js 16 production server (internal "Bridge") rejects requests where `Host` header is not a loopback address (`localhost`, `127.0.0.1`, `[::1]`).

```
{"error":"Invalid Host header. Bridge accepts loopback hosts only."}
```

nginx forwards `Host: $host` (the real domain) → Bridge rejects with 400.

## Root cause

Next.js 16 added a security layer in its production server that validates the `Host` header. It only accepts loopback hosts. This is independent of `next.config.js` `server.hostname` or `--hostname` flags — those only control the listen interface.

## Fix

### Layer 1 — nginx (critical)

In the `location /` block, replace `proxy_set_header Host $host` with `localhost:3000` and forward the original domain via `X-Forwarded-Host`:

```nginx
location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_http_version 1.1;
    proxy_set_header Host "localhost:3000";       # ← Next.js 16 requires loopback Host
    proxy_set_header X-Forwarded-Host $host;       # ← original domain for app logic
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # WebSocket headers if needed
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Layer 2 — next.config.js

```js
const nextConfig = {
  server: {
    hostname: '0.0.0.0',
    port: 3000,
  },
  // ... rest
};
module.exports = nextConfig;
```

### Layer 3 — PM2 start (belt-and-suspenders)

```bash
pm2 start "node_modules/.bin/next start --hostname 0.0.0.0 --port 3000" --name app --cwd /path/to/app
```

## Verification

- `curl -k https://domain.com/` returns HTML (even 404) instead of JSON error = fix working
- `curl -H "Host: domain.com" http://localhost:3000/` will still fail locally (it bypasses nginx) — that's expected

## Why not

- `--hostname 0.0.0.0` alone isn't enough — Bridge host-check is separate from listen address
- `NEXT_PRIVATE_HOSTNAME=0.0.0.0` doesn't affect Bridge validation
- Upgrading Next.js won't change this — it's an intentional security feature

## Affected versions

- Next.js 16.x (confirmed on 16.2.6)
- May also affect 15.x with stricter config — verify if needed
