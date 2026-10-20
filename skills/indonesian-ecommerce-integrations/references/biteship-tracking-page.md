# SvelteKit Public Tracking Page — Biteship Integration

Pattern for a customer-facing `/tracking` page with dual modes: order lookup (by ID/email/phone) and courier tracking (by AWB + carrier). Suitable for any Indonesian e-commerce SvelteKit storefront.

## Architecture

```
/tracking
  ├─ Tab 1: "Cek Pesanan" → GET /api/order/lookup?q=...
  │   └─ Order results (ID, status, total, date) → link to /order/[id]
  │
  ├─ Tab 2: "Lacak Resi" → POST /api/tracking/lookup { awb, courier }
  │   └─ Tracking timeline (events, status, location) via Biteship → scraper → URL fallback
  │
  └─ CTA: "Buka Biteship Tracking" → https://track.biteship.com
```

## File Structure

```
src/routes/
  tracking/
    +page.svelte          # Public tracking page (dual-tab)
  api/tracking/
    lookup/+server.ts     # POST endpoint — public, rate-limited
```

## API Endpoint: `POST /api/tracking/lookup`

No auth required. Rate-limited to 20 req/min/IP.

```typescript
// src/routes/api/tracking/lookup/+server.ts
import { json, error } from '@sveltejs/kit';
import { trackShipment } from '$lib/server/courier-tracking';
import { checkRateLimit } from '$lib/server/ratelimit';

export const POST: RequestHandler = async ({ request }) => {
  const ip = request.headers.get('x-forwarded-for') || '127.0.0.1';
  if (!checkRateLimit(`tracking-lookup:${ip}`, 20, 60 * 1000)) {
    throw error(429, 'Terlalu banyak permintaan.');
  }

  const { awb, courier } = await request.json();
  if (!awb || awb.trim().length < 3) throw error(400, 'Nomor resi minimal 3 karakter');
  if (!courier) throw error(400, 'Pilih kurir');

  const result = await trackShipment(awb.trim(), courier.toLowerCase().trim());
  return json(result);
};
```

## Page Component: `+page.svelte`

Key design decisions:

1. **Dual-tab toggle** — pill-style tabs for mode switching, no page reload
2. **Order lookup** uses existing `/api/order/lookup` endpoint (already has rate limiting)
3. **Courier tracking** uses new `/api/tracking/lookup` POST endpoint
4. **Courier dropdown** — 12 carriers (jne, jnt, tiki, pos, sicepat, anteraja, ninja, lion, idexpress, sap, gojek, grab)
5. **Timeline UI** — reuses the order detail page's tracking timeline pattern (numbered dots, connecting lines, icons)
6. **External link** — prominent CTA to `https://track.biteship.com` for complete tracking experience
7. **FAQ section** — 3 common questions at the bottom

### Couriers list

```typescript
const couriers = [
  { code: 'jne', name: 'JNE' },
  { code: 'jnt', name: 'J&T' },
  { code: 'tiki', name: 'TIKI' },
  { code: 'pos', name: 'POS Indonesia' },
  { code: 'sicepat', name: 'SiCepat' },
  { code: 'anteraja', name: 'AnterAja' },
  { code: 'ninja', name: 'Ninja Van' },
  { code: 'lion', name: 'Lion Parcel' },
  { code: 'idexpress', name: 'ID Express' },
  { code: 'sap', name: 'SAP Express' },
  { code: 'gojek', name: 'GoSend' },
  { code: 'grab', name: 'GrabExpress' },
];
```

### Nav Header Update

Replace or add "Lacak" link pointing to `/tracking`:

```svelte
<!-- src/lib/components/layout/Header.svelte -->
<a href="/tracking" class={navClass('/tracking')}>Lacak</a>
```

## Verification Checklist

```bash
# Page loads
curl -s -o /dev/null -w "%{http_code}" https://domain.com/tracking

# Order lookup works
curl -s "https://domain.com/api/order/lookup?q=test" | python3 -m json.tool

# Tracking lookup works (Biteship)
curl -s -X POST https://domain.com/api/tracking/lookup \
  -H "Content-Type: application/json" \
  -d '{"awb":"REAL_AWB","courier":"jne"}'

# Biteship reachable from inside container
docker exec <container> node -e "
fetch('https://api.biteship.com/v1/couriers', {
  headers: { 'Authorization': 'Bearer ' + process.env.BITESHIP_API_KEY }
}).then(r => r.json()).then(d => console.log('couriers:', d.couriers?.length))
"
```

## Pitfalls

1. **Don't embed Biteship's page in iframe** — it may have X-Frame-Options. Link to it instead.
2. **The tracking API uses `trackShipment()` directly** — same module used by the order detail tracking. Keep the 5-min cache in the order detail endpoint but NOT in the public lookup (fresh data expectations differ).
3. **Courier dropdown must match Biteship's courier codes** — not display names. Biteship returns 85+ couriers but the common ones are the 12 listed above.
4. **No auth on the lookup API** — it's public. Rate limit is the only protection.
