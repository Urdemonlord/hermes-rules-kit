# SvelteKit Midtrans Production Cutover Checklist

Full workflow when switching from Midtrans sandbox (`SB-Mid-*`) to production keys.

## Pre-flight

- [ ] Merchant ID, Client Key, Server Key ready (production — no `SB-` prefix)
- [ ] Production plan active on Midtrans dashboard

## Step 1: Update credentials

```bash
cd /project && umask 077 && sed -i \
  -e 's/^MIDTRANS_SERVER_KEY=.*/MIDTRANS_SERVER_KEY=Mid-server-xxx/' \
  -e 's/^MIDTRANS_IS_PRODUCTION=.*/MIDTRANS_IS_PRODUCTION=true/' \
  -e 's/^PUBLIC_MIDTRANS_CLIENT_KEY=.*/PUBLIC_MIDTRANS_CLIENT_KEY=Mid-client-xxx/' \
  -e 's/^MIDTRANS_MERCHANT_ID=.*/MIDTRANS_MERCHANT_ID=Mxxx/' \
  .env
```

## Step 2: CSP must switch dynamically

**Before** (hardcoded both):
```ts
"script-src 'self' ... https://app.sandbox.midtrans.com https://app.midtrans.com"
"connect-src 'self' https://app.sandbox.midtrans.com https://api.sandbox.midtrans.com https://app.midtrans.com https://api.midtrans.com ..."
"frame-src 'self' ... https://app.sandbox.midtrans.com https://app.midtrans.com"
```

**After** (dynamic from `SNAP_JS_URL`):
```ts
import { SNAP_JS_URL } from '$lib/server/midtrans'

// In handle hook:
const snapJsDomain = SNAP_JS_URL ? new URL(SNAP_JS_URL).origin : 'https://app.midtrans.com'
const snapApiDomain = snapJsDomain.replace('app.', 'api.')
// Use ${snapJsDomain} and ${snapApiDomain} in CSP strings
```

## Step 3: Remove hardcoded sandbox fallbacks

```svelte
<!-- Before: -->
script.src = data.snapJsUrl || 'https://app.sandbox.midtrans.com/snap/snap.js';

<!-- After: -->
script.src = data.snapJsUrl;  // always set from server
```

## Step 4: Verify isSandbox flag

The `order/[id]/+page.server.ts` uses:
```ts
isSandbox: SNAP_JS_URL.includes('sandbox')
```

With production keys, this becomes `false` automatically. The sandbox simulator section in the page component is gated by `{#if data.isSandbox && ...}` — no code change needed, just verify it's hidden.

## Step 5: Container recreate (mandatory)

```bash
# Check for shell env overrides FIRST
echo "${MIDTRANS_SERVER_KEY:-(not set)}"

# Recreate
docker compose up -d --force-recreate

# Verify with masked fingerprints
docker inspect <container> --format '{{json .Config.Env}}' | python3 -c "
import sys, json
envs = json.load(sys.stdin)
for e in envs:
    if 'MIDTRANS' in e.upper():
        parts = e.split('=', 1)
        val = parts[1] if len(parts) > 1 else ''
        masked = val[:8] + '...' + val[-4:] if len(val) > 12 else val
        print(f'{parts[0]}={masked}')
"
```

## Step 6: Verify CSP header

```bash
curl -sI https://domain/ | grep content-security-policy
# Must NOT contain 'sandbox'
```

## Common pitfalls

- **Shell env overrides .env** — Docker Compose resolves `${VAR}` from shell first. If any Midtrans key is exported in `~/.bashrc`, it overrides `.env`.
- **CSP still blocks production** — If CSP still has sandbox URLs but no production URLs, Snap.js will be blocked by the browser.
- **Domain whitelist is NOT needed** — Regular Midtrans Snap does not require domain whitelisting. Only BI-SNAP Core API (different product) has that requirement.
- **Sandbox simulator still shows** — The `isSandbox` flag is derived from `SNAP_JS_URL`. If it's somehow still `true`, check `MIDTRANS_IS_PRODUCTION` in the container.
- **Old orders still show sandbox UI** — That's expected. `isSandbox` is computed per-request, not per-order. If the flag is `false`, sandbox content won't render for any order.
