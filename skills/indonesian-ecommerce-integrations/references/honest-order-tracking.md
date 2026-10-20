# Honest Order Tracking for Indonesian Couriers

Pattern for shipping tracking that NEVER fabricates data. Falls back to courier tracking URLs instead of generating fake events.

## Architecture

```
GET /api/order/[id]/tracking
  │
  ├─ Has trackingNumber?
  │   └─ NO → 200 { status, message: "belum tersedia", events: [] }
  │
  ├─ Cache hit? → return cached
  │
  ├─ Try Biteship API
  │   └─ SUCCESS → return real tracking + events
  │
  └─ Biteship failed
      └─ Return courier tracking URL (NO fake data)
```

## Courier Tracking URLs

```ts
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
  // Fallback for unknown couriers
  default: (awb, courier) => `https://www.google.com/search?q=resi+${courier}+${awb}`
}
```

## Honest Fallback Response

```json
{
  "courier": "JNE",
  "awb": "123456789012345",
  "status": "shipped",
  "events": [],
  "trackingUrl": "https://www.jne.co.id/tracking/waybill/123456789012345",
  "message": "Lacak langsung melalui halaman ekspedisi."
}
```

## Why This Matters

1. **Legal**: Fabricating tracking events ("Paket dalam perjalanan ke Jakarta") when no such data exists is deceptive to customers.
2. **Trust**: A customer who catches fake tracking will never trust the store again.
3. **Simplicity**: Redirecting to the courier's official tracking page is actually more useful than fake events — the courier's data is always the source of truth.

## Anti-Pattern (NEVER DO THIS)

```ts
// DO NOT generate fake tracking events
function generateMockTracking(order) {
  return {
    events: [
      { desc: "Paket diterima oleh JNE", location: "Jepara" },
      { desc: "Paket dalam perjalanan ke Jakarta", location: "Semarang" },
    ],
    _simulated: true  // <-- this flag doesn't make it OK
  }
}
```

## Cache Strategy

In-memory cache with 5-minute TTL, max 100 entries. Simple Map-based.

```ts
const cache = new Map<string, { data: any; ts: number }>()
const CACHE_TTL = 5 * 60 * 1000
const MAX_ENTRIES = 100
```

Cache key: `tracking:${orderId}:${trackingNumber}`
