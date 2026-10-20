# SvelteKit Docker Deployment Pitfalls

## CSRF: ORIGIN Mismatch Across Reverse Proxy Chain

**Symptom**: All form POST submissions return 403 "Cross-site POST form submissions are forbidden" when accessed via public domain, but work fine via localhost.

**Root cause**: SvelteKit's CSRF check compares the request `Origin` header against the configured `ORIGIN` env var. When running behind nginx/Cloudflare + Docker port mapping, the `ORIGIN` env var is often set to `http://127.0.0.1:PORT` but the actual request `Origin` is `https://public-domain.com`. Mismatch = CSRF block.

**Fix**: In `compose.yaml`, set `ORIGIN` to the public URL:
```yaml
environment:
  - ORIGIN=https://actual-domain.com
```

**Verification**: `curl -X POST https://domain.com/form -H "Origin: https://domain.com" -H "Content-Type: application/x-www-form-urlencoded" -d "..."` should return 200/302, not 403.

## $env/static/public vs $env/dynamic/public in Docker

**Symptom**: Build fails with `[MISSING_EXPORT] "env" is not exported by "\0virtual:env/static/public"`.

**Root cause**: `$env/static/public` variables are inlined at **build time**. In Docker, the `.env` file is on the host and compose injects env vars at **runtime**. The Docker build step has no access to these vars.

**Fix**: Use `$env/dynamic/public` instead:
```svelte
<script lang="ts">
  import { env } from '$env/dynamic/public';
  // env.PUBLIC_MY_VAR is read at runtime from process.env
</script>
```

**Note**: For `$env/static/private`, the pattern is different — private vars are only used server-side and can still work with compose runtime injection. The issue is specific to `static/public` which gets embedded in the client bundle.

## Svelte 5 $state SSR Initialization

**Symptom**: Component renders correctly in browser but shows wrong/empty state in SSR HTML (curl/get request). Conditional UI blocks (buttons, sections) that depend on `$state` are missing from initial HTML.

**Root cause**: `$state` initialized to `null`/`undefined` only gets updated when `$effect` runs — but `$effect` only runs in the browser, never during SSR.

**Fix**: Initialize `$state` from the `data` prop directly:
```svelte
<script lang="ts">
  let { data } = $props();
  // WRONG — SSR renders with null:
  let snapToken = $state<string | null>(null);
  // RIGHT — SSR renders with actual value:
  let snapToken = $state<string | null>(data.snapToken || null);
</script>
```

## CSP Blocking Midtrans Snap.js / Iframe

**Symptom**: Snap.js popup never appears — order page shows "Menunggu Pembayaran" with no popup. Browser console shows CSP errors like "Refused to load the script" or "Refused to frame".

**Root cause**: SvelteKit projects with CSP headers in `hooks.server.ts` block external scripts/frames from `app.sandbox.midtrans.com` (Snap.js CDN) and `api.sandbox.midtrans.com` (Snap API). The default CSP typically only allows `'self'` + known services like Google Fonts.

**Fix**: Add Midtrans URLs to all three CSP directives:

```typescript
// src/hooks.server.ts
response.headers.set('Content-Security-Policy', [
  "default-src 'self'",
  // Allow Snap.js script
  "script-src 'self' 'unsafe-inline' https://app.sandbox.midtrans.com https://app.midtrans.com",
  // Allow Snap API calls
  "connect-src 'self' https://app.sandbox.midtrans.com https://api.sandbox.midtrans.com https://app.midtrans.com https://api.midtrans.com",
  // Allow Snap payment iframe
  "frame-src 'self' https://app.sandbox.midtrans.com https://app.midtrans.com",
].join('; '))
```

**Verification**: 
```bash
curl -sI https://domain.com | grep content-security-policy | grep -o "midtrans"
# Should output: midtrans (shows it's in the CSP)
```

Also check browser DevTools Console — no CSP violation messages about midtrans.com.

**Server-side (checkout action)**:
1. Create Snap transaction via `POST /snap/v1/transactions` with server key
2. Store `snap.token` in DB as `paymentRef` on the order
3. Redirect to order page (token passed via DB, not URL)

**Server-side (order page load)**:
1. Read `paymentRef` from order if `paymentMethod === 'midtrans_snap'`
2. Return as `snapToken` in page data

**Client-side (order page component)**:
1. Initialize `snapToken` local state from `data.snapToken` (for SSR)
2. `$effect` auto-loads Snap.js and calls `window.snap.pay(token, callbacks)`
3. Fallback manual button: `<button onclick={payWithSnap}>Bayar dengan Midtrans</button>`
4. On close/error, set `snapToken = null` to hide button until manual re-trigger

**Critical**: Use `https://app.sandbox.midtrans.com/snap/snap.js` for SB- keys, `https://app.midtrans.com/snap/snap.js` for production.

**Client key**: Must be accessible client-side. Use `PUBLIC_MIDTRANS_CLIENT_KEY` with `$env/dynamic/public`.

**Compose env vars needed**:
```yaml
- MIDTRANS_SERVER_KEY=${MIDTRANS_SERVER_KEY}
- MIDTRANS_IS_PRODUCTION=${MIDTRANS_IS_PRODUCTION:-false}
- PUBLIC_MIDTRANS_CLIENT_KEY=${PUBLIC_MIDTRANS_CLIENT_KEY}
- MIDTRANS_MERCHANT_ID=${MIDTRANS_MERCHANT_ID}
```

## .env → compose.yaml Pass-Through Gap

**Symptom**: Env vars are set in `.env` but `process.env.MY_VAR` is empty/undefined inside the container. The app can't read them even though they exist on the host.

**Root cause**: Docker Compose only passes env vars that are explicitly declared in `compose.yaml`'s `environment:` block. Adding a new variable to `.env` without a corresponding `- VAR_NAME=${VAR_NAME}` line in compose means the container never sees it.

**Detection**:
```bash
# Check what the container actually sees
docker exec <container> node -e "console.log(process.env.MY_VAR || 'NOT SET')"
docker exec <container> env | grep MY_VAR

# Compare against host .env
head .env
```

**Fix**: For every new env var added to `.env`, add a matching line in `compose.yaml`:
```yaml
environment:
  - NEW_VAR=${NEW_VAR}
  - NEW_VAR_WITH_DEFAULT=${NEW_VAR_WITH_DEFAULT:-fallback}
```

**Restart required**: After updating `compose.yaml`, run `docker compose up -d` to recreate the container. A running container carries its own snapshot of env vars from creation time — it won't pick up new compose declarations automatically.

## Payment Flow Debugging: SQLite + Docker Exec Pattern

When a SvelteKit e-commerce app shows payment integration failures with no clear error logs, trace the data layer directly:

### 1. Query the SQLite DB for patterns

```bash
# Mount path usually at /var/lib/docker/volumes/<project>_<volume>_data
sudo sqlite3 /var/lib/docker/volumes/.../dev.db \
  "SELECT paymentMethod, paymentRef, paymentStatus, datetime(createdAt) FROM 'Order' ORDER BY createdAt DESC LIMIT 20;"

# Count empty vs filled paymentRef
sudo sqlite3 .../dev.db \
  "SELECT CASE WHEN paymentRef IS NULL OR paymentRef = '' THEN 'empty' ELSE 'filled' END, COUNT(*) FROM 'Order' WHERE paymentMethod = 'midtrans_snap' GROUP BY 1;"
```

**What to look for**: Orders with `paymentMethod = 'midtrans_snap'` but empty `paymentRef` — means Midtrans API call failed and fallback also failed to save. A high empty rate (>20%) signals integration issues, not user behavior.

### 2. Test payment APIs from within the container

```bash
# Test Midtrans Snap API
docker exec <container> node -e "
const key = process.env.MIDTRANS_SERVER_KEY;
const base = process.env.MIDTRANS_IS_PRODUCTION === 'true' ? 'https://app.midtrans.com' : 'https://app.sandbox.midtrans.com';
const auth = 'Basic ' + Buffer.from(key + ':').toString('base64');
fetch(base + '/snap/v1/transactions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: auth },
  body: JSON.stringify({
    transaction_details: { order_id: 'test-' + Date.now(), gross_amount: 10000 },
    customer_details: { first_name: 'Test', phone: '08123456789' }
  })
}).then(r => r.json()).then(d => console.log(d.token ? 'OK' : 'FAIL: ' + d.status_message));
"

# Test Komerce API
docker exec <container> node -e "
fetch('https://api-sandbox.collaborator.komerce.id/user/api/v1/user/payment/create', {
  method: 'POST',
  headers: { 'x-api-key': process.env.KOMMERCE_PAYMENT_KEY, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    order_id: 'test-' + Date.now(), payment_type: 'bank_transfer',
    channel_code: 'BCA', amount: 10000,
    customer: { name: 'Test', email: 'user@example.com', phone: '08123456789' },
    items: [{ name: 'Test', price: 10000, quantity: 1 }]
  })
}).then(r => r.json()).then(d => console.log(d.meta?.code === 200 ? 'OK' : 'FAIL: ' + JSON.stringify(d.meta)));
"
```

### 3. Verify SvelteKit env var propagation in built code

SvelteKit `$env/dynamic/private` variables go through a prefix filter. The built output reveals the actual rules:

```bash
grep -rn 'env_private_prefix\|env_public_prefix' build/server/chunks/internal2.js
# Shows: env_public_prefix: 'PUBLIC_', env_private_prefix: ''
```

The `filter_env(env, allowed, disallowed)` function selects vars where key starts with `allowed` AND does NOT start with `disallowed`. With `allowed=''` and `disallowed='PUBLIC_'`, private env gets ALL vars except PUBLIC_ ones.

**Key check**: If a private env var is missing at runtime, verify it's not accidentally prefixed with `PUBLIC_`.

### 4. Midtrans Snap Popup vs Redirect

**Popup approach (legacy, unreliable)**: Store snap token → redirect to own order page → `onMount` loads Snap.js and calls `window.snap.pay(token)`. 

**Failure modes**:
- Browser popup blockers may block auto-open from `onMount` (not a user gesture)
- Snap.js CDN unreachable or slow → `window.snap` undefined
- `$state` initialized from prop correctly for SSR, but `onMount`/`$effect` timing may miss the token
- ~47% failure rate observed in production (empty `paymentRef` → no token → no popup)

**Redirect approach (RECOMMENDED)**: After `createTransaction()`, redirect directly to `snap.redirectUrl` (Midtrans payment page). After payment, Midtrans redirects back to a return URL. This eliminates all popup-reliability issues and matches user expectation of being "directed to Midtrans."

**Implementation**:

1. Add `finishCallbackUrl` to `createTransaction()` and pass it in the Snap API request:
```ts
// src/lib/server/midtrans.ts
export interface CreateTransactionParams {
  // ... existing fields
  finishCallbackUrl?: string  // URL Midtrans redirects to after payment
}

// In the request body:
if (params.finishCallbackUrl) {
  body.callbacks = { finish: params.finishCallbackUrl }
}
```

2. In checkout action, redirect to `snap.redirectUrl` instead of order page:
```ts
// src/routes/checkout/+page.server.ts
const origin = url.origin
const finishUrl = `${origin}/order/${orderId}?from=midtrans`

const snap = await createTransaction({
  orderId, amount: total,
  items: ...,
  customer: ...,
  finishCallbackUrl: finishUrl  // Midtrans returns here after payment
})

await prisma.order.update({
  where: { id: orderId },
  data: { paymentRef: snap.token, paymentMethod: 'midtrans_snap', paymentStatus: 'pending' }
})

// Redirect to Midtrans, not to own order page
throw redirect(302, snap.redirectUrl)
```

3. Order page handles the return from Midtrans:
```ts
// src/routes/order/[id]/+page.server.ts
const fromMidtrans = url.searchParams.has('from')
// ... pass fromMidtrans to page data
```

4. Remove auto-popup from `onMount`; keep manual "Bayar dengan Midtrans" button as fallback:
```svelte
<!-- src/routes/order/[id]/+page.svelte -->
{#if data.fromMidtrans}
  <p class="text-sm text-stone">Kembali dari halaman pembayaran. Status akan diperbarui otomatis.</p>
{/if}

{#if snapToken}
  <!-- Manual button — user gesture, no popup blocker -->
  <button onclick={async () => { await loadSnapJs(); payWithSnap(snapToken!); }}>
    Bayar dengan Midtrans
  </button>
{/if}
```

5. Keep polling for status updates (webhook may arrive before or after redirect-back):
```ts
// Poll every 10s for 5 minutes (30 polls max)
onMount(() => {
  let pollCount = 0;
  if (order.paymentStatus === 'pending') {
    const interval = setInterval(async () => {
      pollCount++;
      if (pollCount > 30) { clearInterval(interval); return; }
      const res = await fetch(`/api/order/${order.id}/status`);
      if (res.ok) {
        const d = await res.json();
        if (d.paymentStatus !== 'pending') {
          order.paymentStatus = d.paymentStatus;
          clearInterval(interval);
        }
      }
    }, 10000);
    return () => clearInterval(interval);
  }
});
```

**Trade-off**: Popup keeps user on-site for the full flow; redirect takes them off-site then back. For reliability, prefer redirect.

**Verification**: 
```bash
curl -s -b cookies.txt 'http://localhost:3301/checkout' \
  -H 'Origin: https://client-site.meowlabs.id' \
  -d 'name=Test&phone=08123...&address=...&city=...&province=...&zip=50123' \
  | python3 -m json.tool
# Should show: {"type":"redirect","status":302,"location":"https://app.sandbox.midtrans.com/snap/v4/redirection/..."}
```

### 5. SvelteKit `use:enhance` + `applyAction` redirect handling

```svelte
<form method="POST" use:enhance={() => {
    loading = true;
    return async ({ result, update }) => {
        loading = false;
        await applyAction(result);
    };
}}>
```

When the server `throw redirect(302, '/order/xxx')`, SvelteKit sends `{type:'redirect', status:302, location:'/order/xxx'}`. `applyAction(result)` handles this by navigating the browser. If the redirect doesn't happen, check:
- That `result.type === 'redirect'` is being received (log in the callback)
- That no JS error in the callback swallows the result silently
- That `loading = false` runs before `applyAction` which triggers navigation

### 6. DB Update Retry for SQLite Locking

SQLite under concurrent load can fail `prisma.order.update()` with locking errors. When the update is critical (e.g., saving a payment token), retry with backoff:

```ts
let dbOk = false
for (let attempt = 0; attempt < 3; attempt++) {
    try {
        await prisma.order.update({
            where: { id: orderId },
            data: {
                paymentRef: snap.token,
                paymentMethod: 'midtrans_snap',
                paymentStatus: 'pending'
            }
        })
        dbOk = true
        break
    } catch (dbErr: any) {
        if (attempt === 2) {
            console.error('[checkout] DB update failed after 3 retries:', dbErr?.message || dbErr)
        } else {
            await new Promise(r => setTimeout(r, 300))
        }
    }
}
if (!dbOk) {
    console.error('[checkout] Could not save snap token for order', orderId)
}
```

**When to use**: Any time the token/ref MUST be saved for the payment flow to work. If the token exists on Midtrans's side but not in your DB, the user can't retry from the order page.

### 7. Dynamic Snap.js URL from Server (Not Hardcoded)

**Problem**: Hardcoding `'https://app.sandbox.midtrans.com/snap/snap.js'` in the Svelte component means production always loads the sandbox script. When `MIDTRANS_IS_PRODUCTION=true`, the snap token is created against production Midtrans but the JS loads from sandbox CDN — mismatch causes failure.

**Fix**: Pass `SNAP_JS_URL` from server to client via page data:

```ts
// src/routes/order/[id]/+page.server.ts
import { SNAP_JS_URL } from '$lib/server/midtrans'

export const load: PageServerLoad = async ({ params, locals, url }) => {
    // ... existing order loading
    return {
        order: { ...order, total: order.total },
        snapToken,
        snapJsUrl: SNAP_JS_URL,  // dynamic: sandbox or production URL
        // ... other fields
    }
}
```

```svelte
<!-- src/routes/order/[id]/+page.svelte -->
<script>
    // Use data.snapJsUrl instead of hardcoded URL
    function loadSnapJs(): Promise<void> {
        return new Promise((resolve) => {
            if (snapLoaded) { resolve(); return; }
            const script = document.createElement('script');
            script.src = data.snapJsUrl || 'https://app.sandbox.midtrans.com/snap/snap.js';
            script.setAttribute('data-client-key', env.PUBLIC_MIDTRANS_CLIENT_KEY || '');
            script.onload = () => { snapLoaded = true; resolve(); };
            script.onerror = () => resolve();
            document.body.appendChild(script);
        });
    }
</script>
```

**Verification**:
```bash
curl -s "http://localhost:3301/order/<id>" | grep -oP 'snapJsUrl:"[^"]*"'
# Shows: snapJsUrl:"https://app.sandbox.midtrans.com/snap/snap.js"
# (or production URL depending on MIDTRANS_IS_PRODUCTION)
```

### 8. Midtrans Sandbox Testing — Simulator URLs

Midtrans sandbox does NOT accept real payments. All testing uses web-based simulators:

| Metode | Simulator URL |
|--------|--------------|
| GoPay | `simulator.sandbox.midtrans.com/gopay/ui/index` |
| QRIS | `simulator.sandbox.midtrans.com/qris/index` |
| ShopeePay (deeplink) | `simulator.sandbox.midtrans.com/v2/deeplink/index` |
| BCA VA | `simulator.sandbox.midtrans.com/bca/va/index` |
| BNI VA | `simulator.sandbox.midtrans.com/bni/va/index` |
| Permata VA | `simulator.sandbox.midtrans.com/openapi/va/index` (pilih Permata) |
| BRI VA | `simulator.sandbox.midtrans.com/openapi/va/index` (pilih BRI) |
| Mandiri Bill | `simulator.sandbox.midtrans.com/mandiri/bill/index` |
| Indomaret | `simulator.sandbox.midtrans.com/indomaret/index` |
| Alfamart | `simulator.sandbox.midtrans.com/alfamart/index` |

**Test credit cards** (CVV: `123`, OTP: `112233`, expiry: any future):
- Visa accept: `4811 1111 1111 1114`
- Mastercard accept: `5211 1111 1111 1117`
- Full list: https://docs.midtrans.com/docs/testing-payment-on-sandbox

**Testing flow**:
1. Checkout → redirect ke halaman Midtrans
2. Pilih metode bayar (misal BCA VA) → dapat nomor VA dummy
3. Buka simulator VA BCA → input nomor VA → klik "Pay"
4. Midtrans kirim webhook ke `/api/midtrans/webhook` → order status update jadi `paid`

**Warning**: Do NOT attempt real payment on sandbox VA/QR codes. The reference may exist on the real payment provider and funds would be lost irrecoverably.
