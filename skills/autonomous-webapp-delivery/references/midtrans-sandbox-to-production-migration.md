# Midtrans Sandbox → Production Migration Checklist

## Credential update
1. Get production keys from Midtrans MAP dashboard (not SB- prefixed)
2. Update `.env`:
   ```
   MIDTRANS_SERVER_KEY=Mid-server-...
   MIDTRANS_IS_PRODUCTION=true
   PUBLIC_MIDTRANS_CLIENT_KEY=Mid-client-...
   MIDTRANS_MERCHANT_ID=M...
   ```

## Code changes

### 1. CSP headers (hooks.server.ts)
Make CSP dynamic based on `SNAP_JS_URL` instead of hardcoding both sandbox and production URLs:
```ts
import { SNAP_JS_URL } from '$lib/server/midtrans'
const snapJsDomain = new URL(SNAP_JS_URL).origin   // https://app.midtrans.com
const snapApiDomain = snapJsDomain.replace('app.', 'api.')  // https://api.midtrans.com
// Use in script-src, connect-src, frame-src directives
```

### 2. Remove hardcoded sandbox fallbacks
In `+page.svelte`, remove fallback to sandbox Snap.js URL:
```ts
// BEFORE (bad):
script.src = data.snapJsUrl || 'https://app.sandbox.midtrans.com/snap/snap.js'
// AFTER (good):
script.src = data.snapJsUrl  // always set by server, production URL
```

### 3. Sandbox simulator section
The sandbox simulator section is gated by `data.isSandbox` which is derived from `SNAP_JS_URL.includes('sandbox')`. In production this is automatically `false` — no action needed, but verify.

### 4. verifySignature still needed
Webhook signature verification works identically in production. Keep it.

## Verification
```bash
# CSP header should NOT contain "sandbox"
curl -sI https://domain.com | grep -i content-security-policy | grep -o sandbox

# Should return nothing (no sandbox in CSP)

# App healthy
curl -s -o /dev/null -w "%{http_code}" https://domain.com/
# Should return 200
```

## Note on domain whitelist
Midtrans Snap does NOT require domain whitelisting. Client Key is frontend-safe. Just set the keys and deploy.
