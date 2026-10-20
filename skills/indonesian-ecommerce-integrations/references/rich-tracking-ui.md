# Rich Customer Tracking UI — Full Svelte 5 Template (SVG Icons Version)

Complete tracking section for the customer-facing order page (`/order/[id]/+page.svelte`).
Replaces the basic timeline + external link with: progress bar, animated map, SVG icon-enhanced timeline, and collapsible external link.

**Design rule:** Use inline SVG icons, NOT emojis. Emojis render differently across OS, break consistency, and look unprofessional. All icons use `stroke="currentColor"` to inherit parent text color via Tailwind.

## Data contract

The tracking API (`GET /api/order/[id]/tracking`) must return:

```typescript
interface TrackingResponse {
  courier: string           // e.g. "JNE"
  awb: string               // tracking number
  status: string            // order status
  origin: string            // "Jepara, Jawa Tengah"
  destination: string       // customer's city
  events: Array<{
    date: string            // "2026-07-24"
    time: string            // "12:32:54"
    desc: string            // "Paket diterima oleh JNE"
    location: string        // "Jepara - Drop Point JNE"
  }>
  progressPercent: number   // 0-100 for map animation
  _simulated?: boolean      // true if mock data
  trackingUrl?: string      // direct link to courier website
}
```

## SVG Icon Library

Replace emojis with these inline SVGs. All use `stroke="currentColor"` for theming.

```svelte
<!-- Package/box icon (tracking header) — replaces 📦 -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.5" class="text-stone">
  <path d="M16 2v4M8 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z"/>
  <rect x="2" y="16" width="20" height="4" rx="1"/>
</svg>

<!-- Info circle (simulation badge) — replaces 🔬 -->
<svg width="14" height="14" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="10"/>
  <line x1="12" y1="16" x2="12" y2="12"/>
  <line x1="12" y1="8" x2="12.01" y2="8"/>
</svg>

<!-- Checkmark (completed step, timeline last event) — replaces ✓ -->
<svg width="12" height="12" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="3">
  <polyline points="20 6 9 17 4 12"/>
</svg>

<!-- Dot (progress step indicator, timeline latest) — replaces ● -->
<svg width="6" height="6" viewBox="0 0 24 24" fill="currentColor">
  <circle cx="12" cy="12" r="10"/>
</svg>

<!-- Map pin (location) — replaces 📍 -->
<svg width="10" height="10" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="10" r="3"/>
  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
</svg>

<!-- Truck icon (map animation, in-transit) — replaces 🚚 -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="#c2410c" stroke-width="1.5" class="animate-bounce">
  <rect x="1" y="3" width="15" height="13"/>
  <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/>
  <circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
</svg>

<!-- Delivered icon (map animation, arrived) — replaces 📬 -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="#16a34a" stroke-width="1.5" class="animate-bounce">
  <path d="M21 10.5V20a2 2 0 01-2 2H5a2 2 0 01-2-2v-8M3 10l4-6h10l4 6M12 3v7"/>
  <polyline points="8 14 12 18 16 14"/>
</svg>

<!-- External link icon (collapsed details) — replaces ↗ text -->
<svg width="10" height="10" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2">
  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
  <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
</svg>
```

## Full Template (SVG Icons Only)

```svelte
{#if order.trackingNumber}
<div class="border border-sand/50 rounded-lg p-4 sm:p-6 mb-8 text-sm">
  <div class="flex items-center justify-between mb-4">
    <h2 class="font-medium flex items-center gap-2">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="1.5" class="text-stone">
        <path d="M16 2v4M8 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z"/>
        <rect x="2" y="16" width="20" height="4" rx="1"/>
      </svg>
      Tracking Pengiriman
    </h2>
    <div class="flex items-center gap-2 text-[10px] sm:text-xs">
      <span class="px-2 py-0.5 bg-sand/30 rounded font-medium">{(order.trackingCourier || '').toUpperCase()}</span>
      <span class="text-stone font-mono">{order.trackingNumber}</span>
    </div>
  </div>

  {#if tracking?._simulated}
    <div class="mb-4 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded text-[11px] text-blue-700 flex items-center gap-2">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="16" x2="12" y2="12"/>
        <line x1="12" y1="8" x2="12.01" y2="8"/>
      </svg>
      Simulasi — tracking real aktif setelah Biteship API tersambung.
    </div>
  {/if}

  <!-- Status progress bar: Bayar→Konfirm→Proses→Kirim→Sampai -->
  <div class="mb-6">
    <div class="flex items-center gap-0">
      {#each ['pending', 'confirmed', 'processing', 'shipped', 'delivered'] as step, i}
        {@const currentIdx = ['pending', 'confirmed', 'processing', 'shipped', 'delivered'].indexOf(order.status)}
        {@const done = i <= (currentIdx >= 0 ? currentIdx : 0)}
        {@const active = i === (currentIdx >= 0 ? currentIdx : 0)}
        <div class="flex-1 flex flex-col items-center">
          <div class="w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-bold transition-all
            {done ? 'bg-terracotta text-white' : 'bg-sand/30 text-stone'}">
            {#if done && i < (currentIdx >= 0 ? currentIdx : 0)}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            {:else}
              {i + 1}
            {/if}
          </div>
          <span class="text-[8px] sm:text-[9px] mt-1 text-center leading-tight {active ? 'text-terracotta font-medium' : 'text-stone/50'}">
            {step === 'pending' ? 'Bayar' : step === 'confirmed' ? 'Konfirm' : step === 'processing' ? 'Proses' : step === 'shipped' ? 'Kirim' : 'Sampai'}
          </span>
        </div>
        {#if i < 4}
          <div class="h-0.5 flex-1 -mt-4 {i < (currentIdx >= 0 ? currentIdx : 0) ? 'bg-terracotta' : 'bg-sand/30'}"></div>
        {/if}
      {/each}
    </div>
  </div>

  <!-- Animated delivery map: Jepara ──truck──→ city -->
  {#if tracking?.events?.length}
    {@const pct = tracking?.progressPercent ?? (order.status === 'delivered' ? 100 : order.status === 'shipped' ? 65 : order.status === 'processing' ? 25 : 10)}
    <div class="mb-5 bg-ivory rounded-lg p-3 sm:p-4 relative overflow-hidden">
      <div class="flex items-center justify-between mb-3 text-[10px] sm:text-[11px]">
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-green-500"></span>
          <span class="text-stone font-medium">Jepara</span>
        </div>
        <div class="flex-1 mx-3 relative h-6">
          <div class="absolute top-3 left-0 right-0 h-0.5 bg-sand/50 rounded"></div>
          <div class="absolute top-3 left-0 h-0.5 bg-terracotta rounded transition-all duration-1000" style="width: {pct}%"></div>
          <div class="absolute top-1 transition-all duration-1000" style="left: calc({pct}% - 10px)">
            {#if order.status === 'delivered'}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="#16a34a" stroke-width="1.5" class="animate-bounce">
                <path d="M21 10.5V20a2 2 0 01-2 2H5a2 2 0 01-2-2v-8M3 10l4-6h10l4 6M12 3v7"/>
                <polyline points="8 14 12 18 16 14"/>
              </svg>
            {:else}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="#c2410c" stroke-width="1.5" class="animate-bounce">
                <rect x="1" y="3" width="15" height="13"/>
                <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/>
                <circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
              </svg>
            {/if}
          </div>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full {order.status === 'delivered' ? 'bg-green-500' : 'bg-sand/50'}"></span>
          <span class="text-stone font-medium">{order.shippingCity || 'Tujuan'}</span>
        </div>
      </div>
      <p class="text-[9px] sm:text-[10px] text-stone/50 text-center">
        {#if order.status === 'delivered'}
          <span class="text-green-600 font-medium">Paket telah sampai di tujuan</span>
        {:else if order.status === 'shipped'}
          <span class="text-terracotta font-medium">Paket dalam perjalanan</span>
        {:else if order.status === 'processing'}
          Pesanan sedang diproses
        {:else}
          Menunggu pembayaran
        {/if}
      </p>
    </div>
  {/if}

  <!-- Timeline events with SVG icons -->
  {#if tracking?.events?.length}
    <div class="space-y-0 ml-1">
      {#each tracking.events as event, j}
        {@const isLast = j === tracking.events.length - 1}
        {@const isLatest = j === 0}
        <div class="flex gap-3">
          <div class="flex flex-col items-center pt-0.5">
            <div class="w-4 h-4 rounded-full flex items-center justify-center
              {isLatest ? 'bg-terracotta text-white ring-2 ring-terracotta/20' : isLast ? 'bg-green-500 text-white' : 'bg-sand/30 text-stone'}">
              {#if isLast}
                <svg width="8" height="8" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="4">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              {:else if isLatest}
                <svg width="6" height="6" viewBox="0 0 24 24" fill="currentColor">
                  <circle cx="12" cy="12" r="10"/>
                </svg>
              {/if}
            </div>
            {#if !isLast}
              <div class="w-0.5 flex-1 {isLatest ? 'bg-terracotta/30' : 'bg-sand/30'}"></div>
            {/if}
          </div>
          <div class="text-sm pb-3">
            <p class="font-medium {isLatest ? 'text-charcoal' : isLast ? 'text-green-700' : 'text-stone'}">{event.desc}</p>
            {#if event.location}
              <p class="text-stone/60 text-[10px] sm:text-xs mt-0.5 flex items-center gap-1">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="10" r="3"/>
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                </svg>
                {event.location}
              </p>
            {/if}
            <p class="text-stone/40 text-[10px] sm:text-xs mt-0.5">{event.date} · {event.time}</p>
          </div>
        </div>
      {/each}
    </div>
  {:else if trackingError}
    <p class="text-sm text-stone bg-red-50 p-3 rounded">{trackingError}</p>
  {:else if !tracking}
    <div class="flex items-center gap-2 text-sm text-stone animate-pulse">
      <span class="w-3 h-3 border-2 border-terracotta border-t-transparent rounded-full animate-spin"></span>
      Memuat data tracking...
    </div>
  {:else}
    <p class="text-sm text-stone italic">Belum ada data tracking.</p>
  {/if}

  <!-- External link — hidden behind <details> with external-link SVG icon -->
  <details class="mt-4 text-[10px] sm:text-[11px] text-stone/50">
    <summary class="cursor-pointer hover:text-stone transition inline-flex items-center gap-1">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2">
        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
        <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
      </svg>
      Lacak di website {(order.trackingCourier || 'kurir').toUpperCase()}
    </summary>
    <a href={trackingUrl(order.trackingCourier || 'jne', order.trackingNumber)}
      target="_blank" rel="noopener"
      class="inline-block mt-2 text-terracotta hover:underline">
      Buka tracking resmi {(order.trackingCourier || '').toUpperCase()}
    </a>
  </details>
</div>
{/if}
```

## Tracking URL helper (13 couriers)

```typescript
function trackingUrl(courier: string, trackingNumber: string): string {
  const c = (courier || '').toLowerCase().trim()
  const urls: Record<string, string> = {
    jne: `https://www.jne.co.id/tracking/waybill/${trackingNumber}`,
    tiki: `https://www.tiki.id/tracking/${trackingNumber}`,
    pos: `https://www.posindonesia.co.id/tracking/${trackingNumber}`,
    sicepat: `https://www.sicepat.com/tracking/${trackingNumber}`,
    jnt: `https://www.jet.co.id/tracking/${trackingNumber}`,
    anteraja: `https://anter-aja.com/tracking/${trackingNumber}`,
    lion: `https://lionparcel.com/tracking/${trackingNumber}`,
    ninja: `https://www.ninjavan.co/id-id/tracking?tracking_code=${trackingNumber}`,
    idexpress: `https://idexpress.com/tracking/${trackingNumber}`,
    sap: `https://sap-express.id/tracking/${trackingNumber}`,
  }
  return urls[c] || `https://www.google.com/search?q=resi+${courier}+${trackingNumber}`
}
```

## Key design decisions

1. **External link is collapsed** — The primary tracking experience is the inline timeline + map. The external courier link is hidden in `<details>` so it doesn't distract.

2. **Map uses `progressPercent` from API** — Don't hardcode percentages. The API returns the correct value based on order status. Fall back to status-based defaults.

3. **Timeline icons encode priority** — Latest event gets terracotta ring with fill dot. Last event gets green checkmark. Middle events are subtle gray circles.

4. **Simulation badge is a gentle blue** — Informational, not a warning. Uses information-circle SVG icon.

5. **Empty states are explicit** — Loading spinner, error panel, "Belum ada data", each visually distinct.

6. **Emoji ban** — Zero emojis in production UI. All icons are inline SVGs with `stroke="currentColor"` or explicit hex colors. This ensures consistent rendering across all operating systems and browsers.
