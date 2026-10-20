# Midtrans Sandbox → Production Migration

Step-by-step checklist for migrating a SvelteKit storefront from Midtrans sandbox to production.

## 1. Credential rotation

Replace all sandbox keys (`SB-Mid-...`) with production keys (`Mid-...`):

| Variable | Sandbox Example | Production |
|----------|----------------|------------|
| `MIDTRANS_MERCHANT_ID` | `G406109951` | `M283228709` |
| `PUBLIC_MIDTRANS_CLIENT_KEY` | `SB-Mid-client-...` | `Mid-client-...` |
| `MIDTRANS_SERVER_KEY` | `SB-Mid-server-...` | `Mid-server-...` |
| `MIDTRANS_IS_PRODUCTION` | `false` | `true` |

The code in `midtrans.ts` already switches the base URL based on this flag:
- Sandbox: `https://app.sandbox.midtrans.com`
- Production: `https://app.midtrans.com`

## 2. CSP header cleanup

CSP headers in `hooks.server.ts` hardcode sandbox URLs. Replace with a dynamic derivation from `SNAP_JS_URL`:

```typescript
import { SNAP_JS_URL } from '$lib/server/midtrans'

const snapJsDomain = new URL(SNAP_JS_URL).origin  // production → https://app.midtrans.com
const snapApiDomain = snapJsDomain.replace('app.', 'api.')

// Use in CSP:
// script-src: ${snapJsDomain}
// connect-src: ${snapJsDomain} ${snapApiDomain}
// frame-src: ${snapJsDomain}
```

Remove all hardcoded `app.sandbox.midtrans.com` / `api.sandbox.midtrans.com` references from CSP.

## 3. Remove Snap.js hardcoded sandbox fallback

The order page had:

```javascript
script.src = data.snapJsUrl || 'https://app.sandbox.midtrans.com/snap/snap.js';
```

Change to:

```javascript
script.src = data.snapJsUrl;
```

The server always passes the correct Snap.js URL via `SNAP_JS_URL`, so no fallback is needed.

## 4. Sandbox simulator UI

The order page has a sandbox simulator section gated by `data.isSandbox` which is derived from `SNAP_JS_URL.includes('sandbox')`. In production, this automatically returns `false` — so the simulator section never renders. No code change needed; the gate is already correct.

## 5. Domain whitelist — NOT needed for Snap

Midtrans Snap does NOT require domain whitelist. The Client Key is safe to expose on any domain — it only initiates payment sessions. Security comes from the Server Key (backend only).

The domain whitelist/credential exchange process described in https://docs.midtrans.com/reference/getting-started-1 is for **BI-SNAP Core API** (a different product), not for standard Snap integration.

## 6. Docker compose env pass-through

Ensure `compose.yaml` has all Midtrans env vars:

```yaml
- MIDTRANS_SERVER_KEY=${MIDTRANS_SERVER_KEY}
- MIDTRANS_IS_PRODUCTION=${MIDTRANS_IS_PRODUCTION:-false}
- PUBLIC_MIDTRANS_CLIENT_KEY=${PUBLIC_MIDTRANS_CLIENT_KEY}
- MIDTRANS_MERCHANT_ID=${MIDTRANS_MERCHANT_ID}
```

After updating `.env`, force-recreate the container so it picks up new values:

```bash
cd project && docker compose up -d --force-recreate
```

## 7. Verification checklist

```bash
# 1. Keys in container (masked)
docker inspect <container> --format '{{json .Config.Env}}' | python3 -c "
import sys,json
for e in json.load(sys.stdin):
    if 'MIDTRANS' in e:
        print(e.split('=')[0], '=', e.split('=')[1][:8]+'...')
"

# 2. CSP header (should NOT contain 'sandbox')
curl -sI https://client-site.meowlabs.id | grep sandbox
# Expected: NO MATCH

# 3. App health
curl -s -o /dev/null -w "%{http_code}" https://client-site.meowlabs.id
# Expected: 200
```

## 8. Webhook URL

The Midtrans webhook URL (`/api/midtrans/webhook`) does NOT change between sandbox and production. Update the webhook URL in Midtrans dashboard if it was pointing to a sandbox-specific endpoint.

## 9. Webhook Test Notification Pitfall — Return 200, Not 403

Midtrans dashboard has a **"Tes URL notifikasi"** (Test Notification URL) button. This tool sends a real POST with proper signature to your webhook. **If the webhook returns a non-200 status (including 403 for invalid signature), Midtrans reports "Tes gagal — Gagal mengirim notifikasi HTTP karena terdapat kendala pada URL."** This error message means Midtrans received a non-200 response, NOT that the URL is unreachable.

**The fix:** The webhook handler must return 200 even when signature verification fails, especially for test/dummy notifications:

```typescript
// In /api/midtrans/webhook/+server.ts — signature verification section
const valid = verifySignature(orderId, statusCode, grossAmount, SERVER_KEY, signatureKey)
if (!valid) {
  console.error('[midtrans-webhook] Invalid signature:', {
    orderId, statusCode, grossAmount,
    signatureKey: signatureKey?.slice(0, 20) + '...',
    txStatus, paymentType
  })
  // Return 200 so Midtrans test tool doesn't report URL failure.
  return json({ status: 'ignored', reason: 'invalid_signature' })
}
```

**Do NOT `throw error(403, 'Invalid signature')`** — this causes the Midtrans dashboard test to fail, even though the webhook is working correctly. The 403 was correct in principle (reject invalid signatures), but it breaks the dashboard test tool which only checks for 200 OK.

### Verification after fix

```bash
# Should return 200 (not 403/502)
curl -s -o /dev/null -w "%{http_code}" -X POST \
  "https://domain.com/api/midtrans/webhook" \
  -H "Content-Type: application/json" \
  -d '{"order_id":"test","status_code":"200","gross_amount":"10000","signature_key":"test","transaction_status":"settlement"}'
# Expected: 200

# GET should still return 405 (method not allowed)
curl -s -o /dev/null -w "%{http_code}" "https://domain.com/api/midtrans/webhook"
# Expected: 405
```

**502 errors during testing:** If you get 502 from the public URL but 200 from localhost, the container may have been restarting during the first test. Wait 5 seconds and retry. Nginx proxies to the Docker port — if the container isn't ready yet, Nginx returns 502.
