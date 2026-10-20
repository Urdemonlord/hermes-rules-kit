# Indonesian Courier Tracking — Reality Check

## No Public Tracking APIs

Indonesian couriers do NOT expose public tracking APIs. All tracking pages are SPAs behind Cloudflare with client-side rendering. Direct scraping is NOT feasible and will break within weeks.

| Courier | Tracking URL | Scraping Feasibility |
|---------|-------------|---------------------|
| JNE | `jne.co.id/tracking/waybill/{resi}` | Cloudflare-protected, internal API hidden behind auth/captcha |
| J&T | `jet.co.id/tracking/{resi}` | Pure SPA — every URL returns identical HTML shell, no exposed API |
| SiCepat | `sicepat.com/tracking/{resi}` | Cloudflare, DNS may not resolve from foreign VPS |
| Pos Indonesia | `posindonesia.co.id/tracking/{resi}` | Timeout from non-Indonesian VPS |
| AnterAja | `anteraja.id/tracking/{resi}` | SPA, no API endpoints |

Tested from Alibaba Cloud Singapore VPS (129.226.193.x), July 2026. All attempts to find internal APIs returned 404, SPA HTML, or timed out.

## Workable Solutions

### 1. Biteship (Recommended)

`api.biteship.com/v1` — the only reliable API aggregator for Indonesian couriers:
- **Tracking**: `GET /v1/trackings/{awb}/couriers/{courier}` — structured JSON with full event history
- **Rates**: `POST /v1/rates/couriers` — real-time pricing from JNE, J&T, SiCepat, AnterAja, Pos
- **Areas**: `GET /v1/maps/areas?countries=ID` — free city/district search

Cost: ~Rp 1,000/tracking call. Requires funded balance.

### 2. Honest Fallback — Courier Links

When Biteship is unavailable, provide the courier's direct tracking URL. The user clicks to open in a new tab. Zero maintenance, never breaks:

```typescript
const COURIER_TRACKING_URLS: Record<string, (awb: string) => string> = {
  jne: (awb) => `https://www.jne.co.id/tracking/waybill/${awb}`,
  jnt: (awb) => `https://www.jet.co.id/tracking/${awb}`,
  sicepat: (awb) => `https://www.sicepat.com/tracking/${awb}`,
  pos: (awb) => `https://www.posindonesia.co.id/tracking/${awb}`,
  anteraja: (awb) => `https://anteraja.id/tracking/${awb}`,
}
```

Return JSON with empty events array and a message:
```json
{
  "courier": "JNE",
  "awb": "JP0123456789",
  "status": "shipped",
  "events": [],
  "trackingUrl": "https://www.jne.co.id/tracking/waybill/JP0123456789",
  "message": "Lacak langsung melalui halaman ekspedisi."
}
```

**Never generate mock/fake tracking events.** Fake data erodes user trust. An honest "click here to track" link is always better than fabricated events.

## RajaOngkir VPS Accessibility

`api.rajaongkir.com` (203.0.113.10, DigitalOcean Singapore) may be unreachable from certain VPS providers. Observed: TCP timeout from Alibaba Cloud Singapore. DNS resolves but handshake times out.

**Always test connectivity before building RajaOngkir integration:**
```bash
curl -v --max-time 5 "https://api.rajaongkir.com/starter/province" -H "key: YOUR_KEY"
```
