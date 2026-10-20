# Local City List Fallback for RajaOngkir API Outage

When RajaOngkir (Komerce proxy or direct API) is rate-limited (429) or unreachable (TCP timeout), the city search autocomplete in the checkout form silently breaks. The user types a city name, the search returns nothing → user can't select a city → courier/shipping form never renders → checkout appears to have "missing fields."

This provides a hardcoded city list as a zero-API fallback.

## Pattern

1. **Create a static cities.json** with all Indonesian kabupaten/kota (~500 entries):

```json
[
  {"id":"202","name":"Kab. Jepara","type":"Kabupaten","province":"Jawa Tengah"},
  {"id":"225","name":"Kota Semarang","type":"Kota","province":"Jawa Tengah"},
  ...
]
```

2. **Rewrite the search endpoint** to use local data instead of API:

```typescript
// src/routes/api/ongkir/search/+server.ts
import citiesData from '$lib/data/cities.json'
import { json, error } from '@sveltejs/kit'
import type { RequestHandler } from './$types'

interface City { id: string; name: string; type: string; province: string }
const CITIES: City[] = citiesData as City[]

export const GET: RequestHandler = async ({ url }) => {
  const q = url.searchParams.get('q')
  if (!q || q.length < 2) throw error(400, 'Search query must be at least 2 characters')

  const query = q.toLowerCase().trim()
  const results = CITIES.filter(c =>
    c.name.toLowerCase().includes(query) ||
    c.province.toLowerCase().includes(query)
  ).slice(0, 15)

  return json({ data: results })
}
```

3. **Fix the checkout page mapping** — local names already include "Kab." / "Kota" prefix, so don't double-prefix with type:

```typescript
// BEFORE (Komerce API — name was bare, e.g. "Jepara"):
name: `${item.type} ${item.name}`  // "Kabupaten Jepara"

// AFTER (local data — name already has prefix, e.g. "Kab. Jepara"):
name: item.name  // just use as-is
```

## Pitfall: hidden `province` field + dead city API = "Field alamat tidak valid"

Symptom: checkout rejects with a generic "Field alamat tidak valid" even though every visible field is filled. All users affected, not one.

Root cause chain:
1. `province` is a `<input type="hidden">` populated only inside `selectCity()`.
2. The city autocomplete calls the live area-search API. When that API has no key (or is down), the search returns nothing → dropdown never renders → `selectCity()` never runs.
3. `province` submits as `""` → server zod `province: z.string().min(1)` fails → generic message that names no field.

Fixes (apply all three):
- **Fallback the search to the local `cities.json`** (see pattern above) so the dropdown always works — an empty API key must never brick checkout.
- **Make `province` a visible, required input** (`bind:value`, prefilled by `selectCity()` but editable) instead of hidden. A hidden required field is a trap: the user cannot fix it. Never gate a required field on a client-side picker that depends on a network call.
- **Name the missing fields in the error.** Map zod `issue.path[0]` to human labels and return `Mohon lengkapi: <field, ...>` instead of a blanket message.

Diagnostic shortcut: check whether the API key is actually present in the running container, not just in `.env` — `docker exec <app> sh -c 'for k in BITESHIP_API_KEY BITESHIP_API_KEY_TEST BITESHIP_API_KEY_LIVE; do eval v=\$$k; echo "$k len=${#v}"; done'`. Empty (`len=0`) means every city search 502s.

## Advantages

- Zero API calls — no rate limits, instant search
- Works offline during Komerce/RajaOngkir outages
- Searchable by both city name AND province
- Cost calculation still needs API (separate endpoint), but user can at least select a city

## Limitations

- Static list won't include newly created administrative regions
- Cost calculation endpoint still needs a live API (separate problem)
- IDs are arbitrary (not RajaOngkir subdistrict IDs), so cost calculation must handle ID mapping or use a different approach for the cost endpoint

## When to use

- Komerce proxy returns 429 "Daily limit exceeded"
- `api.rajaongkir.com` unreachable from VPS (TCP timeout)
- Temporary fallback while waiting for limit reset or API key upgrade
