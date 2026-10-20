# Biteship API: Keys, Endpoints, and Pitfalls

## API Key Format

Biteship uses JWT-based API keys. All keys are JWT tokens with a type prefix:

| Prefix | Environment | JWT Claims |
|--------|------------|------------|
| `biteship_test.` | Test/Sandbox | `{name, userId, iat}` |
| `biteship_live.` | Production | `{name, userId, iat}` |

Both test and live keys have the same JWT structure. The test key prefix (`biteship_test.`) is what determines the mode — the Biteship `Authorization` header just needs `Bearer <full-key>`.

### Dashboard Key Confusion

Biteship dashboard may show both "Test" and "Production" tabs. The test tab gives a hex string like `6a63f0f55807773ba952d29c` — **this is NOT a valid API key**. It's a user ID reference. The actual API keys are the JWT tokens with `biteship_test.` or `biteship_live.` prefixes.

## Free vs Paid Endpoints

| Endpoint | Free? | Notes |
|----------|-------|-------|
| `GET /v1/couriers` | ✅ Free | Lists all available couriers (85+) |
| `GET /v1/maps/areas?countries=ID&input=...&type=single` | ✅ Free | Search cities/areas by name |
| `GET /v1/maps/areas?countries=ID&type=double` | ✅ Free | Get top-level areas (provinces) |
| `GET /v1/trackings/:awb` | ✅ Free | Track by AWB number (individual) |
| `GET /v1/trackings?status=...` | ❌ Admin only | Bulk tracking listing |
| `POST /v1/rates/couriers` | ❌ Needs balance | Calculate shipping rates |

**Key takeaway**: Couriers, maps, and individual tracking are free and work immediately. Rates require account balance/top-up.

## Tracking Endpoint Behavior

```
GET /v1/trackings/:awb
Authorization: Bearer <key>
```

- Real AWB → returns history with events
- Dummy/nonexistent AWB → returns `{"success": false, "error": "Failed to retrieve tracking number", "code": 40003001}`
- Invalid key → returns `401` with `"Cannot process authorization"`
- The endpoint does NOT need a courier parameter — Biteship auto-detects

## Rates Endpoint (Needs Balance)

```
POST /v1/rates/couriers
{
  "origin_area_id": "IDNP10IDNC157IDND1009IDZ59411",
  "destination_area_id": "IDNP6IDID0297NC100871",
  "couriers": "jne,jnt,sicepat",
  "items": [{"name": "Pesanan", "weight": 1000, "quantity": 1, "value": 150000}]
}
```

Without balance: `{"success": false, "error": "No sufficient balance to call rates API. Please top up your balance"}`

## Flat Rate Fallback Pattern

When Biteship rates fail (no balance), fall back to hardcoded flat rates:

```typescript
export function flatRates(destinationIsJava: boolean, weightGrams: number): BiteshipRate[] {
  const isHeavy = weightGrams > 1000
  if (destinationIsJava) {
    return [
      { courier: 'pos', cost: isHeavy ? 18000 : 10000, etd: '2-3 hari' },
      { courier: 'sicepat', cost: isHeavy ? 19000 : 12000, etd: '1-2 hari' },
      { courier: 'jnt', cost: isHeavy ? 20000 : 13000, etd: '1-2 hari' },
      { courier: 'anteraja', cost: isHeavy ? 21000 : 14000, etd: '1-2 hari' },
      { courier: 'jne', cost: isHeavy ? 22000 : 15000, etd: '1-2 hari' },
    ]
  }
  // Non-Java rates 2-3x higher
}
```

Origin default: Jepara, Jawa Tengah (`IDNP10IDNC157IDND1009IDZ59411`).

## From VPS Singapore

Biteship API is reachable from VPS Singapore (Cloudflare). Unlike RajaOngkir which times out from non-Indonesian IPs, Biteship works globally.

Tested: `curl https://api.biteship.com/v1/couriers` from SG VPS → 200 OK with valid key.
