# RajaOngkir → Biteship Migration Pattern

## Problem
RajaOngkir API (`api.rajaongkir.com`, IP `203.0.113.10`) blocks certain VPS IP ranges at the network level. The symptom is TCP timeout — not an API whitelist issue. No amount of API key config will fix it. This has been confirmed on Huawei Cloud Singapore VPS (`203.0.113.10`).

## Solution: Biteship
Biteship (`api.biteship.com`) is a modern alternative that works from blocked VPS IPs:
- **Maps API** (free, no balance needed): `/v1/maps/areas` — search cities/districts
- **Rates API** (requires funded balance): `/v1/rates/couriers` — calculate shipping costs
- **Tracking API** (requires balance): `/v1/trackings` — real-time shipment tracking

## Migration Steps

### 1. Search endpoint (FREE tier works immediately)
```typescript
// Old: RajaOngkir (blocked)
import { searchCities } from '$lib/server/rajaongkir'
export const GET = async ({ url }) => {
  const cities = await searchCities(q)
  return json({ data: cities })
}

// New: Biteship (works, free)
import { searchAreas } from '$lib/server/biteship'
export const GET = async ({ url }) => {
  const areas = await searchAreas(q)
  return json({ data: areas })
}
```

### 2. Cost endpoint (needs balance, with flat-rate fallback)
```typescript
import { calculateRates, flatRates } from '$lib/server/biteship'

export const POST = async ({ request }) => {
  try {
    const rates = await calculateRates(originAreaId, destinationAreaId, weight, value)
    return json({ data: rates })
  } catch {
    // Fallback to flat rates when Biteship has no balance
    const rates = flatRates(isJava, weight)
    return json({ data: rates, fallback: true })
  }
}
```

### 3. Tracking (real API + honest fallback — NO fake data)
```typescript
export const GET = async ({ params }) => {
  // If no tracking number yet, return honest status
  if (!order.trackingNumber) {
    return json({ status: order.status, message: 'Resi belum tersedia', events: [] })
  }
  // Try Biteship
  try {
    const tracking = await trackShipment(order.trackingNumber, order.trackingCourier)
    return json({ ...tracking, trackingUrl: getCourierTrackingUrl(...) })
  } catch {
    // Fallback: link to courier's own tracking page. NO simulated events.
    return json({
      courier: order.trackingCourier,
      awb: order.trackingNumber,
      events: [],
      trackingUrl: getCourierTrackingUrl(...),
      message: 'Lacak langsung melalui halaman ekspedisi.'
    })
  }
}
```

## Key Rules
- **Never generate fake tracking events.** If API fails, give user the courier's tracking URL.
- **Flat rates** are acceptable fallback when Biteship balance is empty — be transparent with a `fallback: true` flag.
- Biteship area IDs are long strings (not numeric like RajaOngkir) — adjust frontend accordingly.
- Cache tracking responses (5 min TTL) to avoid hitting rate limits.
