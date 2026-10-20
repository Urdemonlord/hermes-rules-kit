# Midtrans Under Review — WhatsApp Fallback Pattern

## Situation
Midtrans merchant account pending review/approval. Checkout must still work — redirect users to WhatsApp for manual order + payment confirmation.

## Implementation (SvelteKit)

### 1. Checkout server action — skip Midtrans if key missing

```typescript
// +page.server.ts (checkout action, after order creation)
const MIDTRANS_KEY = env.MIDTRANS_SERVER_KEY || ''

// After order is created and stock decremented...
if (!MIDTRANS_KEY) {
  await prisma.order.update({
    where: { id: orderId },
    data: { paymentMethod: 'manual', paymentStatus: 'pending' }
  })
  throw redirect(302, `/order/${orderId}`)
}

// ... rest of Midtrans Snap creation
```

Key points:
- Order is created first (stock decremented, cart cleared) regardless of payment gateway
- `paymentMethod: 'manual'` signals WhatsApp fallback mode
- No error state — order is valid, just needs manual payment

### 2. Order page — show WhatsApp CTA when manual

```svelte
{#if order.paymentStatus === 'pending' && order.paymentMethod === 'manual'}
  <div class="border border-green-200 bg-green-50 rounded-lg p-6 mb-8 text-sm">
    <h2 class="font-medium mb-3 text-green-800">Pesanan Diterima</h2>
    <p class="text-green-700 mb-2">Silakan hubungi kami via WhatsApp untuk konfirmasi & pembayaran.</p>
    <p><strong>Total:</strong> {formatPrice(order.total)}</p>
    <p><strong>No. Pesanan:</strong> #{order.id.slice(0, 8)}</p>
    <a href="https://wa.me/62XXXXXXXXXXX?text={encodeURIComponent(
      'Halo, saya ingin konfirmasi pesanan #' + order.id.slice(0, 8) + ' - Total Rp ' + order.total.toLocaleString('id-ID')
    )}"
      target="_blank" rel="noopener noreferrer"
      class="mt-4 flex items-center justify-center gap-2 w-full bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 transition text-sm">
      Konfirmasi via WhatsApp
    </a>
  </div>
{:else if order.paymentStatus === 'pending'}
  <!-- Normal Midtrans payment UI -->
{/if}
```

### 3. Checkout page — update payment method label

```svelte
<div class="border border-sand/50 rounded-lg p-4 mb-6">
  <p class="text-sm font-medium mb-2">Metode Pembayaran</p>
  <p class="text-sm text-stone">Konfirmasi & pembayaran via WhatsApp</p>
</div>
```

## WA URL format
```
https://wa.me/{phone}?text={encoded_message}
```
- Phone: `62XXXXXXXXXXX` (no `+`, no `-`, no spaces)
- Text: URL-encoded pre-filled message with order details

## UX notes
- Green theme (WhatsApp brand color), not Midtrans orange
- Message auto-fills order number + total — reduces friction
- User stays in order page — can see order details while chatting
- Status stays `pending` until owner manually confirms payment (admin dashboard)

## Admin manual confirmation

**Must have a UI action — raw SQL is not sufficient for non-technical operators.**

When checkout is forced to `paymentMethod: 'manual'`, the Midtrans webhook (`/api/midtrans/webhook`) will never fire for these orders — it only handles `paymentMethod: 'midtrans_snap'` orders with a `paymentRef`. If the admin panel has no way to update `paymentStatus`, every manual order is permanently stuck at `pending`.

### Required: admin order detail page (`/admin/orders/[id]`)

Server action (`+page.server.ts`):
```typescript
updatePaymentStatus: async ({ request, params, locals }) => {
    requireAdmin(locals.user)
    const form = await request.formData()
    const paymentStatus = form.get('paymentStatus') as string
    await prisma.order.update({ where: { id: params.id }, data: { paymentStatus } })
    return { success: true }
}
```

UI (Svelte 5 — three separate forms, each with a hidden input):
```svelte
<label class="block text-sm font-medium mb-2">Pembayaran</label>
<form method="POST" action="?/updatePaymentStatus" use:enhance class="flex items-center gap-2">
    <input type="hidden" name="paymentStatus" value="paid">
    <button class="px-3 py-2 rounded text-sm bg-green-600 text-white hover:bg-green-700">✓ Lunas</button>
</form>
<form method="POST" action="?/updatePaymentStatus" use:enhance class="flex items-center gap-2 mt-2">
    <input type="hidden" name="paymentStatus" value="pending">
    <button class="px-3 py-2 rounded text-sm bg-yellow-500 text-white hover:bg-yellow-600">Belum</button>
</form>
<form method="POST" action="?/updatePaymentStatus" use:enhance class="flex items-center gap-2 mt-2">
    <input type="hidden" name="paymentStatus" value="failed">
    <button class="px-3 py-2 rounded text-sm bg-red-600 text-white hover:bg-red-700">✕ Gagal</button>
</form>
```

### Pitfall: forced `paymentMethod: 'manual'`

If the checkout server action unconditionally sets `paymentMethod: 'manual'` and then redirects (as happens when Midtrans is under review), the entire Midtrans code path below is unreachable dead code. This is intentional during review, but remember:
- The admin UI payment status buttons are mandatory — not optional polish.
- Dashboard stats (`paymentStatus === 'paid'` count/aggregate) won't show revenue until admin manually marks orders as paid.
- The cron auto-cancel job (`/api/cron/cancel-expired`) only auto-cancels pending orders with an expiry — manual orders with expired timestamps will be cancelled even if the customer paid and the admin hasn't marked it yet. Consider a longer expiry window for manual orders, or exclude manual orders from auto-cancel.

## When Midtrans approved
Just add `MIDTRANS_SERVER_KEY` env var back. Existing Midtrans code takes over — the `manual` fallback never triggers when key exists. No code changes needed.
