# Biteship API Key Behavior

## Test vs Live Keys

**Critical**: Biteship test keys (`biteship_test.xxx`) DO NOT work for REST API calls. They consistently return `401 Cannot process authorization`. The test environment is only accessible via Biteship's web dashboard, not via API.

**Always use a live/production key** (`biteship_live.xxx`), even during development. Biteship's free tier covers all testing needs.

## Free Tier Mapping

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /v1/couriers` | ✅ Free | 85+ Indonesian couriers |
| `GET /v1/maps/areas` | ✅ Free | Area IDs for rate lookup |
| `GET /v1/trackings/:awb` | ✅ Free | Per-resi tracking |
| `POST /v1/rates/couriers` | ❌ Needs balance | Ongkir calculation |

## VPS Reachability

- **Biteship**: Reachable from Singapore VPS — works normally ✅
- **RajaOngkir**: TCP timeout from Singapore VPS — geo-blocked ❌

This makes Biteship the preferred choice for Indonesian shipping APIs hosted on international VPS/Singapore DCs.

## Key Format

Biteship keys are JWTs:
- Test: `biteship_test.eyJ...` — claims `{name, userId, iat}`
- Live: `biteship_live.eyJ...` — claims `{name, userId, iat}`

Both share the same `userId` in the JWT payload.

## Tracking Page

Biteship provides a hosted tracking page at `https://track.biteship.com` that merchants can embed/link.
