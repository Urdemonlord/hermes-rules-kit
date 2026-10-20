# Payment Provider Under Review → WhatsApp Fallback

## Symptom

Payment provider (Midtrans) is under review/verification. Checkout creates orders but Midtrans Snap can't process payments. Need a temporary WhatsApp-based payment flow.

## Pattern

### 1. Checkout server — bypass payment provider

In `+page.server.ts`, after the order is created and cart cleared:

```typescript
// Midtrans under review — manual order via WhatsApp
await prisma.order.update({
  where: { id: orderId },
  data: { paymentMethod: 'manual', paymentStatus: 'pending' }
})
throw redirect(302, `/order/${orderId}`)
```

This replaces the Midtrans Snap API call block. The order still gets created in the DB (stock decremented, cart cleared), but no payment gateway is called.

**Key**: hardcode the bypass rather than checking `if (!MIDTRANS_KEY)`. Env vars may still have the key from compose.yaml even when provider is non-functional. The check `!MIDTRANS_KEY` will be `false` and the Midtrans call will proceed (and fail on "no payment channels available").

### 2. Order page — WhatsApp button for all pending orders

In `+page.svelte`, replace the Midtrans Snap/Snap.js payment section with a WhatsApp CTA:

```svelte
{#if order.paymentStatus === 'pending'}
  <div class="border border-green-200 bg-green-50 rounded-lg p-6 mb-8 text-sm">
    <h2 class="font-medium mb-3 text-green-800">Pesanan Diterima</h2>
    <p class="text-green-700 mb-2">
      Pesanan Anda sudah tercatat. Silakan hubungi kami via WhatsApp untuk konfirmasi & pembayaran.
    </p>
    <div class="border-t border-green-200 pt-3 mt-3 space-y-1 text-green-700 text-sm">
      <p><strong>Total:</strong> {formatPrice(order.total)}</p>
      <p><strong>No. Pesanan:</strong> #{order.id.slice(0, 8)}</p>
    </div>
    <a href="https://wa.me/{PHONE}?text={encodeURIComponent('Halo, saya ingin konfirmasi pesanan #' + order.id.slice(0, 8) + ' - Total Rp ' + order.total.toLocaleString('id-ID'))}"
      target="_blank" rel="noopener noreferrer"
      class="mt-4 flex items-center justify-center gap-2 w-full bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 transition text-sm">
      <!-- WhatsApp SVG icon -->
      Konfirmasi via WhatsApp
    </a>
  </div>
{:else if order.paymentStatus === 'paid'}
  ...
{:else if order.paymentStatus === 'failed'}
  ...
{/if}
```

**Critical**: remove ALL Midtrans-related UI — Snap.js loader, `goToPaymentPage()`, `loadSnapJs()`, snap token expired block, sandbox test block. Leaving them creates dead code and confusion.

### 3. Update old orders in DB

Old pending orders with `paymentMethod: 'midtrans_snap'` need updating:

```bash
docker exec <container> node -e '
const D = require("better-sqlite3");
const db = new D("/data/dev.db");
const r = db.prepare("UPDATE \"Order\" SET paymentMethod = ? WHERE paymentMethod = ? AND paymentStatus = ?")
  .run("manual", "midtrans_snap", "pending");
console.log("Updated:", r.changes, "rows");
db.close();
'
```

### 4. Checkout page label

Update payment method display:

```svelte
<!-- Before -->
<p>Midtrans Snap ...</p>
<!-- After -->
<p>Konfirmasi & pembayaran via WhatsApp</p>
```

### 5. Remove sandbox test UI from order page

Delete `{#if data.isSandbox && order.paymentStatus === 'pending' && order.paymentMethod === 'midtrans_snap'}...{/if}`.

## Pitfalls

1. **Env vars still present**: Even when provider is non-functional, `MIDTRANS_SERVER_KEY` is set in Docker env from compose.yaml. Code that checks `if (!MIDTRANS_KEY)` will NOT trigger. Hardcode the bypass.

2. **SvelteKit requires Docker rebuild**: `.ts` and `.svelte` changes need `docker compose build --no-cache` + `docker compose up -d`.

3. **Orphaned Midtrans code**: Incomplete edits leave dangling `{/if}`, `{:else if}` or orphaned JS vars. Verify template structure after editing.

4. **Dead JS variables**: Remove `snapToken`, `paymentUrl`, `midtransClientKey`, `goToPaymentPage()`, `loadSnapJs()`, `payWithSnap()` from `<script>` block.

## Related

- `references/midtrans-no-payment-channels.md` — channel not enabled in dashboard (different root cause)
- `references/sveltekit-midtrans-compose-integration.md` — full Midtrans integration reference
