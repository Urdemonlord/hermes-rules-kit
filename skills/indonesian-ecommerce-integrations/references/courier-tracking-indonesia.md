# Indonesian Courier Tracking — Scraper Architecture

## Pattern: per-courier scraper + URL fallback

Each courier gets its own scraping function. When scraping fails (endpoint changes, captcha, IP block), the system falls back to providing a direct tracking URL link.

```
trackShipment(awb, courier)
  → try TRACKERS[courier](awb)     // per-courier scraper
  → if fails: fallback tracking URL // always works, zero maintenance
```

## Known endpoints (from bardiz12/resi-scrapper, GitHub)

These endpoints are from an open-source PHP project. They change frequently — always test before deploying.

### JNE
- **Endpoint**: POST `https://cekresi.jne.co.id/{awb}/`
- **Headers**: Origin: `https://www.jne.co.id`, Referer: `https://www.jne.co.id/id/beranda`
- **Response**: HTML with tracking table
- **Status from VPS (2026-07-27)**: 302 redirect → 403 Forbidden. Endpoint appears deprecated.

### SiCepat
- **Endpoint**: GET `https://content-main-api-production.sicepat.com/public/check-awb/{awb}`
- **Headers**: Accept: application/json, Origin: `https://www.sicepat.com`
- **Response**: JSON `{ result: { history: [...] } }`
- **Status from VPS (2026-07-27)**: 502 Bad Gateway. DNS `content-main-api-production.sicepat.com` doesn't resolve from some VPS providers.

### AnterAja
- **Endpoint**: POST `https://anteraja.id/api/api/tracking/trackparcel/getTrackStatus`
- **Body**: `[{"awb": "..."}]` 
- **Headers**: Verification-Param: `aamunthe`, Referer: `https://anteraja.id/tracking`
- **Response**: JSON array
- **Status from VPS (2026-07-27)**: 404 Not Found. Endpoint may have moved.

### J&T, Pos Indonesia, TIKI
- No known public tracking API endpoints
- All use SPA frontends with internal (protected) APIs
- Best approach: provide direct tracking URL link

## Fallback tracking URLs

These are always available — just redirect the user to the courier's own page:

| Courier | URL Pattern |
|---------|------------|
| JNE | `https://www.jne.co.id/tracking/waybill/{awb}` |
| J&T | `https://www.jet.co.id/tracking/{awb}` |
| SiCepat | `https://www.sicepat.com/tracking/{awb}` |
| Pos Indonesia | `https://www.posindonesia.co.id/tracking/{awb}` |
| AnterAja | `https://anteraja.id/tracking/{awb}` |
| TIKI | `https://www.tiki.id/tracking/{awb}` |
| Lion Parcel | `https://lionparcel.com/tracking/{awb}` |
| Ninja Van | `https://www.ninjavan.co/id-id/tracking?tracking_code={awb}` |
| IDExpress | `https://idexpress.com/tracking/{awb}` |
| SAP Express | `https://sap-express.id/tracking/{awb}` |

## Key lesson

Indonesian courier tracking via scraping is **extremely fragile**. Endpoints change without notice, IPs get blocked, DNS shifts. The architecture MUST include the URL fallback — it's not just a backup, it's the primary reliable path for couriers without public APIs.

When a scraper endpoint breaks:
1. Check `bardiz12/resi-scrapper` or `cekresi-cli` on GitHub for updated endpoints
2. Test from the VPS before deploying
3. If no working endpoint exists, fall back to the tracking URL

## Reference implementations

- `bardiz12/resi-scrapper` (GitHub, PHP, 1 star) — JNE + SiCepat + AnterAja scrapers
- `cekresi-cli` (npm, JavaScript) — CLI tool for multi-courier tracking
- `Irvansbase/cek-resiku-tracking-app` (GitHub, Dart/Flutter) — uses BinderByte API
