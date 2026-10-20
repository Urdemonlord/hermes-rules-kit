# RajaOngkir v2 (Komerce) API — Shipping Cost

Base URL: `https://rajaongkir.komerce.id/api/v1`
Auth: `key: YOUR_API_KEY` header (same for all endpoints)

## Endpoints Used

### GET /destination/domestic-destination — City/Subdistrict Search

```
GET /api/v1/destination/domestic-destination?search=jakarta&limit=10&offset=0
```

Response format (v2, different from v1):
```json
{
  "meta": { "message": "Success Get Domestic Destinations", "code": 200, "status": "success" },
  "data": [
    {
      "id": 17473,
      "label": "GROGOL, GROGOL PETAMBURAN, JAKARTA BARAT, DKI JAKARTA, 11450",
      "province_name": "DKI JAKARTA",
      "city_name": "JAKARTA BARAT",
      "district_name": "GROGOL PETAMBURAN",
      "subdistrict_name": "GROGOL",
      "zip_code": "11450"
    }
  ]
}
```

**Mapping to v1-style interface:**
- `id` → number (use as string)
- `label` → `name`
- `province_name` → `province`
- `city_name` → `city`
- `district_name` → `district`
- `subdistrict_name` → `subdistrict`
- No `type` field — always `"subdistrict"`

### POST /calculate/domestic-cost — Cost Calculation

**CRITICAL: Form-encoded only. JSON returns Go validator errors.**

```
POST /api/v1/calculate/domestic-cost
Content-Type: application/x-www-form-urlencoded

origin=65205&destination=17473&weight=500&courier=jne
```

Response format:
```json
{
  "meta": { "message": "Success Calculate Domestic Shipping cost", "code": 200, "status": "success" },
  "data": [
    {
      "name": "Jalur Nugraha Ekakurir (JNE)",
      "code": "jne",
      "service": "REG",
      "description": "Layanan Reguler",
      "cost": 20000,
      "etd": "1 day"
    }
  ]
}
```

Note: `data` is a **flat array** of service options, not `{ origin, destination, costs: [] }`.

**Available couriers (v2):**
jne, tiki, pos, sicepat, jnt, anteraja, wahana, lion, grab, gosend

### Origin/Destination IDs

IDs are **subdistrict-level** integers. Example:
- `65205` = Pecangaan Kulon, Pecangaan, Jepara, Jawa Tengah, 59462
- `17473` = Grogol, Grogol Petamburan, Jakarta Barat, DKI Jakarta, 11450

### Form-encode helper (TypeScript)

```typescript
function formEncode(data: Record<string, string | number>): string {
  return Object.entries(data)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&')
}

const body = formEncode({ origin: '65205', destination: '17473', weight: 500, courier: 'jne' })
const res = await fetch(`${BASE}/calculate/domestic-cost`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded', key: API_KEY },
  body
})
```

### ETD normalization

The v2 API returns `etd` as "N day" or "N days" or "N-N days". Normalize to "N hari" or "N-N hari":
```typescript
etd: item.etd ? String(item.etd).replace(' day', '').replace(' days', '') + ' hari' : ''
```
