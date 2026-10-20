# Biteship Tracking with Fallback Chain

## Priority Order: Try Biteship First, Fall Through to Scraper + URL

When fetching tracking for a shipment, execute in this order. Stop at first success:

### 1. Biteship API (Primary)

**Endpoint:** `https://api.biteship.com/v1/trackings/{awb}`  
**Auth:** `Bearer {BITESHIP_API_KEY}`  
**Response:** JSON with `history` array + `status`

**Supports:** All major Indonesian couriers (JNE, J&T, TIKI, SiCepat, AnterAja, Ninja Van, Lion Parcel, ID Express, SAP Express, GoSend, GrabExpress)

**Failure modes:**
- Timeout (8s limit) → fallthrough
- 404 (AWB not found in Biteship) → fallthrough
- API error (500) → fallthrough
- Biteship key not configured → skip to scraper

### 2. Per-Courier Scraper (Secondary)

If Biteship fails, try the courier's own tracking API/page:

| Courier | Endpoint | Method | Notes |
|---------|----------|--------|-------|
| **JNE** | `https://cekresi.jne.co.id/{awb}/` | POST | HTML response, regex parse |
| **SiCepat** | `https://content-main-api-production.sicepat.com/public/check-awb/{awb}` | GET | JSON response |
| **AnterAja** | `https://anteraja.id/api/api/tracking/trackparcel/getTrackStatus` | POST body: `[{awb}]` | JSON response |

**Other couriers (J&T, TIKI, Ninja Van, Lion Parcel, etc.):** No known public API → skip to URL-only.

**Scraper failures:**
- Network error / timeout → fallthrough
- 404 or empty response → fallthrough

### 3. Tracking URL Only (Final Fallback)

Return just the link to the courier's tracking page. No live data, but user can click through.

| Courier | URL Template |
|---------|---|
| JNE | `https://www.jne.co.id/tracking/waybill/{awb}` |
| J&T | `https://www.jet.co.id/tracking/{awb}` |
| TIKI | `https://www.tiki.id/tracking/{awb}` |
| SiCepat | `https://www.sicepat.com/tracking/{awb}` |
| AnterAja | `https://anteraja.id/tracking/{awb}` |
| Ninja Van | `https://www.ninjavan.co/id-id/tracking?tracking_code={awb}` |
| Lion Parcel | `https://lionparcel.com/tracking/{awb}` |
| ID Express | `https://idexpress.com/tracking/{awb}` |
| SAP Express | `https://sap-express.id/tracking/{awb}` |
| GoSend | `https://www.gojek.com/` (no direct tracking) |
| GrabExpress | `https://www.grab.com/` (no direct tracking) |

**Response format:**
```typescript
{
  courier: 'JNE',
  awb: 'JP0123456789',
  status: 'unknown',
  origin: '',
  destination: '',
  events: [],  // no live data
  trackingUrl: 'https://www.jne.co.id/tracking/waybill/JP0123456789'
}
```

## Implementation

From `src/lib/server/courier-tracking.ts`:

```typescript
export async function trackShipment(awb: string, courier: string): Promise<TrackingResult> {
  // 1) Try Biteship API first
  const biteshipResult = await trackViaBiteship(awb, courier)
  if (biteshipResult) return biteshipResult

  // 2) Fallback: per-courier scraper
  const tracker = TRACKERS[courier.toLowerCase()]
  if (tracker) {
    try {
      return await tracker(awb)
    } catch (err: any) {
      console.warn(`[courier-tracking] ${courier.toUpperCase()} scraper failed: ${err.message}`)
    }
  }

  // 3) Final fallback: tracking URL link only
  return {
    courier: courier.toUpperCase(),
    awb,
    status: 'unknown',
    origin: '',
    destination: '',
    events: [],
    trackingUrl: getCourierTrackingUrl(courier, awb)
  }
}

async function trackViaBiteship(awb: string, courier: string): Promise<TrackingResult | null> {
  const BITESHIP_KEY = await getActiveBiteshipKey()
  if (!BITESHIP_KEY) return null

  try {
    const res = await fetch(`https://api.biteship.com/v1/trackings/${encodeURIComponent(awb)}`, {
      headers: {
        'Authorization': `Bearer ${BITESHIP_KEY}`,
        'Content-Type': 'application/json'
      },
      signal: AbortSignal.timeout(8000)
    })

    if (!res.ok) {
      console.warn(`[biteship-tracking] ${res.status} for ${courier}/${awb}`)
      return null
    }

    const json = await res.json()
    if (!json.success) return null

    const history = json.history || []
    const events = history.map((h: any) => ({
      date: h.updated_at?.split('T')[0] || h.date || '',
      time: h.updated_at?.split('T')[1]?.slice(0, 8) || h.time || '',
      desc: h.note || h.status || h.description || '',
      location: h.location || h.city || ''
    }))

    let status = 'in_transit'
    const currentStatus = (json.status || '').toLowerCase()
    if (currentStatus.includes('delivered') || currentStatus.includes('diterima')) status = 'delivered'
    else if (currentStatus.includes('pickup')) status = 'picked_up'
    else if (currentStatus.includes('return')) status = 'returned'

    return {
      courier: courier.toUpperCase(),
      awb,
      status,
      origin: json.origin || '',
      destination: json.destination || '',
      events,
      trackingUrl: getCourierTrackingUrl(courier, awb)
    }
  } catch (err: any) {
    console.warn(`[biteship-tracking] Error for ${courier}/${awb}: ${err.message}`)
    return null
  }
}
```

## When This Matters

- **Customer tracking page:** Always returns clickable link at minimum; live data if Biteship works
- **Admin tracking preview:** Shows latest 5 events if available; gracefully degrades to URL-only
- **Webhook integration:** Biteship sends webhook on state changes; use as fallback trigger to refresh admin preview

## Recommendation

Keep Biteship as primary because:
- Single unified API across all couriers
- Fast, reliable, well-documented
- If key misconfigured: scraper still works for JNE/SiCepat/AnterAja
- System never fully blocks tracking — worst case, user gets a link to the courier website
