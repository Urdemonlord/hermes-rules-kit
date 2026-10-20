# Biteship Shipping API

Biteship is an Indonesian shipping aggregator API — covers JNE, J&T, SiCepat, AnterAja, Pos Indonesia, and more. Good alternative when Komerce/RajaOngkir is rate-limited or unreachable.

## Quick Reference

| Resource | URL |
|----------|-----|
| Base URL | `https://api.biteship.com/v1` |
| Auth | `Authorization: Bearer <api_key>` |
| Key format | Production: JWT (`biteship_live.eyJhbGciOiJIUzI1NiJ9.ey...`). Test/Sandbox: either short hex (`6a63f0...`) OR JWT (`biteship_test.eyJ...`) — **test keys never work for API calls regardless of format** |
| npm package | `biteship` (0.0.0) is a placeholder — **do not install**. Call the REST API directly. |
| Free tier | ~1000-5000 req/month, all features included — no separate sandbox |

## Environment — test key vs production key (critical pitfall)

Biteship dashboard has **two key types**:

| Key Type | Tab | API Calls | Dashboard |
|----------|-----|-----------|-----------|
| **Test/Sandbox** | "Sandbox" / "Testing" | ❌ **Always 401** | ✅ Works |
| **Production** | "Production" | ✅ Works | ✅ Works |

**The test key exists but only works inside the dashboard (web app). It CANNOT make API calls.** If you try the test key against `api.biteship.com`, you will get `40101003` "Cannot process authorization" — this is normal behavior, not a broken key.

**Key format differences:**
- Test keys: short hex strings (e.g. `6a63f0f55807773ba952d29c`)
- Production keys: longer strings, may start with `biteship_live_` prefix

**When user gives you a key that looks like a test key:**
1. Test it ONCE against `/v1/couriers` — if 401, it's a test key, not a bad key
2. Tell the user directly: "Ini test key — nggak bisa buat API call. Pake production key dari dashboard."
3. Do NOT test with dummy keys (e.g. `"test"`) before trying the user's actual key — that comes across as dismissive
4. Do NOT question where the user got the key

Biteship **does not have a separate sandbox URL** — same `api.biteship.com` for all keys. The free tier is the testing tier. Use a production key and stay within free tier limits for development.

## VPS Geo-Accessibility

| Provider | From SG VPS | Error Mode |
|----------|------------|------------|
| Biteship | ✅ Reachable | Returns proper HTTP errors (401/402) |
| RajaOngkir | ❌ Blocked | TCP timeout — geo-block, not auth failure |

This means: **if you're on a Singapore VPS, Biteship works. RajaOngkir doesn't.** Don't bother with RajaOngkir proxies — switch to Biteship.

## 401 Error ≠ Fake Key — don't test with dummy keys

A 401 from Biteship can mean:
- Account not yet verified (check email)
- **Test key from Sandbox tab** — doesn't work for API calls, production key needed
- Key from wrong tab (Sandbox vs Production in dashboard)
- Key not yet active (wait a few minutes after creation)
- IP whitelist enabled (check dashboard settings)

**Pitfall — testing with dummy keys (e.g. `Authorization: Bearer test`):**
When a user gives you an API key, test the USER'S KEY first. Do NOT run a "control" test with a dummy key like `"test"` before trying the real key. This reads as dismissive ("let me check if your key even exists") and the user already told you where the key came from.

**Correct sequencing:**
1. Test user's actual key → if 401, identify why (test key? unverified? wrong tab?)
2. If needed, suggest user checks dashboard for production key
3. NEVER: test with `"test"` first → "dummy ndasmu" response

**Never** dismiss a user's key as "dummy" or "invalid" based on 401 alone. Test from local machine to isolate VPS vs key issues.

## Available Endpoints

| Endpoint | Method | Purpose | Needs Balance? |
|----------|--------|---------|---------------|
| `/maps/areas` | GET | Search cities/districts | **No** (free) |
| `/rates/couriers` | POST | Calculate shipping cost | **Yes** |
| `/trackings/:awb/couriers/:courier` | GET | Track shipment | **Yes** |

**Only `/maps/areas` is truly free.** Both `/rates/couriers` and `/trackings` return `"No sufficient balance to call rates/tracking API. Please top up your balance"` when the wallet is empty — even with an active, valid API key. The "free tier" (1,000-5,000 requests/month) covers area search only; rates and tracking deduct from balance.

## Quick Connectivity Test

```bash
# Biteship reachable from SG VPS → returns 401 (auth required, not timeout)
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://api.biteship.com/v1/maps/areas"

# RajaOngkir from SG VPS → TCP timeout (geo-blocked)
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://api.rajaongkir.com/starter/province"
```

## Area Search (`/maps/areas`) — FREE

```bash
curl "https://api.biteship.com/v1/maps/areas?countries=ID&input=jepara&type=single" \
  -H "Authorization: Bearer YOUR_KEY"
```

**Response:**
```json
{
  "success": true,
  "areas": [{
    "id": "IDNP10IDNC157IDND1009IDZ59411",
    "name": "Jepara, Jepara, Jawa Tengah. 59411",
    "administrative_division_level_1_name": "Jawa Tengah",
    "administrative_division_level_2_name": "Jepara",
    "administrative_division_level_3_name": "Jepara",
    "postal_code": 59411
  }]
}
```

## Rates (`/rates/couriers`) — NEEDS BALANCE

```bash
curl -X POST "https://api.biteship.com/v1/rates/couriers" \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_area_id": "IDNP10IDNC157IDND1009IDZ59411",
    "destination_area_id": "IDNP04IDNC5013IDND5026IDZ12950",
    "couriers": "jne,jnt,sicepat,anteraja",
    "items": [{"name":"Kain Tenun","weight":500,"quantity":1,"value":150000}]
  }'
```

**Error without balance:**
```json
{"success": false, "error": "No sufficient balance to call rates API. Please top up your balance"}
```

## Tracking (`/trackings`) — REQUIRES BALANCE

**Single AWB tracking:**

```bash
curl "https://api.biteship.com/v1/trackings/JP0123456789/couriers/jne" \
  -H "Authorization: Bearer YOUR_KEY"
```

Requires `courier` code in the URL path. Without balance returns: `"No sufficient balance to call tracking API. Please top up your balance"`.

**Implementation pattern — hybrid Biteship + scraper + URL fallback:**

```typescript
// Priority: Biteship API → per-courier scraper → tracking URL link
export async function trackShipment(awb: string, courier: string): Promise<TrackingResult> {
  // 1) Try Biteship first (requires balance, reliable from SG VPS)
  const biteship = await trackViaBiteship(awb, courier)
  if (biteship) return biteship

  // 2) Fallback: per-courier scraper (JNE, SiCepat, AnterAja)
  const tracker = TRACKERS[courier.toLowerCase()]
  if (tracker) {
    try { return await tracker(awb) } catch {}
  }

  // 3) Final: bare tracking URL link
  return { trackingUrl: getCourierTrackingUrl(courier, awb), events: [] }
}
```

The Biteship tracker uses `fetch()` with 8-second timeout and returns `null` on failure so it degrades gracefully.

### Biteship Hosted Tracking Page

Biteship provides a hosted tracking page at **`https://track.biteship.com`** that merchants can link to or embed. This is Biteship's own white-label tracking experience — customer enters their AWB and sees the full timeline without visiting the courier's site.

**Use cases:**
- Quick public tracking link for customers without an account
- Embed in order confirmation emails
- Supplement the custom `/tracking` page on your storefront

**Integration:**
```html
<a href="https://track.biteship.com" target="_blank" rel="noopener">
  🚚 Lacak Paket
</a>
```

The page can be customized per merchant in the Biteship dashboard under "Tracking Page" settings.

**Full SvelteKit `/tracking` page implementation:** see `references/biteship-tracking-page.md` — dual-tab page (order lookup + public courier tracking) with public `POST /api/tracking/lookup` endpoint.

### Tracking API caching (same pattern as RajaOngkir)

Use in-memory Map with TTL to avoid burning API quota on page refreshes:

```typescript
const cache = new Map<string, { data: any; ts: number }>()
const CACHE_TTL = 5 * 60 * 1000  // 5 min
const MAX_ENTRIES = 100
```

Key: `tracking:${orderId}:${trackingNumber}`.

## TypeScript Module (`src/lib/server/biteship.ts`)

Core exports:

| Function | Returns | Purpose |
|----------|---------|---------|
| `searchAreas(query)` | `BiteshipArea[]` | Free area search |
| `calculateRates(origin, dest, weight, value, couriers?)` | `BiteshipRate[]` | Real-time rates |
| `trackShipment(awb, courier)` | `BiteshipTrackingResult` | Shipment tracking |
| `flatRates(province, weight)` | `BiteshipRate[]` | Zone-based fallback estimates (5 zones) |
| `provinceToZone(province)` | `number` | Classify province into shipping zone 1-5 |

**For the zone-based flat rate system (5 zones, 4 weight tiers, courier multipliers), see:** `references/biteship-zones-flatrates.md`

## Flat Rate Fallback — When Biteship Has No Balance

**See `references/biteship-zones-flatrates.md` for the full 5-zone, 4-weight-tier system with courier multipliers.** The zone-based approach is significantly more accurate than the old 2-zone Java/non-Java binary (e.g., Papua 2kg: 110K zone-based vs 55K old — old was 50% under).

Quick summary:

| Zone | Provinces | 1kg base (JNE) | ETD |
|------|-----------|----------------|-----|
| 1 | Java, Bali | 15K | 1-2 hari |
| 2 | Sumatra (non-Aceh) | 28K | 2-3 hari |
| 3 | Kalimantan, Sulawesi | 45K | 4-6 hari |
| 4 | Aceh, NTT, NTB | 58K | 5-7 hari |
| 5 | Maluku, Papua | 82K | 7-14 hari |

**Implementation pattern:** Frontend sends `destinationProvince` from Biteship `/maps/areas` response. Backend tries Biteship rates first, falls back to `flatRates(province, weight)` which classifies province into zone and applies weight-tier pricing + courier multipliers. Unknown provinces default to Zone 3 (conservative middle).

## Migration from Komerce RajaOngkir to Biteship

Checklist (in order):

1. Add `BITESHIP_API_KEY` to `.env` and `compose.yaml`
2. Create `src/lib/server/biteship.ts` (full module — area search, rates, tracking, flat rates)
3. Update `/api/ongkir/cost/+server.ts`: try Biteship first, fall back to flat rates
4. Update `/api/order/[id]/tracking/+server.ts`: replace `trackWaybill()` (Komerce) with `trackShipment()` (Biteship)
5. Update `/api/order/[id]/status/+server.ts`: replace Komerce `getPaymentStatus()` with Midtrans `getTransactionStatus()`
6. Update `/order/[id]/+page.server.ts`: remove Komerce `paymentDetails` fetch
7. Delete `/api/kommerce/webhook/` directory
8. Delete `src/lib/server/kommerce-payment.ts` and `src/lib/server/rajaongkir.ts`
9. Remove Komerce env vars from `compose.yaml` and `.env`:
   - `KOMMERCE_PAYMENT_KEY`
   - `KOMMERCE_PAYMENT_PRODUCTION`
   - `KOMMERCE_WEBHOOK_SECRET`
10. Clean Komerce URLs from CSP in `hooks.server.ts`:
    - Remove `rajaongkir.komerce.id`, `api-sandbox.collaborator.komerce.id`, `pay-sandbox.komerce.my.id`
    - Add `api.biteship.com`
11. Update checkout page to pass `destinationProvince` to cost endpoint

## Environment Variables

Add to `compose.yaml`:
```yaml
- BITESHIP_API_KEY=${BITESHIP_API_KEY}
```

Add to `.env`:
```
BITESHIP_API_KEY=biteship_live.eyJhbGciOiJIUzI1NiJ9.ey...
```

Add to CSP in `hooks.server.ts`:
```
connect-src ... https://api.biteship.com
```
