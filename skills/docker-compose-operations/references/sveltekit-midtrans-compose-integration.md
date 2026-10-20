# SvelteKit + Midtrans Snap Integration (Docker Compose)

Complete pattern for integrating Midtrans Snap payment gateway into a SvelteKit app running in Docker Compose.

**Updated 2026-07-25**: Migrated from popup-based to redirect-based Snap. See "Popup vs Redirect" section below.

## Architecture

**Redirect-based (current)**:
1. Server creates Snap transaction via Midtrans API → receives `token` + `redirect_url`
2. Server stores `token` in DB as `paymentRef` (fallback for manual retry)
3. Server redirects browser to `redirect_url` (Midtrans payment page)
4. User pays on Midtrans page
5. Midtrans redirects back to `finishCallbackUrl` (our order page + `?from=midtrans`)
6. Webhook updates order status asynchronously

**Why redirect, not popup**: Popup-based Snap (`snap.pay()` via JS) fails silently when:
- Popup blockers block the Snap modal (auto-open from `onMount` without user gesture)
- Snap.js CDN fails to load
- Browser JS errors prevent initialization
Redirect is deterministic — the browser navigates to Midtrans like any link.

## Required Environment Variables

### `.env`
```bash
MIDTRANS_SERVER_KEY=SB-Mid-server-xxxxxxxxxx
MIDTRANS_IS_PRODUCTION=false
PUBLIC_MIDTRANS_CLIENT_KEY=SB-Mid-client-xxxxxxxxxx
MIDTRANS_MERCHANT_ID=Gxxxxxxxxx
```

### `compose.yaml`
```yaml
services:
  app:
    environment:
      - MIDTRANS_SERVER_KEY=${MIDTRANS_SERVER_KEY}
      - MIDTRANS_IS_PRODUCTION=${MIDTRANS_IS_PRODUCTION:-false}
      - PUBLIC_MIDTRANS_CLIENT_KEY=${PUBLIC_MIDTRANS_CLIENT_KEY}
      - MIDTRANS_MERCHANT_ID=${MIDTRANS_MERCHANT_ID}
```

## Server-Side: Create Transaction + Redirect

### `$lib/server/midtrans.ts`
```typescript
import { env } from '$env/dynamic/private'

const MIDTRANS_SERVER_KEY = env.MIDTRANS_SERVER_KEY || ''
const MIDTRANS_IS_PRODUCTION = env.MIDTRANS_IS_PRODUCTION || 'false'

const BASE_URL = MIDTRANS_IS_PRODUCTION === 'true'
    ? 'https://app.midtrans.com'
    : 'https://app.sandbox.midtrans.com'

const SNAP_API_URL = `${BASE_URL}/snap/v1/transactions`
export const SNAP_JS_URL = MIDTRANS_IS_PRODUCTION === 'true'
    ? 'https://app.midtrans.com/snap/snap.js'
    : 'https://app.sandbox.midtrans.com/snap/snap.js'

export interface CreateTransactionParams {
    orderId: string
    amount: number
    items: { id: string; name: string; price: number; quantity: number }[]
    customer: { name: string; phone: string; email?: string; address?: string; city?: string; postalCode?: string }
    finishCallbackUrl?: string  // where Midtrans redirects after payment
}

export async function createTransaction(params: CreateTransactionParams) {
    const body: Record<string, any> = {
        transaction_details: { order_id: params.orderId, gross_amount: params.amount },
        item_details: params.items,
        customer_details: {
            first_name: params.customer.name,
            phone: params.customer.phone,
            email: params.customer.email || undefined,
            shipping_address: params.customer.address ? {
                address: params.customer.address,
                city: params.customer.city,
                postal_code: params.customer.postalCode
            } : undefined
        },
        enabled_payments: ['credit_card', 'bca_va', 'bni_va', 'bri_va', 'mandiri_va',
            'permata_va', 'other_va', 'gopay', 'shopeepay', 'qris', 'cstore', 'akulaku']
    }

    if (params.finishCallbackUrl) {
        body.callbacks = { finish: params.finishCallbackUrl }
    }

    const res = await fetch(SNAP_API_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: 'Basic ' + Buffer.from(MIDTRANS_SERVER_KEY + ':').toString('base64')
        },
        body: JSON.stringify(body)
    })

    const data = await res.json()
    if (data.status_code >= 400) throw new Error(`Midtrans: ${data.status_message}`)

    return { token: data.token, redirectUrl: data.redirect_url }
}
```

### Checkout action (redirect to Midtrans)
```typescript
export const actions: Actions = {
    default: async ({ request, locals, url }) => {
        // ... create order in DB ...

        const finishUrl = `${url.origin}/order/${orderId}?from=midtrans`

        const snap = await createTransaction({
            orderId,
            amount: total,
            items: items.map(i => ({
                id: i.productId, name: i.product.name,
                price: i.product.price, quantity: i.quantity
            })),
            customer: { name, phone, email, address, city, postalCode: zip },
            finishCallbackUrl: finishUrl
        })

        // Store token for fallback manual payment
        await prisma.order.update({
            where: { id: orderId },
            data: { paymentRef: snap.token, paymentMethod: 'midtrans_snap', paymentStatus: 'pending' }
        })

        // Redirect to Midtrans (NOT to order page)
        throw redirect(302, snap.redirectUrl)
    }
}
```

## Order Page: Handle Midtrans Return

### Server (`order/[id]/+page.server.ts`)
```typescript
import { SNAP_JS_URL } from '$lib/server/midtrans'

export const load = async ({ params, url }) => {
    const order = await prisma.order.findUnique({ where: { id: params.id }, include: { items: true } })
    const fromMidtrans = url.searchParams.has('from')
    const snapToken = order.paymentRef || null  // fallback from DB

    return {
        order,
        snapToken,
        fromMidtrans,
        snapJsUrl: SNAP_JS_URL,     // dynamic sandbox/production URL
        isSandbox: SNAP_JS_URL.includes('sandbox')
    }
}
```

### Client — Manual Midtrans Button (fallback, NOT auto-open)
```svelte
<script>
    function loadSnapJs() {
        const script = document.createElement('script')
        script.src = data.snapJsUrl  // dynamic from server, NOT hardcoded
        script.setAttribute('data-client-key', env.PUBLIC_MIDTRANS_CLIENT_KEY || '')
        document.body.appendChild(script)
    }

    function payWithSnap(token: string) {
        window.snap?.pay(token, {
            onSuccess: () => location.reload(),
            onPending: () => location.reload(),
            onError: () => {},
            onClose: () => {}
        })
    }
</script>

{#if fromMidtrans}
    <p>Kembali dari halaman pembayaran. Status akan diperbarui otomatis.</p>
{/if}

{#if snapToken}
    <button onclick={() => { loadSnapJs(); payWithSnap(snapToken) }}>
        Bayar dengan Midtrans
    </button>
{/if}
```

## Popup vs Redirect

| Aspect | Popup (old) | Redirect (current) |
|--------|------------|-------------------|
| UX | Modal overlay on order page | Full redirect to Midtrans |
| Reliability | Popup blockers, JS errors, CDN failures | Browser-native navigation |
| Auto-open | `onMount` → rawan diblok | Server-side 302 → selalu jalan |
| Snap.js | Must load before popup | Not needed for redirect (only fallback button) |
| `finishCallbackUrl` | Not used | Used for return after payment |

## Sandbox Testing

Midtrans sandbox does NOT use real money. Use Midtrans's web-based simulators:

| Payment Method | Simulator URL |
|---------------|---------------|
| BCA VA | `simulator.sandbox.midtrans.com/bca/va/index` |
| BNI VA | `simulator.sandbox.midtrans.com/bni/va/index` |
| BRI VA | `simulator.sandbox.midtrans.com/bri/va/index` |
| Permata VA | `simulator.sandbox.midtrans.com/openapi/va/index` |
| GoPay | `simulator.sandbox.midtrans.com/gopay/ui/index` |
| QRIS | `simulator.sandbox.midtrans.com/qris/index` |
| ShopeePay | `simulator.sandbox.midtrans.com/v2/deeplink/index` |
| Indomaret | `simulator.sandbox.midtrans.com/indomaret/index` |

**Test credit cards**: Visa `4811 1111 1111 1114`, Mastercard `5211 1111 1111 1117`. CVV: `123`. OTP: `112233`.

**Webhook simulation** (verify status update pipeline):
```bash
ORDER_ID=xxx
GROSS=449000
SERVER_KEY=SB-Mid-server-xxx
SIGNATURE=$(echo -n "${ORDER_ID}200${GROSS}${SERVER_KEY}" | sha512sum | cut -d' ' -f1)

curl -X POST 'https://client-site.meowlabs.id/api/midtrans/webhook' \
  -H 'Content-Type: application/json' \
  -d "{
    \"transaction_status\": \"settlement\",
    \"status_code\": \"200\",
    \"signature_key\": \"$SIGNATURE\",
    \"order_id\": \"$ORDER_ID\",
    \"gross_amount\": \"$GROSS\",
    \"fraud_status\": \"accept\"
  }"
```

## Webhook Endpoint

Must be registered in Midtrans Dashboard > Settings > Payment Notification URL:
`https://client-site.meowlabs.id/api/midtrans/webhook`

Also set Finish/Unfinish/Error Redirect URLs (fallback, rarely used since we pass `finishCallbackUrl` dynamically):
`https://client-site.meowlabs.id/`

## Common Pitfalls

### 1. Docker build cache silently serves stale code
`docker compose up -d --build` can cache layers even when source `.ts`/`.svelte` files changed. Fix:
```bash
docker compose build --no-cache app
docker compose up -d
```
Verify: `docker exec <container> grep -c '<expected-pattern>' /app/build/server/chunks/.../<file>.js`

### 2. Snap.js URL hardcoded to sandbox
Always pass `SNAP_JS_URL` from server to client. Hardcoding `app.sandbox.midtrans.com` breaks production.

### 3. Missing `finishCallbackUrl`
Without it, Midtrans redirects to dashboard-configured URL (may not match order ID). Always pass per-order callback.

### 4. `paymentRef` not saved before redirect
If `prisma.order.update()` fails, the token is lost. Retry the DB update (up to 3x with 300ms delay) before redirecting.

### 5. Komerce/other fallback removed
Do NOT keep dead fallback payment providers. They silently activate when the primary fails, creating orders with wrong `paymentMethod` and confusing UX. If the primary gateway fails, show a clear error message with retry option.

### 6. Midtrans domain whitelist (does NOT exist for regular Snap)
Regular Snap does NOT need domain whitelist. The Midtrans docs page `docs.midtrans.com/reference/getting-started-1` is for **BI-SNAP Core API**, which requires PKCS8 keypair exchange, IP whitelisting, and credential exchange. Do not confuse the two. Regular Snap only needs: Server Key, Client Key, Merchant ID, and optionally webhook URL set in dashboard. No domain registration step.

### 7. Shell env var overrides .env in Docker Compose
When credential rotation appears to fail (container still has old key), check if the variable is exported in the shell (`~/.bashrc`, `~/.profile`). Docker Compose resolves `${VAR}` from shell environment first, `.env` file second. Detection: `echo "${VAR:-(not set)}"`. Fix: either unset the shell var, or inline-export the correct value before `compose up`.

---

## Sandbox → Production Cutover Checklist

When switching from Midtrans Sandbox to Production, verify these code changes in addition to credential rotation:

| Check | File | What to change |
|-------|------|----------------|
| Snap.js URL fallback | `order/[id]/+page.svelte` | Remove hardcoded `'https://app.sandbox.midtrans.com/snap/snap.js'` fallback — use `data.snapJsUrl` from server only |
| CSP headers | `hooks.server.ts` | Replace hardcoded `app.sandbox.midtrans.com` / `api.sandbox.midtrans.com` with dynamic domain from `SNAP_JS_URL` |
| Sandbox simulator section | `order/[id]/+page.svelte` | Must be gated by `{#if data.isSandbox && ...}` — verify `isSandbox` is `false` in production |
| `isSandbox` derivation | `order/[id]/+page.server.ts` | `SNAP_JS_URL.includes('sandbox')` — auto-detects based on `MIDTRANS_IS_PRODUCTION` |
| `enabled_payments` | `$lib/server/midtrans.ts` | Sandbox allowed all payment methods; production may have different availability per merchant agreement |

**Verification after cutover**:
```bash
# CSP must NOT contain 'sandbox'
curl -sI http://localhost:3301/ | grep -i sandbox
# Should return nothing

# App must serve 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3301/

# Order page must not expose sandbox simulator
# (manually verify by creating a test order and inspecting page source)
```

## Verification
```bash
# Check env vars
docker exec <container> node -e "
console.log('SERVER_KEY:', process.env.MIDTRANS_SERVER_KEY ? 'SET' : 'MISSING')
console.log('CLIENT_KEY:', process.env.PUBLIC_MIDTRANS_CLIENT_KEY ? 'SET' : 'MISSING')
"

# Test full checkout flow (add to cart → checkout → should redirect to midtrans.com)
# Response should be: {"type":"redirect","status":302,"location":"https://app.sandbox.midtrans.com/..."}

# Test webhook
curl -X POST 'http://localhost:3301/api/midtrans/webhook' -H 'Content-Type: application/json' -d '{
  "transaction_status":"settlement","status_code":"200",
  "signature_key":"SIG","order_id":"xxx","gross_amount":"10000"
}'
```
