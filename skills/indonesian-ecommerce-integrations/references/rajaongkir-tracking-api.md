# RajaOngkir Tracking API — Full Integration Pattern

Complete code for adding live shipment tracking to a SvelteKit e-commerce app using RajaOngkir waybill API.

## 1. Server lib: `rajaongkir.ts` — add `trackWaybill()`

```typescript
// src/lib/server/rajaongkir.ts

export interface TrackingEvent {
  date: string
  time: string
  desc: string
  location: string
}

export interface TrackingResult {
  courier: string
  awb: string
  status: string
  service: string
  origin: string
  destination: string
  receiver: string
  weight: string
  events: TrackingEvent[]
  raw: unknown
}

export async function trackWaybill(
  awb: string,
  courier: string
): Promise<TrackingResult> {
  const body = formEncode({ awb, courier })

  const res = await fetch(`${BASE_URL}/track/waybill`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      key: API_KEY  // reuse existing auth
    },
    body
  })

  const data = await res.json()
  if (!res.ok) {
    const msg = data?.meta?.message || data?.message || `RajaOngkir tracking error: ${res.status}`
    throw new Error(msg)
  }

  const d = data.data || {}
  return {
    courier: d.courier || courier,
    awb: d.awb || awb,
    status: d.status || d.delivery_status || '',
    service: d.service || d.service_type || '',
    origin: d.origin || d.origin_name || '',
    destination: d.destination || d.destination_name || '',
    receiver: d.receiver || d.receiver_name || '',
    weight: d.weight || '',
    events: (d.history || d.manifest || []).map((e: any) => ({
      date: e.date || e.event_date || '',
      time: e.time || e.event_time || '',
      desc: e.desc || e.description || e.status || '',
      location: e.location || e.city || ''
    })),
    raw: d
  }
}
```

## 2. Proxy API endpoint: `src/routes/api/order/[id]/tracking/+server.ts`

```typescript
import { prisma } from '$lib/server/db'
import { trackWaybill } from '$lib/server/rajaongkir'
import { json } from '@sveltejs/kit'
import type { RequestHandler } from './$types'

export const GET: RequestHandler = async ({ params, locals }) => {
  const order = await prisma.order.findUnique({
    where: { id: params.id },
    select: { id: true, userId: true, trackingNumber: true, trackingCourier: true }
  })

  if (!order) return json({ error: 'Order not found' }, { status: 404 })

  // Ownership check
  if (order.userId && locals.user && order.userId !== locals.user.id) {
    return json({ error: 'Forbidden' }, { status: 403 })
  }

  if (!order.trackingNumber || !order.trackingCourier) {
    return json({ error: 'Tracking info not available yet' }, { status: 404 })
  }

  try {
    const tracking = await trackWaybill(order.trackingNumber, order.trackingCourier)
    return json(tracking)
  } catch (e: any) {
    return json({ error: e.message || 'Tracking failed' }, { status: 502 })
  }
}
```

## 3. Frontend: SvelteKit order page (`+page.svelte`)

### Script section

```svelte
<script lang="ts">
  let tracking = $state<{
    events: { date: string; time: string; desc: string; location: string }[]
    status: string
  } | null>(null)
  let trackingError = $state<string | null>(null)

  onMount(() => {
    // Fetch live tracking from RajaOngkir via proxy
    if (order.trackingNumber) {
      fetch(`/api/order/${order.id}/tracking`)
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(d => tracking = d)
        .catch(() => trackingError = 'Gagal memuat data tracking')
    }
  })
</script>
```

### Template — tracking timeline

```svelte
{#if order.trackingNumber}
<div class="border border-sand/50 rounded-lg p-6 mb-8 text-sm">
  <h2 class="font-medium mb-3">Tracking Pengiriman</h2>
  <div class="space-y-1 text-stone mb-4">
    <p>Kurir: <span class="font-medium text-charcoal">{order.trackingCourier || '-'}</span></p>
    <p>No. Resi: <span class="font-medium text-charcoal">{order.trackingNumber}</span></p>
  </div>

  {#if tracking?.events?.length}
    <div class="space-y-0">
      {#each tracking.events as event}
        <div class="flex gap-3 pb-3">
          <div class="flex flex-col items-center">
            <div class="w-2.5 h-2.5 rounded-full bg-terracotta mt-1"></div>
            <div class="w-px flex-1 bg-sand/60"></div>
          </div>
          <div class="text-sm pb-2">
            <p class="font-medium text-charcoal">{event.desc}</p>
            {#if event.location}
              <p class="text-stone text-xs mt-0.5">{event.location}</p>
            {/if}
            <p class="text-stone text-xs">{event.date} {event.time}</p>
          </div>
        </div>
      {/each}
    </div>
  {:else if trackingError}
    <p class="text-sm text-stone">{trackingError}</p>
  {:else if !tracking}
    <p class="text-sm text-stone animate-pulse">Memuat data tracking...</p>
  {:else}
    <p class="text-sm text-stone">Belum ada data tracking.</p>
  {/if}

  <!-- Fallback link to courier website -->
  <a href={trackingUrl(order.trackingCourier || 'jne', order.trackingNumber)}
     target="_blank" rel="noopener"
     class="inline-block mt-3 text-terracotta hover:underline text-sm">
    Lacak di website kurir ↗
  </a>
</div>
{/if}
```

### Helper function for courier URL fallback

```svelte
<script lang="ts">
  function trackingUrl(courier: string, trackingNumber: string): string {
    const c = courier.toLowerCase().trim()
    const urls: Record<string, string> = {
      jne: `https://www.jne.co.id/tracking/waybill/${trackingNumber}`,
      tiki: `https://www.tiki.id/tracking/${trackingNumber}`,
      pos: `https://www.posindonesia.co.id/tracking/${trackingNumber}`,
      sicepat: `https://www.sicepat.com/tracking/${trackingNumber}`,
      jnt: `https://www.jet.co.id/tracking/${trackingNumber}`,
      anteraja: `https://anter-aja.com/tracking/${trackingNumber}`,
      lion: `https://lionparcel.com/tracking/${trackingNumber}`,
    }
    return urls[c] || `https://rajaongkir.com/tracking/${trackingNumber}`
  }
</script>
```

## 4. Prisma schema — add tracking fields

```prisma
model Order {
  // ...existing fields...
  trackingNumber   String?
  trackingCourier  String?
  // ...rest of fields...
}
```

## 5. Admin — input form for tracking

### Action handler (`+page.server.ts`)

```typescript
export const actions: Actions = {
  updateTracking: async ({ request, params, locals }) => {
    requireAdmin(locals.user)
    const form = await request.formData()
    const trackingNumber = form.get('trackingNumber') as string || null
    const trackingCourier = form.get('trackingCourier') as string || null
    await prisma.order.update({
      where: { id: params.id },
      data: { trackingNumber, trackingCourier }
    })
    return { success: true }
  }
}
```

### Admin form template (`+page.svelte`)

```svelte
<div class="bg-white border border-sand/50 rounded-lg p-6 mt-6">
  <h2 class="font-medium mb-4">Tracking Pengiriman</h2>

  {#if order.trackingNumber}
    <div class="text-sm text-stone mb-4 space-y-1">
      <p>Kurir: <span class="font-medium text-charcoal">{order.trackingCourier || '-'}</span></p>
      <p>Resi: <span class="font-medium text-charcoal">{order.trackingNumber}</span></p>
    </div>
  {/if}

  <form method="POST" action="?/updateTracking" use:enhance class="flex flex-wrap items-end gap-3">
    <div class="flex-1 min-w-40">
      <label class="block text-sm font-medium mb-1">Kurir</label>
      <input name="trackingCourier" value={order.trackingCourier || ''}
             placeholder="JNE, SiCepat, J&T..."
             class="w-full px-3 py-2 border border-sand rounded text-sm">
    </div>
    <div class="flex-1 min-w-40">
      <label class="block text-sm font-medium mb-1">No. Resi</label>
      <input name="trackingNumber" value={order.trackingNumber || ''}
             placeholder="JP0123456789"
             class="w-full px-3 py-2 border border-sand rounded text-sm">
    </div>
    <button class="bg-charcoal text-white px-4 py-2 rounded text-sm hover:bg-stone transition whitespace-nowrap">
      Simpan Resi
    </button>
  </form>
</div>
```

## Pitfalls

- **Field name `awb` vs `waybill`**: The URL path is `/track/waybill` but the form field is `awb`. Wrong field name gives 422, not 404.
- **Form-encoded, not JSON**: Same POST body rule as cost endpoint (see main SKILL.md).
- **Invalid AWB returns 404, not 4xx**: `{"meta":{"message":"Invalid Awb","code":404,"status":"error"}}` — not an exception, handle gracefully.
- **`events` key varies**: `d.history` or `d.manifest` depending on courier. Always check both.
- **No test AWBs**: RajaOngkir Komerce API does not provide test waybills. Test with a real resi from an existing order or expect `Invalid Awb` for dummy numbers.
- **Containerized Prisma**: Schema changes need `docker cp` + `prisma db push` in running containers (no rebuild needed for schema-only changes).
- **Cache API calls**: Every order-page load calls RajaOngkir for tracking. Use in-memory cache (5 min TTL, 100 entries) to avoid burning API quota. See main SKILL.md "Tracking API caching" section.
