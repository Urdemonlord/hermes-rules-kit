---
name: indonesian-ecommerce-integrations
description: Integrate Indonesian e-commerce backends — Midtrans Snap/Core payment, Biteship shipping (rates + tracking), QRIS, GoPay/GoBiz merchant, mobile-responsive storefront patterns, and admin dashboard patterns. Covers checkout, voucher systems, stock restore, auto-cancel cron, cart badge, and admin dashboard tech-debt audit. Load when adding ongkir, payment gateway, tracking, checkout, or admin features to any Indonesian storefront project.
triggers:
  - "midtrans"
  - "midtrans snap"
  - "midtrans redirect"
  - "ongkir"
  - "rajaongkir"
  - "raja ongkir"
  - "shipping cost Indonesia"
  - "cek ongkos kirim"
  - "kommerce payment"
  - "komerce"
  - "virtual account payment"
  - "QRIS payment"
  - "qris dinamis"
  - "dynamic qris"
  - "gopay merchant"
  - "gopay merchant panel"
  - "gopay qris"
  - "gobiz"
  - "cek pesanan"
  - "order tracking"
  - "lacak pesanan"
  - "order lookup"
  - "tracking UX"
  - "order timeline"
  - "SvelteKit nav active"
  - "SvelteKit header highlight"
---

  - "indonesian payment gateway"
  - "midtrans alternative"
  - "checkout page"
  - "pembayaran"
  - "tracking"
  - "resi"
  - "waybill"
  - "lacak paket"
---

# Indonesian E-Commerce Backend Integrations

Covers RajaOngkir v2 shipping cost API, RajaOngkir tracking API, Komerce Payment gateway, and mobile-responsive e-commerce patterns.

## Quick Reference

| Service | Base URL | Auth Header | Content-Type |
|---------|----------|-------------|--------------|
| **Biteship** | `https://api.biteship.com/v1` | `Authorization: Bearer <key>` | `application/json` |
| **RajaOngkir v2 (Shipping)** | `https://rajaongkir.komerce.id/api/v1` | `key: YOUR_KEY` | `application/json` for GET, `application/x-www-form-urlencoded` for POST |
| **Komerce Payment** | `https://api-sandbox.collaborator.komerce.id/user` (sandbox) / `https://api.collaborator.komerce.id/user` (live) | `x-api-key: YOUR_KEY` | `application/json` |
| **Midtrans Core API** | `https://api.midtrans.com/v2` (production) / `https://api.sandbox.midtrans.com/v2` (sandbox) | `Authorization: Basic base64(server_key:)` | `application/json` |

## RajaOngkir v2 — Critical Pitfalls

### 1. Cost endpoint uses FORM-ENCODED (NOT JSON)
The `POST /api/v1/calculate/domestic-cost` endpoint **only accepts form-encoded data**, not JSON. Sending JSON with `Content-Type: application/json` returns a cryptic Go validator error: `CalculateRequestV2.Origin failed on the 'required' tag` even when the field IS present. This wastes ~15 minutes of debugging.

**Correct request:**
```bash
curl -X POST https://rajaongkir.komerce.id/api/v1/calculate/domestic-cost \
  -H "key: YOUR_KEY" \
  -d "origin=65205&destination=17473&weight=500&courier=jne"
```

### 2. Response fields use `_name` suffix
The v2 API returns `province_name`, `city_name`, `district_name`, `subdistrict_name` (not `province`, `city`, `district`, `subdistrict` like v1). Destination search returns `label` (not `name`).

### 3. Cost response is a flat array
The response `data` is a flat array of options, not `{ origin, destination, costs: [] }` nested structure.

### 4. IDs are subdistrict-level numbers
The origin/destination IDs are subdistrict-level integers (e.g., `65205` for Pecangaan Kulon, Jepara), not city-level codes from v1.

## Komerce Payment — API Contract

### Auth
Uses `x-api-key` header (NOT the same `key:` as shipping).

### Create Payment
```
POST /api/v1/user/payment/create
```
Body:
```json
{
  "order_id": "string (required)",
  "payment_type": "bank_transfer | qris",
  "channel_code": "BCA | BNI | BRI | MANDIRI | QRIS",
  "amount": 25000,
  "customer": {
    "name": "string (required)",
    "email": "string (required)",
    "phone": "string (required, minimum 8 digits)"
  },
  "items": [{
    "name": "string",
    "price": 25000,
    "quantity": 1
  }]
}
```
Returns: `payment_id`, `va_number` (for bank_transfer), `qr_string` (for qris), `payment_url`, `bank_code`, `bank_name`, `expired_at`.

### Status Check
```
GET /api/v1/user/payment/status/{payment_id}
```
Returns full status including `merchant_receives` (fee deducted), `paid_at`, `sender_name`.

### Cancel
```
POST /api/v1/user/payment/cancel
Body: { "payment_id": "..." }
```

### Webhook
Komerce sends POST to your configured webhook URL with `{ payment_id, status, order_id }`. Always double-check status via the GET endpoint before acting — never trust webhook body alone.

## Mobile-Responsive E-Commerce Patterns

When building storefronts for Indonesian market (70%+ mobile traffic):

### Image display
- Mobile: `object-cover` (full-bleed, no white bars for portrait fashion photos)
- Desktop: `object-contain` (see full product)
- Use: `class="object-cover md:object-contain"`

### Checkout column ordering
- On mobile, show order summary BEFORE the long shipping form
- Use: order-first div with `class="order-1 md:order-2"` for summary, `class="order-2 md:order-1"` for form

### Touch targets
- Minimum 44x44px tap area (Tailwind: `w-11 h-11` or `py-3` + `px-4`)
- Always show wishlist/action buttons (never `opacity-0 group-hover:opacity-100` — invisible on touch)
- Add `active:` states for tactile feedback: `active:scale-95`, `active:bg-sand/30`
- Radio buttons: `w-5 h-5 accent-charcoal` for tappable size
- Add `touch-action: manipulation` to body CSS to prevent double-tap zoom

### Header navigation
- Mobile menu should include ALL categories, not just top 2-3
- Use 48px touch targets in mobile nav (`py-3 px-3`)

### Hero carousel
- Mobile: `min-h-[50vh]` (not 60-80vh — pushes content too far)
- Desktop: `md:h-[80vh]`

## Midtrans Snap — Redirect Approach (Recommended)

**Use full-page redirect to Midtrans, NOT the Snap.js popup.** The popup approach (`window.snap.pay()`) is unreliable — browser popup blockers, CSP issues, and silent JS failures cause ~47% of orders to have no payment interaction. The redirect approach eliminates all of these.

### Redirect flow

1. Checkout POST → `createTransaction()` with `finishCallbackUrl` → redirect user to `snap.redirectUrl`
2. **Store BOTH `paymentRef` (token) AND `paymentUrl` (redirect URL) on the Order.** The URL enables direct "Bayar" buttons on list views without needing Snap.js. Add `paymentUrl String?` column to Order schema, then `prisma db push` for migration.
3. User pays on Midtrans page (all payment methods available)
4. Midtrans redirects back to `finishCallbackUrl` (`/order/{id}?from=midtrans`)
5. Webhook updates order status (already handled by existing webhook handler)

### Checkout server action — redirect pattern

```typescript
// src/routes/checkout/+page.server.ts
import { createTransaction } from '$lib/server/midtrans'
import { env } from '$env/dynamic/private'

const MIDTRANS_KEY = env.MIDTRANS_SERVER_KEY || ''

// In the default action, after creating the order:
const origin = url.origin
const finishUrl = `${origin}/order/${orderId}?from=midtrans`

if (MIDTRANS_KEY) {
  try {
    const snap = await createTransaction({
      orderId,
      amount: total,
      items: items.map(i => ({
        id: i.productId, name: i.product.name, price: i.product.price, quantity: i.quantity
      })),
      customer: { name, phone, email, address, city, postalCode: zip },
      finishCallbackUrl: finishUrl   // Midtrans redirects here after payment
    })

    // Retry DB update — SQLite locking can fail under concurrent load
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        await prisma.order.update({
          where: { id: orderId },
          data: {
            paymentRef: snap.token,
            paymentUrl: snap.redirectUrl,  // ← store for direct pay buttons
            paymentMethod: 'midtrans_snap',
            paymentStatus: 'pending'
          }
        })
        break
      } catch (dbErr) {
        if (attempt === 2) console.error('[checkout] DB update failed after 3 retries')
        else await new Promise(r => setTimeout(r, 300))
      }
    }

    // Full redirect to Midtrans payment page (NOT /order/{id})
    throw redirect(302, snap.redirectUrl)
  } catch (e: any) {
    if (e instanceof Response || (e?.status && e?.location)) throw e
    console.error('[checkout] Midtrans error:', e?.message || e)
    // fallback to Komerce below
  }
}
```

### Order page server — handle redirect-back

```typescript
// src/routes/order/[id]/+page.server.ts
import { SNAP_JS_URL } from '$lib/server/midtrans'

export const load: PageServerLoad = async ({ params, locals, url }) => {
  const order = await prisma.order.findUnique({ where: { id: params.id }, include: { items: true } })
  if (!order) throw error(404, 'Pesanan tidak ditemukan')

  const fromMidtrans = url.searchParams.has('from')
  let snapToken: string | null = null
  let paymentUrl: string | null = null

  // Read snap token from DB paymentRef
  if (order.paymentMethod === 'midtrans_snap' && order.paymentRef) {
    snapToken = order.paymentRef
  }
  // Read stored redirect URL (enables direct-pay from list views)
  if (order.paymentUrl) {
    paymentUrl = order.paymentUrl
  }

  return {
    order: { ...order, total: order.total },
    paymentError: url.searchParams.has('payment_error'),
    snapToken,
    paymentUrl,          // ← enables direct "Bayar" button
    fromMidtrans,
    snapJsUrl: SNAP_JS_URL
  }
}
```

### Order page client — multi-state payment buttons

The payment section must handle FOUR distinct states. Do NOT use a single `paymentDetails` object — it was never populated for Midtrans orders (only Komerce), making it dead code.

```svelte
<script lang="ts">
  import { env } from '$env/dynamic/public'

  let snapToken = $state<string | null>(data.snapToken || null)
  let paymentUrl = $state(data.paymentUrl || null)
  let snapExpired = $state(false)   // differentiate "not tried" vs "tried & failed"
  let paying = $state(false)
  let snapLoaded = $state(false)

  // State 1: Direct redirect to Midtrans payment page (best UX)
  function goToPaymentPage() {
    if (paymentUrl) window.location.href = paymentUrl
  }

  // State 2: Snap.js popup (fallback when URL not stored)
  function loadSnapJs(): Promise<void> {
    return new Promise((resolve) => {
      if (snapLoaded) { resolve(); return; }
      const script = document.createElement('script')
      script.src = data.snapJsUrl || 'https://app.sandbox.midtrans.com/snap/snap.js'
      script.setAttribute('data-client-key', env.PUBLIC_MIDTRANS_CLIENT_KEY || '')
      script.onload = () => { snapLoaded = true; resolve() }
      script.onerror = () => resolve()
      document.body.appendChild(script)
    })
  }

  function payWithSnap(token: string) {
    if (!window.snap) return
    paying = true
    window.snap.pay(token, {
      onSuccess: () => window.location.reload(),
      onPending: () => window.location.reload(),
      onError: () => {
        // Token expired — show "Batas waktu habis", don't just hide button
        snapExpired = true
        snapToken = null
        paying = false
      },
      onClose: () => { paying = false }
    })
  }
</script>

{#if order.paymentStatus === 'pending'}
  <div class="border border-yellow-200 bg-yellow-50 rounded-lg p-6">
    <h2>Pembayaran Tertunda</h2>
    <p>Total: <strong>{formatPrice(order.total)}</strong></p>

    {#if snapExpired}
      <!-- State 4: Token tried and failed = expired -->
      <div class="bg-red-50 border border-red-200 rounded p-4">
        <p class="font-medium">Batas waktu pembayaran habis</p>
        <p class="text-xs">Token pembayaran sudah kadaluarsa. Silakan buat pesanan baru.</p>
      </div>
      <a href="/cart" class="block w-full bg-terracotta text-white py-3 rounded text-center">
        Pesan Ulang
      </a>

    {:else if paymentUrl}
      <!-- State 1: Direct redirect (primary — no Snap.js needed) -->
      <p class="text-xs">Anda akan diarahkan ke halaman pembayaran Midtrans.</p>
      <div class="flex items-center gap-2 text-xs">
        <span class="w-2 h-2 rounded-full bg-yellow-400"></span>
        Batas pembayaran: 24 jam
      </div>
      <button onclick={goToPaymentPage} class="w-full bg-terracotta text-white py-3 rounded">
        💳 Bayar Sekarang — Rp {formatPrice(order.total)}
      </button>

    {:else if snapToken}
      <!-- State 2: Snap.js popup (fallback) -->
      <p class="text-xs">Klik untuk membuka popup pembayaran Midtrans.</p>
      <button
        onclick={async () => { await loadSnapJs(); payWithSnap(snapToken!) }}
        disabled={paying}
        class="w-full bg-terracotta text-white py-3 rounded disabled:opacity-50"
      >
        {paying ? 'Membuka pembayaran...' : '💳 Bayar dengan Midtrans'}
      </button>

    {:else}
      <!-- State 3: No payment method available -->
      <p>Menunggu konfirmasi pembayaran. Status diperbarui otomatis.</p>
    {/if}
  </div>
{/if}
```

### Pitfall: `paymentDetails` was dead code for Midtrans

The old pattern used a `paymentDetails` object that was only populated for Komerce orders (`getPaymentStatus()`). For Midtrans orders, `paymentDetails` was always `undefined`, so the `{@if paymentDetails?.paymentUrl}` branch never activated. The Snap.js button appeared as a fallback — but if the token was expired, `onError` set `snapToken = null` and the button DISAPPEARED silently.

**Fix:** Replace `paymentDetails` with explicit `paymentUrl` (stored at checkout) and `snapToken`. Add `snapExpired` boolean to differentiate "no token" from "token failed."

### Pitfall: expired Snap token silently hides button

Midtrans Snap tokens expire after ~24 hours (varies by payment method). The old `onError: () => { snapToken = null }` makes the button vanish with only "Menunggu konfirmasi pembayaran" text. The user has no way to know what happened or what to do.

**Fix:** Set `snapExpired = true` on error. Show a clear "Batas waktu habis" message with a "Pesan Ulang" CTA. Never let a failed payment attempt result in a blank/informational state.

### Direct "Bayar" buttons on list views

Orders list, account dashboard, and guest lookup (`/orders`) should all show a direct "💳 Bayar" button for pending orders — NOT just "→ Lanjutkan pembayaran" text. This eliminates 2 extra clicks (list → detail → button).

**Pattern for list views:**
```svelte
{#if order.paymentStatus === 'pending'}
  <div class="mt-3 flex gap-2">
    <a href="/order/{order.id}" class="flex-1 text-center border py-2 rounded">Detail</a>
    {#if order.paymentUrl}
      <a href={order.paymentUrl} class="flex-1 text-center bg-terracotta text-white py-2 rounded">💳 Bayar</a>
    {:else}
      <a href="/order/{order.id}" class="flex-1 text-center bg-terracotta text-white py-2 rounded">💳 Bayar</a>
    {/if}
  </div>
{/if}
```

**Server-side:** All endpoints that return order lists must include `paymentUrl` in the Prisma `select`:
- `account/+page.server.ts`
- `account/orders/+page.server.ts`
- `api/order/lookup/+server.ts`

### Pitfall: Snap.js URL hardcoded to sandbox

The old pattern hardcoded `'https://app.sandbox.midtrans.com/snap/snap.js'` in the Svelte component. In production, this loads the sandbox Snap.js with a production token → mismatch → payment popup fails silently.

**Fix:** Export `SNAP_JS_URL` from `$lib/server/midtrans.ts` (already computed from `MIDTRANS_IS_PRODUCTION` env), pass it to the client via page server data as `snapJsUrl`, and use `data.snapJsUrl` in the component.

### Pitfall: Empty `paymentRef` = Midtrans silently failed

**Diagnostic query:**
```sql
SELECT paymentMethod,
  CASE WHEN paymentRef IS NULL OR paymentRef = '' THEN 'EMPTY' ELSE 'OK' END as ref_status,
  COUNT(*) as cnt
FROM 'Order' WHERE paymentMethod = 'midtrans_snap'
GROUP BY ref_status;
```

If ~50% are empty, `createTransaction()` is failing and the catch block falls through to Komerce (which also fails to save). Root causes:
1. Midtrans API intermittent failures (network, rate limiting)
2. SQLite `prisma.order.update()` failing after Midtrans succeeds — token lost
3. Double-submit: second request clears cart before the first finishes

**Fix:** The retry loop above covers case 2. Case 1 needs `finishCallbackUrl` + webhook resilience. Case 3 needs frontend debounce on submit button.

### Pitfall: `snap.redirectUrl` can be `undefined` — crashes `redirect()` with TypeError

When Midtrans returns a response without `redirect_url` (rare but possible — intermittent API issues, partial responses with `token` but no `redirect_url`), the checkout code does `throw redirect(302, snap.redirectUrl)` with `undefined` as the location. SvelteKit's `redirect()` calls `.toString()` on the location parameter:

```
TypeError: Cannot read properties of undefined (reading 'toString')
    at redirect (utils.js:359:12)
```

This TypeError is NOT caught by `if (e instanceof Response || (e?.status && e?.location)) throw e` — it falls through to the catch block, logs `[checkout] Midtrans error: Cannot read properties of undefined (reading 'toString')`, and redirects to `/order/{id}?payment_error=1`. The user sees "Sistem pembayaran sedang bermasalah" but the root cause is invisible.

**Fix — guard redirectUrl before passing to redirect():**
```typescript
const snap = await createTransaction({ ... })

if (!snap.redirectUrl) {
  console.error('[checkout] Midtrans returned no redirect_url — token:', snap.token, '| raw snap:', JSON.stringify(snap))
  throw new Error('Midtrans tidak mengembalikan URL pembayaran')
}

throw redirect(302, snap.redirectUrl)
```

Also add diagnostic logging in `createTransaction()` to capture the raw Midtrans response when `token` or `redirect_url` is missing:
```typescript
const data = await res.json()

if (data.status_code && data.status_code >= 400) {
  console.error('[midtrans] API error — status:', res.status, 'body:', JSON.stringify(data))
  throw new Error(`Midtrans error: ${data.status_message || 'Unknown error'}`)
}

if (!data.token || !data.redirect_url) {
  console.error('[midtrans] Missing token or redirect_url — status:', res.status, 'body:', JSON.stringify(data))
}
```

### Pitfall: Midtrans `gross_amount` must equal sum of `item_details`

Midtrans validates: `transaction_details.gross_amount` === sum of all `item_details[i].price * item_details[i].quantity`. If they don't match, the API returns **400** with `error_messages: ["transaction_details.gross_amount is not equal to the sum of item_details"]`. This happens when the checkout total includes shipping cost or voucher discounts not reflected as line items. The response has no `token` or `redirect_url`, so the guard below catches it.

**Symptom:** Log shows `[midtrans] Missing token or redirect_url — status: 400 body: {"error_messages":["transaction_details.gross_amount is not equal to the sum of item_details"]}`. The checkout falls through to `/order/{id}?payment_error=1`.

**Fix — add shipping and voucher as line items:**
```typescript
// Build item_details so the sum matches gross_amount exactly
const midtransItems = items.map(i => ({
  id: i.productId, name: i.product.name, price: i.product.price, quantity: i.quantity
}))
if (shippingCost > 0) {
  midtransItems.push({ id: 'SHIPPING', name: 'Ongkos Kirim', price: shippingCost, quantity: 1 })
}
if (voucherDiscount > 0) {
  midtransItems.push({ id: 'VOUCHER', name: `Diskon: ${voucherName}`, price: -voucherDiscount, quantity: 1 })
}
// Now sum(midtransItems.price * quantity) === total === gross_amount ✓
```

**Diagnostic check** — verify the math before calling Midtrans:
```typescript
const itemsSum = midtransItems.reduce((s, i) => s + i.price * i.quantity, 0)
if (itemsSum !== total) {
  console.error('[checkout] Item sum mismatch — items:', itemsSum, 'total:', total)
}
```

### Pitfall: Komerce RajaOngkir proxy daily rate limit (429)

The Komerce proxy (`rajaongkir.komerce.id`) has a daily request limit. When exceeded, all ongkir endpoints return `{"meta":{"message":"Daily limit exceeded","code":429,"status":"error"}}`. This silently breaks the city search autocomplete in checkout → user can't select a city → courier/shipping form never renders → checkout appears to have "missing fields."

**Detection:** Check both the Komerce proxy AND the real RajaOngkir API (`api.rajaongkir.com`). The real API may also be unreachable from some VPS IPs (TCP timeout to 203.0.113.10 port 443).

**Fix path:** Switch to RajaOngkir API directly with a real RajaOngkir account (not Komerce-issued key). Note: the real RajaOngkir API uses different endpoints and response format than the Komerce proxy — don't just change the base URL.

**Temporary fallback:** Hardcode a local cities JSON file (~500 entries) and rewrite the search endpoint to use local data. See `references/local-city-fallback.md`. This keeps the checkout city search working even when the API is down. Cost calculation still needs the API — this only fixes the search.

### Pitfall: `paymentMethod` left null when all gateways fail

Always set a default on order creation:
```typescript
paymentMethod: 'pending',  // will be updated when gateway responds
paymentStatus: 'pending',
```

And in the final catch block, best-effort set `paymentMethod: 'failed'` so the order is never orphaned without a payment method.

### Midtrans Snap transaction — adding finish callback

The `createTransaction()` function in `midtrans.ts` should accept `finishCallbackUrl`:

```typescript
export interface CreateTransactionParams {
  // ... existing fields ...
  finishCallbackUrl?: string  // URL Midtrans redirects to after payment
}

// In createTransaction body:
const body: Record<string, any> = {
  transaction_details: { ... },
  item_details: [ ... ],
  customer_details: { ... },
  enabled_payments: [ ... ]
}

if (params.finishCallbackUrl) {
  body.callbacks = { finish: params.finishCallbackUrl }
}
```

Without this, Midtrans redirects to the default URL set in the dashboard (or nowhere).

### Midtrans webhook

Already covered by the existing `midtrans.ts` lib. The webhook handler verifies signature with SHA512 hash:
```
SHA512(order_id + status_code + gross_amount + server_key)
```

Status mapping:
| Midtrans Status | Payment Status | Order Status |
|---|---|---|
| `capture`, `settlement` | `paid` | `processing` |
| `pending` | `pending` | `pending` |
| `deny`, `expire`, `cancel` | `failed` | `cancelled` |
| `refund` | `refunded` | `cancelled` |

### Pitfall: CSP blocks Midtrans Snap.js (popup never appears)

SvelteKit projects with CSP headers in `hooks.server.ts` will block Snap.js scripts and iframes. The order page shows "Menunggu Pembayaran" but the Midtrans popup never appears. Browser console shows CSP violation errors.

**Preferred: dynamic CSP from `SNAP_JS_URL`** — avoids hardcoding both sandbox and production URLs. The `SNAP_JS_URL` already switches based on `MIDTRANS_IS_PRODUCTION`, so derive CSP domains from it:

```typescript
// src/hooks.server.ts
import { SNAP_JS_URL } from '$lib/server/midtrans'

// ... in handle():
const snapJsDomain = new URL(SNAP_JS_URL).origin           // https://app.midtrans.com OR https://app.sandbox.midtrans.com
const snapApiDomain = snapJsDomain.replace('app.', 'api.') // https://api.midtrans.com    OR https://api.sandbox.midtrans.com

response.headers.set('Content-Security-Policy', [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com ${snapJsDomain}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: https:",
  "font-src 'self' https://fonts.gstatic.com",
  `connect-src 'self' ${snapJsDomain} ${snapApiDomain} https://api.biteship.com`,
  `frame-src 'self' https://www.google.com ${snapJsDomain}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; '))
```

This eliminates the `app.sandbox.midtrans.com` in production or `app.midtrans.com` in sandbox — only the correct domain is added. No CSP drift between environments.

**Static fallback (legacy):** If `SNAP_JS_URL` is unavailable at CSP-set time, hardcode both domains:

```typescript
"script-src 'self' ... https://app.sandbox.midtrans.com https://app.midtrans.com"
"connect-src 'self' ... https://app.sandbox.midtrans.com https://api.sandbox.midtrans.com https://app.midtrans.com https://api.midtrans.com"
"frame-src 'self' ... https://app.sandbox.midtrans.com https://app.midtrans.com"
```

### Pitfall: Midtrans Snap does NOT require domain whitelist

For standard Snap integration (not BI-SNAP Core API), the Midtrans MAP dashboard does **NOT** have a domain whitelist or domain registration field for Client Key. The Client Key is safe to expose on the frontend — it only initiates payment sessions. The Server Key (stored server-side) handles actual transaction authorization.

Do **NOT** tell users to register their domain in MAP dashboard > Settings > Access Keys > Domains. This setting does not exist for standard Snap merchants. It only exists for BI-SNAP Core API merchants who go through a separate credential-exchange onboarding process (`docs.midtrans.com/reference/getting-started-1`).

**What you need for production Snap:**
- `MIDTRANS_MERCHANT_ID` (e.g., `M283228709`)
- `PUBLIC_MIDTRANS_CLIENT_KEY` (e.g., `Mid-client-...`) — injected into frontend via `$env/dynamic/public`
- `MIDTRANS_SERVER_KEY` (e.g., `Mid-server-...`) — server-side only, in `$env/dynamic/private`
- `MIDTRANS_IS_PRODUCTION=true`

That is it. No domain registration step.

### Pitfall: $env/static/public fails in Docker builds

For the Snap.js client key accessible client-side, use `$env/dynamic/public` NOT `$env/static/public`. Docker injects env vars at runtime via compose, but `static/public` inlines at build time — causing `[MISSING_EXPORT] "env" is not exported` build failure. Use `import { env } from '$env/dynamic/public'` in the order page component.

---

## SvelteKit Frontend Patterns

### Active Nav State

Use `$page.url.pathname` from `$app/stores` to highlight the current page in navigation. The `border-b-2` underline works cleanly across both transparent-hero and solid-scrolled header states.

```svelte
<script>
  import { page } from '$app/stores';
  const currentPath = $derived($page.url.pathname);
  function navClass(href: string) {
    const active = currentPath.startsWith(href);
    const base = 'transition py-1 border-b-2';
    if (active) return `${base} border-accent ...`;
    return `${base} border-transparent ...`;
  }
</script>
```

### Data Duplication Pitfall

When static content (blog articles, testimonials) is defined in both a dedicated route page AND a server load function, changes MUST be applied to both files. A missing field in server load silently breaks the homepage section while the dedicated route looks fine.

### Order Tracking UX

For guest-facing "Cek Pesanan" pages, see `references/order-tracking-ux-checklist.md` for the comprehensive 10-point audit framework: card wrapper, CTA button, placeholder text, helper text, states (loading/error/not-found/found), timeline visualization, status badges, active nav, input sizing, and icons.

### Pitfall: `use:enhance` must call `applyAction(result)` for redirects

When using `use:enhance` on the checkout form, the callback MUST call `await applyAction(result)` to process server-side `throw redirect()`. Without it, the form POST completes but the page stays stuck — the redirect is swallowed client-side.

```svelte
<!-- WRONG — redirect swallowed, page stuck -->
<form method="POST" use:enhance={() => {
  loading = true;
  return async () => { loading = false; };
}}>

<!-- RIGHT — redirect processed by SvelteKit -->
<form method="POST" use:enhance={() => {
  loading = true;
  return async ({ result }) => {
    loading = false;
    await applyAction(result);
  };
}}>
```

### Pitfall: `invalidateAll()` needed to update layout data after form actions

SvelteKit `use:enhance` + `applyAction(result)` only re-runs the **page's** `load` function, NOT the **layout's** `load`. If your layout depends on data that form actions modify (e.g., cart item count in `+layout.server.ts`), the layout data becomes stale until the next full-page navigation. The user must refresh to see the updated badge.

**Symptom:** Cart badge number doesn't change when user clicks "Add to Cart" — requires page refresh to update.

**Fix — call `invalidateAll()` after successful form submission:**

```svelte
<script>
  import { invalidateAll } from '$app/navigation'
</script>

<!-- On product page — add-to-cart form -->
<form method="POST" action="/cart?/add" use:enhance={() => {
  return async ({ result }) => {
    await applyAction(result)
    await invalidateAll()  // re-runs layout load → cartCount updates
  }
}}>

<!-- On cart page — update/remove forms -->
<form method="POST" action="?/update" use:enhance={() => {
  return async ({ result }) => {
    if (result.type === 'success') await invalidateAll()
  }
}}>

<form method="POST" action="?/remove" use:enhance={() => {
  return async ({ result }) => {
    if (result.type === 'success') await invalidateAll()
  }
}}>
```

**When NOT to use `invalidateAll()`:** Only use it when layout data genuinely depends on the form action's side effects. For isolated page-level data, `applyAction(result)` alone is sufficient and more efficient.

### Cart badge — SSR layout data pattern

To show a live cart item count badge on the cart icon in the navbar:

**1. Add `cartCount` to `+layout.server.ts`:**
```typescript
import { prisma } from '$lib/server/db'

export const load: LayoutServerLoad = async ({ locals }) => {
  const cartCount = await prisma.cartItem.count({
    where: { sessionId: locals.cartId }
  })
  return {
    user: locals.user ? { id: locals.user.id, name: locals.user.name, email: locals.user.email, role: locals.user.role } : null,
    cartCount
  }
}
```

**2. Pass to Header component in `+layout.svelte`:**
```svelte
<Header user={data.user} cartCount={data.cartCount} />
```

**3. Render badge in `Header.svelte`:**
```svelte
<script>
  let { user, cartCount = 0 } = $props()
</script>

<a href="/cart" class="relative ..." aria-label="Cart">
  <svg><!-- cart icon --></svg>
  {#if cartCount > 0}
    <span class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center
      rounded-full bg-terracotta text-white text-[10px] font-bold">
      {cartCount > 99 ? '99+' : cartCount}
    </span>
  {/if}
</a>
```

**4. Update layout on every cart mutation** — use `invalidateAll()` as described above. This ensures the badge updates without page refresh after add/update/remove.

### Pitfall: Client key is separate from Server key

The Snap.js `data-client-key` attribute must be set to your **Midtrans Client Key** (from dashboard, Settings > Access Keys), NOT the Server Key. Without a valid client key, Snap popup shows a generic error. Tell the user to send both Server Key AND Client Key.

## Midtrans Environment Switch — Sandbox → Production

When switching a live storefront from sandbox to production Midtrans:

1. Update `.env` with production credentials:
   ```
   MIDTRANS_SERVER_KEY=Mid-server-xxx
   MIDTRANS_IS_PRODUCTION=true
   PUBLIC_MIDTRANS_CLIENT_KEY=Mid-client-xxx
   MIDTRANS_MERCHANT_ID=M123456789
   ```
2. **`docker compose up -d --force-recreate`** — plain `restart` won't pick up new `.env` values because Docker Compose only re-reads `.env` on `up`.
3. Verify runtime env:
   ```bash
   docker inspect <container> --format '{{json .Config.Env}}' | python3 -c "import sys,json; [print(e) for e in json.load(sys.stdin) if 'MIDTRANS' in e]"
   ```
4. Production key format: `Mid-server-...` / `Mid-client-...` (no `SB-` prefix). Sandbox keys always start with `SB-Mid-`.
5. Verify `SNAP_JS_URL` switches automatically — `midtrans.ts` already reads `MIDTRANS_IS_PRODUCTION` to choose between `app.midtrans.com` and `app.sandbox.midtrans.com`.
6. Verify CSP headers — should only contain production domains (see CSP pitfall above).
7. **No domain whitelist needed** — standard Snap integration doesn't require domain registration in MAP dashboard.

### Sandbox simulator UI — auto-hidden in production

The order page sandbox simulator section is gated by `isSandbox`, derived server-side:
```typescript
// +page.server.ts
isSandbox: SNAP_JS_URL.includes('sandbox')
```
When `MIDTRANS_IS_PRODUCTION=true`, `SNAP_JS_URL` is `app.midtrans.com` → `isSandbox=false` → simulator links hidden. No code removal needed — the gate is automatic.

### Pitfall: hardcoded Snap.js fallback URL

The old pattern hardcoded `'https://app.sandbox.midtrans.com/snap/snap.js'` as a fallback in the Svelte component. In production, this loads the sandbox Snap.js with a production token → mismatch → payment popup fails silently.

**Fix:** Always use the server-provided `data.snapJsUrl`. No client-side fallback needed — if the server doesn't provide a URL, the payment flow is already broken.

Use Midtrans Core API `/v2/charge` to generate **dynamic QRIS** — each transaction gets a fresh QR code with a specific amount. This is the primary method for QRIS in e-commerce/POS, distinct from Static QRIS (single QR reused, customer enters amount manually).

### Static vs Dynamic QRIS

| | **Dynamic QRIS** | **Static QRIS** |
|---|---|---|
| **QR code** | Baru setiap transaksi | Satu QR dipakai terus |
| **Amount** | Ditentukan merchant via API | Customer input manual |
| **Order ID** | Bisa custom (`order_id`) | Auto-generated |
| **Use case** | E-commerce, POS, invoice | Offline store, bazaar, QR meja |
| **API** | `POST /v2/charge` | Generate from Midtrans dashboard |

### Prerequisites

1. GoPay payment method must be **activated first** on Midtrans dashboard before QRIS can be enabled
2. Existing Midtrans merchants with active GoPay automatically qualify for QRIS
3. Static QRIS requires additional onboarding (~1 working day) after dynamic QRIS is active

### Charge API — Create Dynamic QRIS

```
POST /v2/charge
```

**Auth:** `Authorization: Basic base64(server_key:)`  (note: colon after server_key, no password)

**Request:**
```json
{
  "payment_type": "qris",
  "transaction_details": {
    "order_id": "ORDER-001",
    "gross_amount": 275000
  },
  "item_details": [
    {
      "id": "item01",
      "price": 275000,
      "quantity": 1,
      "name": "Kemeja Tenun Ikat"
    }
  ],
  "customer_details": {
    "first_name": "the operator",
    "last_name": "Utomo",
    "email": "user@example.com",
    "phone": "081223323423"
  },
  "qris": {
    "acquirer": "gopay"
  }
}
```

**Acquirer options:**

| `acquirer` value | Provider |
|---|---|
| `gopay` | GoPay |
| `airpay shopee` | ShopeePay (AirPay Shopee) |

If `qris.acquirer` is omitted, Midtrans auto-selects based on merchant configuration.

**Response (201 Created):**
```json
{
    "status_code": "201",
    "status_message": "QRIS transaction is created",
    "transaction_id": "0d8178e1-c6c7-4ab4-81a6-893be9d924ab",
    "order_id": "ORDER-001",
    "gross_amount": "275000.00",
    "currency": "IDR",
    "payment_type": "qris",
    "transaction_time": "2020-09-29 11:46:13",
    "transaction_status": "pending",
    "fraud_status": "accept",
    "acquirer": "gopay",
    "actions": [
        {
            "name": "generate-qr-code",
            "method": "GET",
            "url": "https://api.midtrans.com/v2/qris/0d8178e1-c6c7-4ab4-81a6-893be9d924ab/qr-code"
        }
    ],
    "qr_string": "00020101021226620014COM.GO-JEK.WWW0119936..."
}
```

### Display QR Code to Customer

Three options, in order of simplicity:

1. **Hotlink directly:** `<img src="https://api.midtrans.com/v2/qris/{transaction_id}/qr-code">` — no download needed, auth handled by Midtrans
2. **Download and display:** `GET` the URL from `actions[0].url`, serve as inline image
3. **Generate from `qr_string`:** Use a client-side QR library (qrcode.js, etc.) with the `qr_string` value

### QRIS Webhook / Notification

Midtrans sends HTTP POST to the configured notification URL (set via `X-Override-Notification` header or in dashboard). The QRIS notification JSON body:

```json
{
  "transaction_type": "on-us",
  "transaction_time": "2021-06-23 15:45:42",
  "transaction_status": "settlement",
  "transaction_id": "1015a919-b03f-450a-bc85-b38202a79a96",
  "status_message": "midtrans payment notification",
  "status_code": "200",
  "signature_key": "5d40504728eb96686bd5926299768a6496547f70dbd1e19d583ef4e780fe9dd5c...",
  "settlement_time": "2021-06-23 15:46:00",
  "payment_type": "qris",
  "order_id": "ORDER-001",
  "merchant_id": "G490526303",
  "issuer": "gopay",
  "gross_amount": "789000.00",
  "fraud_status": "accept",
  "currency": "IDR",
  "acquirer": "gopay"
}
```

**Status mapping for QRIS:**

| `transaction_status` | `fraud_status` | Meaning | Action |
|---|---|---|---|
| `settlement` | `accept` | **Paid** — success | Fulfill order |
| `pending` | `accept` | Waiting for customer to scan & pay | Wait |
| `expire` | `accept` | QR expired unpaid | Cancel order |
| `deny` / `cancel` | — | Rejected / cancelled | Cancel order |

### Signature Verification (Mandatory)

Always verify the `signature_key` before trusting the notification:
```
SHA512(order_id + status_code + gross_amount + server_key)
```
Compare against `signature_key` field. Mismatch = discard (not from Midtrans).

### Fallback: Get Transaction Status

If webhook fails to arrive, poll with:
```
GET /v2/{transaction_id}/status
```
Returns the same JSON body as notification. Recommended poll interval: 10s, max 30 attempts (5 min).

### Pitfall: QRIS `gross_amount` is a string in response

The response returns `"275000.00"` as a string, not a number. Parse it before using in calculations.

### Pitfall: `qr_string` may not be present on older API versions

The `qr_string` field was added later. Always check for presence; fall back to the `actions[0].url` QR image endpoint.

## GoPay Merchant Panel / GoBiz — Direct Integration (Zero Midtrans)

GoPay has its own merchant platform called **GoBiz**. The API (`api.gobiz.co.id`) gives merchants direct access to transaction history, real-time payment monitoring, and QRIS capabilities — without Midtrans as intermediary.

### Critical concept: Dynamic QRIS without an API call

This is the key insight. Unlike Midtrans (where you `POST /v2/charge` to get a QR code), GoPay dynamic QRIS is generated **client-side through string manipulation** — no API call needed at all.

**How it works:**
1. Merchant gets a **static QRIS string** from GoBiz dashboard (EMVCo format, starts `000201...`)
2. To make it dynamic: insert a `field 54` (amount) into the string, change the point-of-initiation flag from `010211` (static) to `010212` (dynamic), and recalculate the CRC16 checksum
3. Generate a QR code image from the resulting string using any QR library (`qrcode` npm package)

This is why the FB post claims "tidak butuh hosting/domain" — the entire QRIS generation runs in the browser.

```typescript
// Core algorithm (from gobiz-pay, MIT license)
function buildDynamicQris(staticQris: string, amount: number): string {
  // 1. Strip old CRC16 if present
  let rawBase = staticQris;
  if (staticQris.slice(-8, -4) === "6304") {
    rawBase = staticQris.slice(0, -4);
  }
  // 2. Change static flag (010211) → dynamic flag (010212)
  const step1 = rawBase.replace("010211", "010212");
  // 3. Split at "5802ID" (country code marker)
  const [before, after] = step1.split("5802ID");
  // 4. Insert field 54: "54" + (len of amount as 2 digits) + amount
  const nominalField = "54" + String(amount.toString().length).padStart(2, "0") + amount;
  // 5. Reassemble + recalculate CRC16
  let crcPayload = before + nominalField + "5802ID" + after;
  if (!crcPayload.endsWith("6304")) crcPayload += "6304";
  return crcPayload + convertCRC16(crcPayload);
}
```

### GoBiz API — Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `api.gobiz.co.id/goid/login/request` | POST | Initiate login (email + password) |
| `api.gobiz.co.id/goid/token` | POST | Get access token (password or OTP grant) |
| `api.gobiz.co.id/v1/users/me` | GET | Get merchant ID and profile |
| `api.gojekapi.com/merchant-analytics/v2/merchants/transactions` | GET | Transaction history (analytics view) |
| `api.gobiz.co.id/journals/search` | POST | Detailed transaction journal (Elasticsearch query DSL) |

### Auth flow

```typescript
// Step 1: request login
POST api.gobiz.co.id/goid/login/request
Body: { email, login_type: "password", client_id: "go-biz-web-new" }

// Step 2: exchange for token
POST api.gobiz.co.id/goid/token
Body: { client_id: "go-biz-web-new", grant_type: "password", data: { email, password } }
Response: { access_token, refresh_token, expires_in }

// All subsequent requests use: Authorization: Bearer <access_token>
// Required headers (mimic GoBiz web dashboard):
//   x-appid: go-biz-web-dashboard
//   x-uniqueid: <random UUID>
//   x-user-type: merchant
//   gojek-country-code: ID
```

### Payment monitoring (polling, not webhook)

GoBiz has **no push webhook**. You poll for incoming payments:

```typescript
import { getGoPayWatcher } from 'gobiz-pay';

const watcher = getGoPayWatcher();
const payment = await watcher.waitForPayment(50000, {
  timeout: 300_000,    // 5 minutes
  tolerance: 100,      // tolerate Rp 100 difference
});
// Returns: { txId, amount, entry }
```

The watcher polls `getTransactionsAnalytics()` at intervals, comparing incoming settlements against the expected amount.

### Transaction history

```typescript
const merchant = new GoPayMerchant();
await merchant.init();  // auto-login with cached token
const history = await merchant.getHistory({ days: 7, size: 50 });
// Returns: { status, data: { histories: [{ type, amount, time, raw }] } }
```

### Open-source library: gobiz-pay (MIT)

[github.com/ItsAzni/gobiz-pay](https://github.com/ItsAzni/gobiz-pay) — MIT-licensed TypeScript SDK covering all the above. Install: `npm install gobiz-pay`. Requires Node.js >= 18.

Companion commercial CLI (same API, more features): [IbraDecode/gopaymerchant](https://github.com/IbraDecode/gopaymerchant) — adds paylink, refund, webhook server, CLI interface. Source code sold separately.

### When to use GoBiz vs Midtrans

| | **GoBiz (direct)** | **Midtrans** |
|---|---|---|
| **QRIS generation** | String manipulation (client-side, no API) | POST /v2/charge (server-side API) |
| **Setup** | GoBiz merchant account + QRIS static string | Midtrans dashboard + KYC + activation |
| **Acquirers** | GoPay only | GoPay + ShopeePay + all QRIS issuers |
| **Fee** | Only MDR QRIS (0.3%) | + Midtrans markup (~0.7-1% total) |
| **Webhook** | None (polling only) | HTTP POST with SHA512 signature |
| **Refund** | Via GoBiz dashboard (no API in SDK) | API: POST /v2/{id}/refund |
| **Best for** | Micro-business, POS, offline + QR | E-commerce, SaaS, automated flows |

See `references/gobiz-gopay-merchant-api.md` for full API endpoint details, auth headers, and the QRIS string manipulation spec.

## Voucher / Discount System Patterns

### DB-backed vouchers (replaces hardcoded)

Hardcoded vouchers in source code become a deployment bottleneck — can't add/edit/disable without redeploy, no usage tracking, no per-user limits. Move to database with `Voucher` + `VoucherUsage` models.

**Prisma schema:**
```prisma
model Voucher {
  id              String          @id @default(cuid())
  code            String          @unique
  discountType    String          // "percent" | "free_ship"
  discountPercent Int             @default(0)
  description     String
  minPurchase     Int?
  maxUses         Int?
  usedCount       Int             @default(0)
  active          Boolean         @default(true)
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt
  usages          VoucherUsage[]
}

model VoucherUsage {
  id        String   @id @default(cuid())
  voucherId String
  voucher   Voucher  @relation(fields: [voucherId], references: [id])
  orderId   String
  userId    String?
  createdAt DateTime @default(now())

  @@unique([voucherId, orderId])   // prevent double-apply on same order
  @@unique([voucherId, userId])    // per-user limit (NULLs = distinct in SQLite = guest bypass)
}
```

**Validator — async, reads from DB:**
```typescript
// src/lib/server/voucher.ts
export async function validateVoucher(code: string, subtotal: number, userId?: string | null): Promise<VoucherResult | null> {
  const voucher = await prisma.voucher.findUnique({ where: { code: code.toUpperCase() } })
  if (!voucher || !voucher.active) return null
  if (voucher.minPurchase && subtotal < voucher.minPurchase) return null
  if (voucher.maxUses && voucher.usedCount >= voucher.maxUses) return null

  // Per-user: one use per logged-in user
  if (userId) {
    const existing = await prisma.voucherUsage.findFirst({ where: { voucherId: voucher.id, userId } })
    if (existing) return null
  }

  if (voucher.discountType === 'free_ship') {
    return { valid: true, code: voucher.code, discountType: 'free_ship', discountPercent: 0, description: voucher.description, discountAmount: 0 }
  }
  return { valid: true, code: voucher.code, discountType: 'percent', discountPercent: voucher.discountPercent, description: voucher.description, discountAmount: Math.round(subtotal * voucher.discountPercent / 100) }
}
```

**Record usage after order creation (non-critical — don't fail the order):**
```typescript
export async function recordVoucherUsage(voucherCode: string, orderId: string, userId?: string | null) {
  try {
    const voucher = await prisma.voucher.findUnique({ where: { code: voucherCode.toUpperCase() } })
    if (!voucher) return
    await prisma.$transaction([
      prisma.voucherUsage.create({ data: { voucherId: voucher.id, orderId, userId: userId || null } }),
      prisma.voucher.update({ where: { id: voucher.id }, data: { usedCount: { increment: 1 } } })
    ])
  } catch (e) { console.error('[voucher] usage record failed:', e) }
}
```

**Checkout integration — call after order creation:**
```typescript
// In checkout action: const voucher = await validateVoucher(voucherCode, subtotal, userId)
// After prisma.$transaction creates the order:
if (voucherCode) {
  recordVoucherUsage(voucherCode, orderId, userId)  // fire-and-forget, non-blocking
}
```

**Seeding existing vouchers into production DB:**
```typescript
// Run inside Docker container after migration with PrismaBetterSqlite3 adapter
// Prisma v7+ REQUIRES the adapter — new PrismaClient() without it throws PrismaClientConstructorValidationError
import { PrismaClient } from '@prisma/client'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

const p = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: 'file:/data/dev.db' }) })

const vouchers = [
  { code: 'WELCOME10', discountType: 'percent', discountPercent: 10, description: 'Diskon 10%', active: true },
  { code: 'FREESHIP', discountType: 'free_ship', discountPercent: 0, description: 'Gratis Ongkir', active: true },
]
for (const v of vouchers) {
  await p.voucher.upsert({ where: { code: v.code }, update: v, create: v })
}
```

### Pitfall: Per-user constraint with guest orders

The `@@unique([voucherId, userId])` constraint allows guests to reuse vouchers because SQLite treats NULLs as distinct. For guest users, enforce at application level or accept the limitation for MVP.

### Client-Side Voucher UX Flow (Cross-Page Persistence)

The database-backed voucher system above handles **server-side** validation. But the **client-side** UX must carry the voucher code and discount preview across three pages: product → cart → checkout. The pipeline is:

```
Product page → API validation → localStorage persistence
     ↓
Cart page → reads localStorage → shows discount in total
     ↓
Checkout page → reads localStorage → re-validates → shows discount → form submits voucher code → server authoritative validation
```

#### Step 1: API endpoint for client-side validation

Create `POST /api/voucher/validate` so the client can preview discount before checkout:

```typescript
// src/routes/api/voucher/validate/+server.ts
import { json } from '@sveltejs/kit'
import { validateVoucher } from '$lib/server/voucher'

export const POST: RequestHandler = async ({ request, locals }) => {
  const { code, subtotal } = await request.json()
  if (!code || !subtotal) return json({ valid: false, error: 'Kode dan subtotal diperlukan' }, { status: 400 })
  const result = await validateVoucher(code.trim(), parseInt(String(subtotal)) || 0, locals.user?.id || null)
  if (!result) return json({ valid: false, error: 'Kode voucher tidak valid atau tidak memenuhi syarat' })
  return json(result)
}
```

#### Step 2: Product page — validate + store in localStorage

Replace any dummy voucher input (that only sets `voucherApplied = true` locally) with a real one:

```svelte
<script>
  let voucherCode = $state('')
  let voucherLoading = $state(false)
  let voucherError = $state('')
  let voucherData = $state<{ code: string; discountType: string; discountPercent: number; discountAmount: number; description: string } | null>(null)

  // Load saved voucher from localStorage on mount (recovery from page reload)
  $effect(() => {
    try {
      const saved = localStorage.getItem('iki_voucher')
      if (saved) {
        const parsed = JSON.parse(saved)
        voucherCode = parsed.code || ''
        voucherData = parsed
      }
    } catch (_) {}
  })

  async function applyVoucher() {
    if (!voucherCode.trim()) return
    voucherLoading = true
    voucherError = ''
    try {
      const res = await fetch('/api/voucher/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: voucherCode.trim(), subtotal: data.product.price })
      })
      const json = await res.json()
      if (json.valid) {
        voucherData = json
        localStorage.setItem('iki_voucher', JSON.stringify(json))  // persist for cart/checkout
      } else {
        voucherError = json.error || 'Kode voucher tidak valid'
        voucherData = null
      }
    } catch { voucherError = 'Gagal validasi voucher' }
    voucherLoading = false
  }

  function removeVoucher() {
    voucherCode = ''
    voucherData = null
    voucherError = ''
    localStorage.removeItem('iki_voucher')
  }
</script>

<!-- Template: show discount preview when voucher is valid -->
{#if voucherData}
  <div class="mt-2 p-2 bg-green-50 rounded border border-green-200">
    <p>✓ Voucher <strong>{voucherData.code}</strong> — {voucherData.description}</p>
    {#if voucherData.discountType === 'percent'}
      <p>Diskon {voucherData.discountPercent}% — Hemat {formatPrice(voucherData.discountAmount)}</p>
      <p class="font-bold">Harga setelah diskon: {formatPrice(data.product.price - voucherData.discountAmount)}</p>
    {:else if voucherData.discountType === 'free_ship'}
      <p>🚚 Gratis ongkos kirim!</p>
    {/if}
    <button onclick={removeVoucher} class="text-red-500 hover:underline">Hapus voucher</button>
  </div>
{/if}
```

#### Step 3: Cart page — read from localStorage, show discount

```svelte
<script>
  let voucherCode = $state('')
  let voucherData = $state<... | null>(null)
  let voucherDiscount = $derived(voucherData?.discountAmount ?? 0)

  let subtotal = $derived(data.items.reduce((sum, it) => sum + it.product.price * it.quantity, 0))
  let total = $derived(Math.max(0, subtotal - voucherDiscount))

  // Load from localStorage on mount
  $effect(() => {
    try {
      const saved = localStorage.getItem('iki_voucher')
      if (saved) {
        const parsed = JSON.parse(saved)
        voucherCode = parsed.code || ''
        voucherData = parsed
      }
    } catch (_) {}
  })
</script>

<!-- Show voucher discount line item in total breakdown -->
<div class="flex justify-between text-sm text-stone"><span>Subtotal</span><span>{formatPrice(subtotal)}</span></div>
{#if voucherDiscount > 0}
  <div class="flex justify-between text-sm text-green-600"><span>Diskon Voucher</span><span>-{formatPrice(voucherDiscount)}</span></div>
{/if}
<div class="flex justify-between text-lg font-bold"><span>Total</span><span>{formatPrice(total)}</span></div>
```

#### Step 4: Checkout page — prefill + re-validate + pass to server

```svelte
<!-- Voucher input inside checkout form — name="voucher" submits to server -->
<div class="p-3 bg-ivory rounded-lg border border-dashed border-terracotta/30">
  <p class="text-sm font-medium">Kode Voucher</p>
  <div class="flex gap-2">
    <input type="text" bind:value={voucherCode} name="voucher" placeholder="Masukkan kode" />
    {#if voucherData}
      <button type="button" onclick={removeCheckoutVoucher}>Hapus</button>
    {:else}
      <button type="button" onclick={applyCheckoutVoucher}>Pakai</button>
    {/if}
  </div>
  {#if voucherData}
    <p class="text-green-600">✓ <strong>{voucherData.code}</strong> — {voucherData.description}</p>
  {/if}
</div>
```

The checkout server already reads `voucher` from `formData` and re-validates via `validateVoucher()` — this is the authoritative validation. The client-side API call is purely for UX preview.

#### Pitfall: dummy voucher input on product page

A voucher input that only sets `voucherApplied = true` locally (no API call, no localStorage, no discount calculation) creates a broken experience:
- User sees "Voucher applied ✓" but the price never changes
- Voucher code is lost when navigating to cart/checkout
- No discount is shown anywhere

The input is purely decorative and creates false expectations. Either remove it or implement the full pipeline above.

#### Pitfall: re-validate on checkout because subtotal changes

The `discountAmount` computed on the product page is for a single product. On checkout, the subtotal is the sum of all cart items. Always re-validate the voucher against the checkout subtotal — the saved `discountAmount` from the product page will be wrong.

```typescript
// In checkout $effect — re-validate against actual subtotal
$effect(() => {
  const saved = localStorage.getItem('iki_voucher')
  if (saved) {
    const parsed = JSON.parse(saved)
    fetch('/api/voucher/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: parsed.code, subtotal })  // subtotal = checkout subtotal
    }).then(r => r.json()).then(json => {
      if (json.valid) voucherData = json
      else { voucherData = null; localStorage.removeItem('iki_voucher') }
    })
  }
})
```

#### Pitfall: free_ship vouchers show discountAmount = 0 on client

`validateVoucher` returns `discountAmount: 0` for `free_ship` vouchers because the shipping cost isn't known until the user selects courier on checkout. The client should show "🚚 Gratis Ongkir" text for `discountType === 'free_ship'` and NOT try to subtract from total. The server-side checkout action handles zeroing `shippingCost` when a `free_ship` voucher is applied.

### Buy Now / Beli Langsung Pattern

Indonesian storefronts benefit from a "Beli Langsung" (Buy Now) button on the product detail page alongside "Tambah ke Keranjang" (Add to Cart). This lets users skip the cart entirely and go straight to checkout for impulse purchases.

#### Implementation: add-to-cart via fetch + redirect

```svelte
<script>
  let buyingNow = $state(false)

  async function buyNow() {
    buyingNow = true
    try {
      // Add to cart via fetch (same form action as "Tambah ke Keranjang")
      const formData = new FormData()
      formData.append('productId', data.product.id)
      formData.append('quantity', String(quantity))
      const res = await fetch('/cart?/add', { method: 'POST', body: formData })
      if (res.ok || res.redirected) {
        sessionStorage.setItem('iki_direct_checkout', '1')
        window.location.href = '/checkout'
      }
    } catch {
      buyingNow = false
    }
  }
</script>

<!-- Two buttons side by side -->
<div class="flex gap-2 sm:gap-3">
  <button type="submit" class="flex-1 bg-charcoal text-white ...">Tambah ke Keranjang</button>
  <button type="button" onclick={buyNow} disabled={buyingNow || product.stock === 0}
    class="bg-terracotta text-white ...">
    {buyingNow ? '...' : 'Beli Langsung'}
  </button>
</div>
```

#### Why fetch + redirect instead of separate endpoint

Adding a dedicated "buy now" API endpoint introduces complexity: it must create a cart item, then create an order, then redirect — duplicating checkout logic. The fetch-to-cart-then-redirect approach reuses the existing cart infrastructure and checkout flow. The `sessionStorage` flag `iki_direct_checkout` can be read by checkout server to differentiate the source if needed.

#### Pitfall: the fetch must NOT use `use:enhance`

`use:enhance` is for SvelteKit form actions and processes redirects via `applyAction()`. For `buyNow()`, use raw `fetch()` + `window.location.href` — the server redirect from the form action doesn't matter because we're navigating manually after the fetch completes.

### Type discrimination (still applies as before)

Don't model "free shipping" as `discountPercent: 0` — it reads as "Rp 0 discount" and the shipping cost is never zeroed. Use `discountType` field: `'percent'` | `'free_ship'`.

### Pitfall: `shippingCost` must be `let`, not `const`

When using Zod for checkout validation, `z.coerce.number()` produces a `number`. But FREESHIP voucher mutates `shippingCost`, so destructure into a temp alias then assign to a `let`:
```typescript
const { shipping_cost: _shippingCost } = parsed.data
let shippingCost = _shippingCost  // mutable for free_ship
```

### Pitfall: `minPurchase` validation should compare subtotal, not total

Check `minPurchase` against the subtotal (before shipping/voucher). Otherwise a free-ship voucher combined with `minPurchase` can be bypassed.

## Stock Restore on Failed/Cancelled Payment

When a payment fails, expires, or is refunded, stock that was decremented at checkout must be restored. This is critical — without it, stock permanently shrinks on every failed checkout attempt.

### Prerequisite: `productId` on OrderItem

The `OrderItem` model MUST have a `productId` field to reliably restore stock:

```prisma
model OrderItem {
  id          String  @id @default(cuid())
  orderId     String
  order       Order   @relation(fields: [orderId], references: [id], onDelete: Cascade)
  productId   String?          // ← ADD THIS for stock restore
  productName String
  price       Int
  quantity    Int
  variant     String?
}
```

Use `prisma db push` for migration (no migration file needed for Dockerized SQLite).

### Store `productId` during checkout

```typescript
// In checkout page.server.ts, when creating order items:
items: {
  create: items.map(i => ({
    productId: i.productId,    // ← store for later restore
    productName: i.product.name,
    price: i.product.price,
    quantity: i.quantity
  }))
}
```

### Restore stock in webhook handler

```typescript
// src/routes/api/midtrans/webhook/+server.ts
if (paymentStatus === 'failed' || paymentStatus === 'refunded') {
  const items = await prisma.orderItem.findMany({
    where: { orderId },
    select: { productId: true, productName: true, quantity: true }
  })
  for (const item of items) {
    if (item.productId) {
      await prisma.product.update({
        where: { id: item.productId },
        data: { stock: { increment: item.quantity } }
      })
    } else {
      // Legacy: match by name (fallback for old orders without productId)
      const product = await prisma.product.findFirst({ where: { name: item.productName } })
      if (product) {
        await prisma.product.update({
          where: { id: product.id },
          data: { stock: { increment: item.quantity } }
        })
      }
    }
  }
}
```

### Also restore in status polling endpoint

The webhook may not arrive in time (or at all in sandbox). Also add stock restore in `/api/order/[id]/status` when polling detects payment failure:

```typescript
// In status polling handler, after detecting failed payment:
if (mapped.paymentStatus === 'failed' || mapped.paymentStatus === 'refunded') {
  await restoreStock(order.id)  // same logic as webhook
}
```

### Pitfall: matching by productName is unreliable

Without `productId`, the only way to find the product is `findFirst({ where: { name: item.productName } })`. This breaks if:
1. Multiple products share the same name
2. Product name was changed after the order was placed
3. Product was deleted

Always store `productId` at checkout time. The `productName` match is a fallback for legacy orders.

### Auto-Cancel Expired Orders (Cron Job)

Orders left in `pending` payment status forever cause "ghost stock" — inventory is decremented but never reclaimed. Midtrans sends `expire` webhook when a payment times out, but webhooks can fail. Add a cron job as defense-in-depth.

**Schema — add `expiresAt` to Order:**
```prisma
model Order {
  // ... existing fields ...
  expiresAt  DateTime?  // set to now() + 24h at checkout
}
```

**Set during checkout:**
```typescript
// In checkout action, when creating the order:
data: {
  // ... other fields ...
  expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000), // 24 hours
}
```

**API endpoint — `GET /api/cron/cancel-expired`:**
```typescript
// Finds all pending orders past expiresAt, cancels them, restores stock
export const GET: RequestHandler = async () => {
  const now = new Date()
  const expired = await prisma.order.findMany({
    where: { paymentStatus: 'pending', expiresAt: { not: null, lt: now } },
    select: { id: true }
  })

  let cancelled = 0
  for (const order of expired) {
    await prisma.order.update({
      where: { id: order.id },
      data: { paymentStatus: 'failed', status: 'cancelled' }
    })
    // Restore stock using same logic as webhook handler
    await restoreStock(order.id)
    cancelled++
  }
  return json({ cancelled, timestamp: now.toISOString() })
}
```

**Cron job — `no_agent` shell script every 15 min:**
```bash
#!/bin/bash
curl -sf "https://domain.com/api/cron/cancel-expired"
```

Use Hermes cron with `no_agent=true` and `script=cancel-expired-orders.sh` to run without LLM token cost.

**Pitfall: Don't rely on webhook alone for expiry.** Midtrans webhook can fail (network, downtime, misconfiguration). The cron job is the safety net — it catches orders that the webhook missed.

## Midtrans Sandbox — Testing Payment Methods

After redirect to Midtrans sandbox page, there's no obvious "Simulate Payment" button. Each payment method has a separate simulator:

## Production Deployment Lessons

See `references/pitfalls-production.md` for real-world deployment lessons covering RajaOngkir blocking, Biteship migration, tracking honesty, rate limiting, centralized config, Docker optimization, and email receipts.

## Midtrans Sandbox — Testing Payment Methods

| Method | Simulator URL | Notes |
|--------|--------------|-------|
| **QRIS / GoPay / ShopeePay** | `https://simulator.sandbox.midtrans.com/qris/index` | Click Pay → auto-success |
| **BCA VA** | `https://simulator.sandbox.midtrans.com/bca/va/index` | Enter VA number → Pay |
| **BNI VA** | `https://simulator.sandbox.midtrans.com/bni/va/index` | Enter VA number → Pay |
| **BRI VA** | `https://simulator.sandbox.midtrans.com/bri/va/index` | Enter VA number → Pay |
| **Mandiri VA** | `https://simulator.sandbox.midtrans.com/mandiri/bill/index` | Enter VA number → Pay |
| **Indomaret / Alfamart** | `https://simulator.sandbox.midtrans.com/alfamart/index` | Enter code → Pay |
| **Credit Card** | Use test card directly | `4811 1111 1111 1114` / `01/30` / `123` |

**Easiest test path:** Choose QRIS at the Midtrans page → click Pay → open simulator URL in new tab → click Pay → done. Webhook arrives within seconds.

After payment, Midtrans sends webhook to `https://yourdomain.com/api/midtrans/webhook` (configured in Midtrans dashboard under Settings > Payment Notification).

## Order History & Guest Lookup — \"Lupa Bayar\" Recovery

### The problem

After checkout, the user is redirected to Midtrans. If they close the browser before paying, the order URL is lost. Without login, there's no way to find the order. Even logged-in users need a simple way to see pending payments.

### Three-layer solution

| Layer | Path | Who | Purpose |
|-------|------|-----|---------|
| **localStorage** | (order page JS) | All users | Silently saves last 5 order IDs when user visits order page |
| **Guest lookup** | `/orders` | Guests | Search by order ID / name / phone |
| **My Orders** | `/account` & `/account/orders` | Logged-in | Full order history with payment status |

### Layer 1: localStorage on order page

```svelte
<!-- src/routes/order/[id]/+page.svelte -->
<script>
  onMount(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('iki_recent_orders') || '[]')
      if (!saved.includes(order.id)) {
        saved.unshift(order.id)
        localStorage.setItem('iki_recent_orders', JSON.stringify(saved.slice(0, 5)))
      }
    } catch (_) { /* ignore */ }
    // ... tracking + polling ...
  })
</script>
```

### Layer 2: Guest lookup API + page

API endpoint `GET /api/order/lookup?q=...` — searches by:
- Order ID prefix (8+ chars) → exact match
- Name / phone (3+ chars) → contains match

Returns at most 5 orders (no payment details, just ID/total/status). No auth required for guests.

```typescript
// src/routes/api/order/lookup/+server.ts
export const GET: RequestHandler = async ({ url }) => {
  const q = url.searchParams.get('q')
  if (!q || q.length < 3) throw error(400, 'Minimal 3 karakter')

  const query = q.trim()
  // Try order ID first (prefix match)
  if (query.length >= 8) {
    const orders = await prisma.order.findMany({
      where: { id: { startsWith: query } },
      select: { id: true, total: true, status: true, paymentStatus: true, shippingName: true, createdAt: true },
      take: 5, orderBy: { createdAt: 'desc' }
    })
    if (orders.length > 0) return json({ orders })
  }
  // Fallback to name/phone match
  const orders = await prisma.order.findMany({
    where: {
      OR: [{ shippingName: { contains: query } }, { shippingPhone: { contains: query } }]
    },
    select: { id: true, total: true, status: true, paymentStatus: true, shippingName: true, createdAt: true },
    take: 5, orderBy: { createdAt: 'desc' }
  })
  return json({ orders })
}
```

The UI page at `/orders` is a simple search form — renders matching orders as cards with payment status badges. Link added to navbar ("Cek Pesanan") and footer.

### Layer 3: My Orders for logged-in users

Server load at `/account/+page.server.ts` already fetches user's orders. Augment the template to show payment status badges prominently:

```svelte
{#if order.paymentStatus === 'pending'}
  <span class="bg-yellow-100 text-yellow-700 rounded">Menunggu Bayar</span>
{:else if order.paymentStatus === 'paid'}
  <span class="bg-green-100 text-green-700 rounded">Lunas</span>
```

Also add a dedicated `/account/orders` page showing all orders with infinite scroll for power users.

### Pitfall: hardcoding order page URL after checkout

Don't rely on the user bookmarking the order page. The redirect-to-Midtrans flow means the browser history may not include the order URL. Always combine all three layers — localStorage saves the URL silently even if the user doesn't realize it.

### Navbar placement

"**Cek Pesanan**" link goes in the main nav (between "Tentang" and the cart icon). For mobile, add it before "Kontak" in the hamburger menu. Users intuitively look for a way to track orders — make it visible even when logged out.

## Komerce Payment — Frontend Rendering

After creating a payment server-side, the response contains `va_number`, `bank_code`, `bank_name`, `payment_url`, `qr_string`. Do NOT show only generic "Waiting for Payment" — render the actual VA number with a payment button.

### Server: pass `paymentDetails` to page

```ts
let paymentDetails = null
if (order.paymentRef && order.paymentStatus === 'pending') {
  try { paymentDetails = await getPaymentStatus(order.paymentRef) }
  catch (e) { /* ignore — fresh order */ }
}
return { order, paymentError, paymentDetails }
```

### Client: render VA + payment button

```svelte
<script lang="ts">
  let paymentDetails = data.paymentDetails
  function openPayment() {
    if (paymentDetails?.paymentUrl) window.open(paymentDetails.paymentUrl, '_blank')
  }
</script>

{#if order.paymentStatus === 'pending'}
  <div class="border border-yellow-200 bg-yellow-50 rounded-lg p-6">
    {#if paymentDetails?.vaNumber}
      <p class="text-xs uppercase">{paymentDetails.bankName}</p>
      <p class="text-lg font-mono font-bold tracking-wider">{paymentDetails.vaNumber}</p>
    {/if}
    {#if paymentDetails?.qrString}
      <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encodeURIComponent(paymentDetails.qrString)}" alt="QRIS" />
    {/if}
    {#if paymentDetails?.paymentUrl}
      <button onclick={openPayment} class="w-full bg-terracotta text-white py-3 rounded">
        Bayar Sekarang
      </button>
    {:else}
      <p>Pembayaran akan terverifikasi otomatis via Midtrans.</p>
    {/if}
  </div>
{/if}
```

### Pitfall: `paymentDetails` fetched but never rendered

Server returns `paymentDetails` in load, but `+page.svelte` ignores it. Always verify:
1. `let paymentDetails = data.paymentDetails` in script
2. Template renders `vaNumber`, `bankName`, `qrString`, `paymentUrl`
3. Fallback to generic text when no details exist

### Payment status polling (10s × 30 = 5 min)

```svelte
onMount(() => {
  let n = 0
  if (order.paymentStatus === 'pending') {
    const iv = setInterval(async () => {
      if (++n > 30) { clearInterval(iv); return }
      const r = await fetch(`/api/order/${order.id}/status`)
      if (r.ok) {
        const d = await r.json()
        if (d.paymentStatus !== 'pending') {
          order.paymentStatus = d.paymentStatus; order.status = d.status; clearInterval(iv)
        }
      }
    }, 10000)
    return () => clearInterval(iv)
  }
})
```

## SvelteKit 2.x `redirect()` is NOT `instanceof Response`

In SvelteKit 2.x (v2.69+), `throw redirect(302, '/path')` throws a `Redirect` instance (extends `Error`, NOT `Response`). A catch block checking `e instanceof Response` will NOT re-throw it.

### Symptom

Order page URL shows `?payment_error=1` instead of `?payment=created`, even though payment API call succeeded. Docker logs show:

```
[checkout] Komerce payment error: Redirect { location: '/order/...?payment=created' }
```

### Fix

```ts
// BEFORE (broken in SvelteKit 2.x):
if (e instanceof Response) throw e

// AFTER:
if (e instanceof Response || (e?.status && e?.location)) throw e
```

## RajaOngkir Tracking API — Live Shipment Tracking

When tracking fields exist on an order (`trackingNumber` + `trackingCourier`), use RajaOngkir's live tracking API instead of just linking to courier websites. Same API key as shipping cost.

### Endpoint

```
POST https://rajaongkir.komerce.id/api/v1/track/waybill
```

### Auth

Same `key: YOUR_KEY` header as shipping cost endpoints.

### Request

Form-encoded body (NOT JSON):
- `awb` — tracking/waybill number (REQUIRED)
- `courier` — courier code (`jne`, `tiki`, `pos`, `sicepat`, `jnt`, `anteraja`, `lion`, etc.)

```bash
curl -X POST https://rajaongkir.komerce.id/api/v1/track/waybill \
  -H "key: YOUR_KEY" \
  -d "awb=JP0123456789&courier=jne"
```

### Response (valid AWB)

```json
{
  "meta": { "message": "Success", "code": 200, "status": "success" },
  "data": {
    "awb": "JP0123456789",
    "courier": "jne",
    "service": "REG",
    "status": "ON DELIVERY",
    "manifest": [
      {
        "date": "2025-01-15",
        "time": "14:30",
        "desc": "Paket sedang dalam perjalanan",
        "location": "JAKARTA"
      }
    ]
  }
}
```

### Critical pitfalls

1. **Field name is `awb`, NOT `waybill`** — The URL path is `/track/waybill` but the form field is `awb`. Using `waybill` as the body field returns 422: `"Field validation for 'Awb' failed on the 'required' tag"`.

2. **Form-encoded only** — JSON body returns 404. Always use `Content-Type: application/x-www-form-urlencoded`.

3. **History field may be `manifest` or `history`** — The response array key varies. Map both: `d.history || d.manifest || []`.

### Recommended architecture

Do NOT call RajaOngkir tracking API directly from the browser. Create a thin server-side proxy endpoint (`/api/order/[id]/tracking`) that:
1. Reads order ownership from DB (userId check)
2. Reads `trackingNumber` + `trackingCourier` from DB
3. Calls `trackWaybill()` server-side
4. Returns sanitized JSON to the frontend

This keeps the API key server-side and adds ownership verification.

Frontend fetches the proxy endpoint in `onMount()` and renders a timeline of events. Keep a fallback link to the courier's website for cases where the API fails.

### Full integration pattern

See `references/rajaongkir-tracking-api.md` for complete code: server lib function, proxy endpoint, SvelteKit frontend with live tracking timeline.

### Tracking API caching — avoid burning API quota

The order page auto-fetches tracking on every load. Each fetch calls RajaOngkir's rate-limited API. Add a simple in-memory cache:

```typescript
const cache = new Map<string, { data: any; ts: number }>()
const CACHE_TTL = 5 * 60 * 1000  // 5 min
const MAX_ENTRIES = 100

function getCached(key: string) {
  const entry = cache.get(key)
  if (!entry || Date.now() - entry.ts > CACHE_TTL) {
    cache.delete(key)
    return null
  }
  return entry.data
}

function setCache(key: string, data: any) {
  if (cache.size >= MAX_ENTRIES) {
    const oldest = cache.keys().next().value
    if (oldest) cache.delete(oldest)
  }
  cache.set(key, { data, ts: Date.now() })
}
```

Key: `tracking:${orderId}:${trackingNumber}`. This caps at 100 unique orders cached simultaneously, 5 min TTL per entry — sufficient for low-to-mid traffic storefronts. Redis is overkill unless concurrent pod scaling.

### Auth policy for guest orders

Guest orders (no `userId`) allow anyone with the order ID to view tracking. This is intentional — customers placing orders without accounts need to track their package. Tracking data is non-sensitive (shipment status only, no payment or personal info beyond name/address which is already visible on the order page).

If you need stricter access, add a `trackingToken` column to orders (random UUID) and require `?token=<redacted>` on the tracking API endpoint.

### Tracking Simulation — Mock Events When API Is Down

When Biteship or RajaOngkir tracking API is unavailable (no API key, no balance, network error), generate realistic mock tracking events based on order status. This keeps the tracking UI functional for demos and development without external API dependency.

**Enhanced version (recommended):** See the "Enhanced Mock Tracking Generator" section below for richer events with `progressPercent`, separate `confirmed` status, 4-event `delivered` timeline, and Semarang transit hub. The pattern below is the minimal version.

#### Core pattern: `generateMockTracking()` function (minimal)

```typescript
function generateMockTracking(order: {
  id: string; status: string; trackingNumber: string;
  trackingCourier: string; createdAt: Date; shippingCity: string
}) {
  const courier = (order.trackingCourier || 'jne').toUpperCase()
  const resi = order.trackingNumber || 'SIM' + order.id.slice(0, 8)
  const city = order.shippingCity || 'Jakarta'
  const now = new Date()

  function d(daysAgo: number) {
    const dt = new Date(now.getTime() - daysAgo * 86400000)
    dt.setHours(8 + Math.floor(Math.random() * 10), Math.floor(Math.random() * 60))
    return { date: dt.toISOString().split('T')[0], time: dt.toTimeString().slice(0, 8) }
  }

  const events = []
  if (order.status === 'shipped') {
    events.push(
      { ...d(2), desc: `Paket diterima oleh ${courier}`, location: `Jepara - Drop Point ${courier}` },
      { ...d(1), desc: `Paket dalam perjalanan ke ${city}`, location: `Hub ${courier}` },
    )
  } else if (order.status === 'delivered') {
    events.push(
      { ...d(3), desc: `Paket diterima oleh ${courier}`, location: `Jepara - Drop Point ${courier}` },
      { ...d(1), desc: `Paket dalam perjalanan ke ${city}`, location: `Hub ${courier}` },
      { ...d(0.2), desc: `Paket telah diterima oleh penerima`, location: city },
    )
  } else if (order.status === 'processing' || order.status === 'confirmed') {
    events.push({ ...d(0.5), desc: 'Pesanan sedang diproses oleh penjual', location: 'Jepara - the client site' })
  } else {
    events.push({ ...d(0.1), desc: 'Menunggu konfirmasi pembayaran', location: 'Sistem' })
  }

  return { courier, awb: resi, status: order.status, origin: 'Jepara, Jawa Tengah', destination: city, events, _simulated: true }
}
```

#### Tracking endpoint: real first, mock fallback

```typescript
// GET /api/order/[id]/tracking
export const GET: RequestHandler = async ({ params, locals }) => {
  const order = await prisma.order.findUnique({ where: { id: params.id }, select: { ... } })
  if (!order) return json({ error: 'Not found' }, { status: 404 })
  if (!order.trackingNumber || !order.trackingCourier) return json({ error: 'No tracking' }, { status: 404 })

  // Check cache
  const cached = getCached(`tracking:${order.id}:${order.trackingNumber}`)
  if (cached) return json(cached)

  // Try real API first
  try {
    const tracking = await trackShipment(order.trackingNumber, order.trackingCourier)
    const result = { ...tracking, trackingUrl: getCourierTrackingUrl(order.trackingCourier, order.trackingNumber) }
    setCache(cacheKey, result)
    return json(result)
  } catch (_) {
    // Fall through to simulation
  }

  // Mock fallback
  const mock = generateMockTracking(order)
  const result = { ...mock, trackingUrl: getCourierTrackingUrl(order.trackingCourier, order.trackingNumber) }
  setCache(cacheKey, result)
  return json(result)
}
```

#### `_simulated` flag — REMOVED (anti-pattern)

**Do NOT use `_simulated: true` or `generateMockTracking()`.** Generating fake tracking events misleads customers and erodes trust. The old approach used `_simulated: true` with mock events; this has been deprecated in favor of honest fallback.

When real courier tracking (Biteship) is unavailable, return:
```json
{
  "courier": "JNE",
  "awb": "1234567890",
  "status": "shipped",
  "events": [],
  "trackingUrl": "https://www.jne.co.id/tracking/waybill/1234567890",
  "message": "Lacak langsung melalui halaman ekspedisi."
}
```

This provides the courier's own tracking page URL — the customer gets real data directly from the source.

```svelte
{#if tracking?._simulated}
  <div class="bg-blue-50 border border-blue-200 rounded text-blue-700 text-xs px-3 py-1.5">
    🔬 Mode Simulasi — data tracking adalah contoh. Tracking real akan aktif dengan Biteship API.
  </div>
{/if}
```

#### Pitfall: caching returns stale simulation after status changes

The cache key `tracking:${orderId}:${trackingNumber}` doesn't include order status. When admin updates status (e.g., `processing` → `shipped`), cached mock events remain stale. Either include status in the cache key or keep TTL short (5 min). For production, prefer real API over simulation — the cache will auto-expire.

### Admin Tracking Input — Dropdown + Auto-Fill

The admin order detail page should use a `<select>` dropdown for courier selection, NOT a free-text `<input>`. Free-text causes typos (`"jne"` vs `"JNE"` vs `"JNE Express"`) that break tracking API calls.

#### Dropdown with auto-fill from checkout

```svelte
<select name="trackingCourier" class="w-full px-3 py-2 border border-sand rounded text-sm">
  <option value="">-- Pilih Kurir --</option>
  {#each ['jne','jnt','sicepat','anteraja','pos','tiki','lion','ninja','idexpress','sap','jet','wahana','rex','first','ncs','star','pandu','indo','jxl','dakota','rpx'] as k}
    <option value={k} selected={order.trackingCourier === k || (!order.trackingCourier && order.shippingCourier === k)}>
      {k.toUpperCase()}
    </option>
  {/each}
</select>
```

**Key:** `(!order.trackingCourier && order.shippingCourier === k)` auto-fills the courier selected by the user during checkout. No need for admin to re-type.

#### Courier tracking URL fallback map

```typescript
const COURIER_TRACKING_URLS: Record<string, (awb: string) => string> = {
  jne: (awb) => `https://www.jne.co.id/tracking/waybill/${awb}`,
  tiki: (awb) => `https://www.tiki.id/tracking/${awb}`,
  pos: (awb) => `https://www.posindonesia.co.id/tracking/${awb}`,
  sicepat: (awb) => `https://www.sicepat.com/tracking/${awb}`,
  jnt: (awb) => `https://www.jet.co.id/tracking/${awb}`,
  anteraja: (awb) => `https://anter-aja.com/tracking/${awb}`,
  lion: (awb) => `https://lionparcel.com/tracking/${awb}`,
  ninja: (awb) => `https://www.ninjavan.co/id-id/tracking?tracking_code=${awb}`,
  idexpress: (awb) => `https://idexpress.com/tracking/${awb}`,
  sap: (awb) => `https://sap-express.id/tracking/${awb}`,
}

function getCourierTrackingUrl(courier: string, awb: string): string {
  const fn = COURIER_TRACKING_URLS[courier.toLowerCase()]
  return fn ? fn(awb) : `https://www.google.com/search?q=resi+${courier}+${awb}`
}
```

## Svelte 5 Pitfall: `{@const}` Must Be Inside a Block

Svelte 5 `{@const}` can ONLY be used as a direct child of `{#if}`, `{#each}`, `{#snippet}`, or `{#key}` blocks. Using it outside any block in the template causes a build error:

```
Svelte compilation error: {@const} is only valid as a child of {#if}, {#each}, {#snippet}, or {#key}
```

**WRONG** — standalone `{@const}` outside any block:
```svelte
{@const statusSteps = ['pending', 'confirmed', 'processing', 'shipped', 'delivered']}
{@const currentIdx = statusSteps.indexOf(order.status)}
<div class="flex">
  {#each statusSteps as step, i}
    <!-- ... -->
  {/each}
</div>
```

**RIGHT** — move `{@const}` inside the `{#each}` block:
```svelte
<div class="flex">
  {#each ['pending', 'confirmed', 'processing', 'shipped', 'delivered'] as step, i}
    {@const currentIdx = ['pending', 'confirmed', 'processing', 'shipped', 'delivered'].indexOf(order.status)}
    {@const done = i <= currentIdx}
    <!-- ... -->
  {/each}
</div>
```

Alternative: compute the values in `<script>` with `$derived()` or plain `let` instead.

## Rich Tracking UI — Progress Bar + Animated Map + Timeline

Richer than the basic tracking timeline. Three visual components combined: status step progress bar, animated route map, and icon-enhanced event timeline.

### Progress bar (5 steps)

```svelte
<div class="flex items-center gap-0">
  {#each ['pending', 'confirmed', 'processing', 'shipped', 'delivered'] as step, i}
    {@const currentIdx = ['pending', 'confirmed', 'processing', 'shipped', 'delivered'].indexOf(order.status)}
    {@const done = i <= (currentIdx >= 0 ? currentIdx : 0)}
    {@const active = i === (currentIdx >= 0 ? currentIdx : 0)}
    <div class="flex-1 flex flex-col items-center">
      <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
        {done ? 'bg-terracotta text-white' : 'bg-sand/30 text-stone'}">
        {#if done && i < currentIdx}✓{:else}{i + 1}{/if}
      </div>
      <span class="text-[9px] mt-1 {active ? 'text-terracotta font-medium' : 'text-stone/50'}">
        {step === 'pending' ? 'Bayar' : step === 'confirmed' ? 'Konfirm' : step === 'processing' ? 'Proses' : step === 'shipped' ? 'Kirim' : 'Sampai'}
      </span>
    </div>
    {#if i < 4}
      <div class="h-0.5 flex-1 -mt-4 {i < currentIdx ? 'bg-terracotta' : 'bg-sand/30'}"></div>
    {/if}
  {/each}
</div>
```

### Animated delivery map

Uses a progress bar with truck emoji positioned at the correct percentage:

```svelte
{@const pct = tracking?.progressPercent ?? (order.status === 'delivered' ? 100 : order.status === 'shipped' ? 65 : order.status === 'processing' ? 25 : 10)}
<div class="bg-ivory rounded-lg p-3 relative overflow-hidden">
  <div class="flex items-center justify-between mb-3 text-[11px]">
    <div class="flex items-center gap-1.5">
      <span class="w-2 h-2 rounded-full bg-green-500"></span>
      <span>Jepara</span>
    </div>
    <div class="flex-1 mx-3 relative h-6">
      <div class="absolute top-3 left-0 right-0 h-0.5 bg-sand/50 rounded"></div>
      <div class="absolute top-3 left-0 h-0.5 bg-terracotta rounded transition-all" style="width: {pct}%"></div>
      <div class="absolute top-1 text-base transition-all" style="left: calc({pct}% - 12px)">
        <span class="animate-bounce">{order.status === 'delivered' ? '📬' : '🚚'}</span>
      </div>
    </div>
    <div class="flex items-center gap-1.5">
      <span class="w-2 h-2 rounded-full {order.status === 'delivered' ? 'bg-green-500' : 'bg-sand/50'}"></span>
      <span>{order.shippingCity || 'Tujuan'}</span>
    </div>
  </div>
  <p class="text-[10px] text-stone/50 text-center">
    {order.status === 'delivered' ? '✅ Paket telah sampai' : order.status === 'shipped' ? '🚚 Dalam perjalanan' : order.status === 'processing' ? '📋 Sedang diproses' : '⏳ Menunggu pembayaran'}
  </p>
</div>
```

### Icon-enhanced event timeline

Each event gets: circle icon (latest=terracotta ring, last=green check), location with 📍, and muted timestamp:

```svelte
{#each tracking.events as event, j}
  {@const isLast = j === tracking.events.length - 1}
  {@const isLatest = j === 0}
  <div class="flex gap-3">
    <div class="flex flex-col items-center pt-0.5">
      <div class="w-4 h-4 rounded-full flex items-center justify-center text-[10px]
        {isLatest ? 'bg-terracotta text-white ring-2 ring-terracotta/20' : isLast ? 'bg-green-500 text-white' : 'bg-sand/30 text-stone'}">
        {isLast ? '✓' : isLatest ? '●' : ''}
      </div>
      {#if !isLast}<div class="w-0.5 flex-1 {isLatest ? 'bg-terracotta/30' : 'bg-sand/30'}"></div>{/if}
    </div>
    <div class="text-sm pb-3">
      <p class="font-medium {isLatest ? 'text-charcoal' : isLast ? 'text-green-700' : 'text-stone'}">{event.desc}</p>
      {#if event.location}<p class="text-stone/60 text-xs mt-0.5">📍 {event.location}</p>{/if}
      <p class="text-stone/40 text-xs mt-0.5">{event.date} · {event.time}</p>
    </div>
  </div>
{/each}
```

### External tracking link — collapsed `<details>`

The link to the courier's website should be secondary, hidden behind a `<details>` element so it doesn't distract from the inline timeline:

```svelte
<details class="mt-4 text-[11px] text-stone/50">
  <summary class="cursor-pointer hover:text-stone">Lacak di website {courier.toUpperCase()} ↗</summary>
  <a href={trackingUrl(courier, trackingNumber)} target="_blank" rel="noopener" class="inline-block mt-2 text-terracotta hover:underline">
    Buka tracking resmi {courier.toUpperCase()}
  </a>
</details>
```

### Progressive disclosure

Only show the map and timeline when there are events. Show loading spinners, error states, and empty states clearly:

```svelte
{#if tracking?.events?.length}
  <!-- map + timeline -->
{:else if trackingError}
  <p class="bg-red-50 p-3 rounded">{trackingError}</p>
{:else if !tracking}
  <div class="flex items-center gap-2 animate-pulse">
    <span class="w-3 h-3 border-2 border-terracotta border-t-transparent rounded-full animate-spin"></span>
    Memuat data tracking...
  </div>
{:else}
  <p class="italic text-stone">Belum ada data tracking.</p>
{/if}
```

## SVG Icons Over Emojis — Design Preference

For production Indonesian storefront UIs, prefer inline SVG icons over emojis. Emojis render differently across operating systems (Apple vs Android vs Windows), break design consistency, and look unprofessional on desktop. SVG icons are consistent, support `stroke`/`fill` color theming, and animate smoothly.

**Pattern:** Use minimal inline SVGs (12-18px viewBox) with Tailwind color classes:

```svelte
<!-- Truck icon (shipping) -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
  <rect x="1" y="3" width="15" height="13"/>
  <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/>
  <circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
</svg>

<!-- Checkmark (done step) -->
<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
  <polyline points="20 6 9 17 4 12"/>
</svg>

<!-- Map pin (location) -->
<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="10" r="3"/>
  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
</svg>

<!-- External link icon -->
<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
  <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
</svg>

<!-- Package/box icon (tracking header) -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
  <path d="M16 2v4M8 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z"/>
  <rect x="2" y="16" width="20" height="4" rx="1"/>
</svg>

<!-- Info circle (simulation badge) -->
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="10"/>
  <line x1="12" y1="16" x2="12" y2="12"/>
  <line x1="12" y1="8" x2="12.01" y2="8"/>
</svg>
```

**Color theming:** Use `stroke="currentColor"` so the icon inherits the parent's text color via Tailwind. For colored icons (delivered package), use explicit hex: `stroke="#16a34a"`.

**Pitfall: emojis break consistency.** A truck emoji 🚚 looks different on iOS (realistic), Android (flat), and Windows (outline). An SVG truck renders identically everywhere.

## Enhanced Mock Tracking Generator

The previous mock generator had only 3 event variations. The enhanced version adds:

- `progressPercent` (5, 15, 25, 65, 100 per status) for map animation
- `confirmed` status as separate from `processing`
- 4-event timeline for `delivered` (pickup → transit → arrived at destination → delivered)
- `processing` gets 2 events (payment confirmed → being processed)
- Transit hub named consistently ("Semarang - Hub Transit") instead of generic "Jakarta"

```typescript
function generateMockTracking(order: {
  id: string; status: string; trackingNumber: string;
  trackingCourier: string; createdAt: Date; shippingCity: string
}) {
  const courier = (order.trackingCourier || 'jne').toUpperCase()
  const resi = order.trackingNumber || 'SIM' + order.id.slice(0, 8)
  const city = order.shippingCity || 'Jakarta'
  const now = new Date()
  const events: Array<{date:string;time:string;desc:string;location:string}> = []
  let progressPercent = 0

  function d(daysAgo: number) {
    const dt = new Date(now.getTime() - daysAgo * 86400000)
    dt.setHours(8 + Math.floor(Math.random() * 10), Math.floor(Math.random() * 60))
    return { date: dt.toISOString().split('T')[0], time: dt.toTimeString().slice(0, 8) }
  }

  if (order.status === 'delivered') {
    events.push(
      { ...d(3), desc: `Paket diterima oleh ${courier}`, location: `Jepara - Drop Point ${courier}` },
      { ...d(2), desc: `Paket dalam perjalanan ke ${city}`, location: `Semarang - Hub Transit ${courier}` },
      { ...d(0.5), desc: `Paket tiba di ${city} — sedang diantar kurir`, location: `${city} - Kantor ${courier}` },
      { ...d(0.1), desc: `Paket telah diterima oleh penerima`, location: city },
    )
    progressPercent = 100
  } else if (order.status === 'shipped') {
    events.push(
      { ...d(1.5), desc: `Paket diterima oleh ${courier}`, location: `Jepara - Drop Point ${courier}` },
      { ...d(0.3), desc: `Paket dalam perjalanan ke ${city}`, location: `Semarang - Hub Transit ${courier}` },
    )
    progressPercent = 65
  } else if (order.status === 'processing') {
    events.push(
      { ...d(1), desc: 'Pembayaran dikonfirmasi', location: 'Sistem' },
      { ...d(0.5), desc: 'Pesanan sedang diproses oleh penjual', location: 'Jepara - the client site' },
    )
    progressPercent = 25
  } else if (order.status === 'confirmed') {
    events.push({ ...d(0.5), desc: 'Pesanan dikonfirmasi — menunggu diproses', location: 'Sistem' })
    progressPercent = 15
  } else {
    events.push({ ...d(0.1), desc: 'Menunggu konfirmasi pembayaran', location: 'Sistem' })
    progressPercent = 5
  }

  return { courier, awb: resi, status: order.status, origin: 'Jepara, Jawa Tengah', destination: city, events, progressPercent, _simulated: true }
}
```

The `progressPercent` field should be passed through the tracking API response so the frontend can use it directly instead of computing fallback percentages from order status.

Biteship is an Indonesian multi-courier shipping API. Covers JNE, J&T, SiCepat, AnterAja, Pos Indonesia, and more.

**Key difference from RajaOngkir:** Biteship's area-search endpoint is FREE (no balance needed). Rates and tracking need a funded account.

### API contract

| Endpoint | Method | Auth |
|----------|--------|------|
| `GET /v1/maps/areas?countries=ID&input={q}&type=single` | Search areas | `Bearer <key>` |
| `POST /v1/rates/couriers` | Cost calc | `Bearer <key>` |
| `GET /v1/trackings/{id}/couriers/{code}` | Tracking | `Bearer <key>` |

### Rate-limited or no-balance? Use flat rate fallback

When Biteship returns `"No sufficient balance"` or the API is down, serve flat rate estimates based on Java/luar-Jawa and weight:

```typescript
// src/routes/api/ongkir/cost/+server.ts
export const POST = async ({ request }) => {
  const { originId, destinationId, weight, destinationProvince } = body

  // 1. Try real-time rates
  try {
    const rates = await calculateRates(originId, destinationId, weight, 150000)
    if (rates.length > 0) return json({ data: rates })
  } catch (_) { /* fall through */ }

  // 2. Flat rate fallback
  const isJava = destinationProvince ? isJavaProvince(destinationProvince) : true
  return json({ data: flatRates(isJava, weight) })
}
```

**Flat rates (Java from Jepara, ≤1kg):** Pos 10k · SiCepat 12k · J&T 13k · AnterAja 14k · JNE 15k
**Flat rates (Luar Jawa, ≤1kg):** Pos 28k · SiCepat 30k · J&T 32k · AnterAja 33k · JNE 35k
**Over 1kg:** Add ~40-50% to all rates.

### Prerequisites

- `BITESHIP_API_KEY` in `.env` and `compose.yaml`
- `api.biteship.com` added to CSP `connect-src` in `hooks.server.ts`
- Checkout page must pass `destinationProvince` to `/api/ongkir/cost`

See `references/biteship-api.md` for full API details, flat rate table, and the TypeScript module implementation.

## Password Reset & Transactional Email (Resend API — Zero Deps)

Use for forgot-password, order confirmation, or any transactional email in Indonesian storefront projects.

### Why Resend
- Zero npm dependencies (REST API via `fetch`)
- Free tier: 100 emails/day
- No SMTP config needed — just `RESEND_API_KEY`
- Falls back to `console.log` the reset link when no key is set

### Prisma schema

```prisma
model PasswordResetToken {
  id        String   @id @default(cuid())
  email     String
  token     String   @unique
  expiresAt DateTime
  used      Boolean  @default(false)
  createdAt DateTime @default(now())
}
```

Push schema: `docker cp prisma/schema.prisma container:/app/prisma/schema.prisma && docker exec container npx prisma db push`

### Email lib: `src/lib/server/email.ts`

```typescript
import { env } from '$env/dynamic/private'

const RESEND_API_KEY = env.RESEND_API_KEY || ''
const FROM_EMAIL = env.EMAIL_FROM || 'user@example.com'
const ORIGIN = env.ORIGIN || 'http://localhost:3000'

export async function sendPasswordResetEmail(email: string, token: string) {
  const resetUrl = `${ORIGIN}/reset-password?token=<redacted>`
  if (!RESEND_API_KEY) {
    console.log(`[email] Reset link for ${email}: ${resetUrl}`)
    return true
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${RESEND_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from: FROM_EMAIL,
      to: [email],
      subject: 'Reset Password',
      html: `<a href="${resetUrl}">Reset Password</a>`
    })
  })
  return res.ok
}
```

### Routes

| Route | Purpose |
|-------|---------|
| `/forgot-password` | Form → generates token → sends email. Always returns success (prevents email enumeration). |
| `/reset-password?token=<redacted>` | Validates token → form for new password → hashes + marks token used. |

### Pitfall: email enumeration prevention
The forgot-password endpoint must ALWAYS return the same "check your email" response, even if the email doesn't exist. Otherwise attackers can enumerate valid emails.

```typescript
// CORRECT — always return sent: true
const user = await prisma.user.findUnique({ where: { email } })
if (user) {
  const token=<redacted>'hex')
  await prisma.passwordResetToken.create({ data: { email, token, expiresAt: new Date(Date.now() + 3600_000) } })
  await sendPasswordResetEmail(email, token)
}
return { sent: true }  // always the same response
```

### Pitfall: token one-time use
Mark token as `used: true` in the same transaction as password update. Prevents replay.

```typescript
await prisma.$transaction(async (tx) => {
  await tx.user.update({ where: { email: record.email }, data: { passwordHash: hashSync(password, 10) } })
  await tx.passwordResetToken.update({ where: { id: record.id }, data: { used: true } })
})
```

### Required env vars

Add to `.env.example`:
```
RESEND_API_KEY=
EMAIL_FROM=user@example.com
```

## Product Demo / Review Videos — Higgsfield Video Explainer

For creating narrated product demos, store walkthrough videos, or website review videos, use the [Higgsfield Video Explainer CLI](https://github.com/higgsfield-ai/skills). It generates non-photoreal narrated explainer videos from ordered 10-second blocks with AI-generated visuals, voice narration, and server-side assembly.

**Install:**
```bash
curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh
higgsfield auth login
```

**Pipeline:** Style selection → research → script narration → generate voice per block → generate video clip per block → assemble into final MP4.

**Use case:** Demo video the client site — walk through product pages, checkout flow, voucher system, and tracking UI. Each feature = one 10-second block. Total 60-120 seconds for a full store tour.

**Pitfall:** Higgsfield needs a funded account. The CLI `higgsfield auth login` opens browser OAuth. Without auth, `higgsfield account status` returns "No workspace selected."

For full Hermes Agent integration (MCP server config + skills install), see `references/higgsfield-hermes-setup.md`.

## References
- `references/rajaongkir-v2-api.md` — Full API contract for shipping cost
- `references/kommerce-payment-api.md` — Full API contract for payment gateway
- `references/midtrans-qris-api.md` — Midtrans QRIS dynamic API contract, notifications, pitfall list
- `references/midtrans-redirect-session.md` — Redirect-approach fix session: diagnostics, E2E verification, file manifest
- `references/gobiz-gopay-merchant-api.md` — GoBiz (GoPay Merchant) API endpoints, QRIS string manipulation spec, auth flow, monitoring patterns
- `references/rajaongkir-tracking-api.md` — Tracking API contract + integration pattern
- `references/transactional-email-resend.md` — Resend API pattern + password reset flow
- `references/local-city-fallback.md` — Local city JSON fallback for when RajaOngkir API is down/429
- `references/biteship-api.md` — Biteship shipping API (area search, rates, tracking, flat rate fallback)
- `references/admin-dashboard-tech-debt.md` — Common admin dashboard technical debt findings + fix patterns
- `references/rich-tracking-ui.md` — Full Svelte 5 tracking template: progress bar, animated map, icon timeline, collapsible external link

## Templates
- `templates/gobiz-env.example` — .env template for GoBiz/GoPay merchant credentials
- `templates/gobiz-qris-demo.mjs` — Bootstrap script: QRIS generation + live payment monitor
