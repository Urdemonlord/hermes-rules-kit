# RajaOngkir API — VPS Connectivity & Integration

## API endpoint

Base URL: `https://api.rajaongkir.com/starter` (resolves to `203.0.113.10`, DigitalOcean)

Auth: `key` header with API key

Endpoints used:
- `GET /city?id=<id>` — get city by ID
- `GET /city?city=<query>` — search cities
- `POST /cost` — calculate shipping (form-encoded: `origin`, `destination`, `weight`, `courier`)

## Common connectivity problem

`api.rajaongkir.com:443` may be **unreachable from certain VPS IPs** — connection timeout at the network level. Symptoms:

```bash
curl -sv --connect-timeout 10 "https://api.rajaongkir.com/starter/" -H "key: ..."
# * Trying 203.0.113.10:443...
# * connect timeout after 9997ms, move on!
# * Failed to connect — Timeout was reached
```

Root cause: RajaOngkir's DigitalOcean-hosted server blocks specific IP ranges at the infrastructure firewall level, independent of the dashboard IP whitelist. Adding the VPS IP to the RajaOngkir dashboard whitelist doesn't resolve network-level blocking.

Diagnostic: use `check-host.net` to confirm the server is up from other locations:

```bash
curl -s "https://check-host.net/check-http?host=api.rajaongkir.com&port=443"
# If "ok" from other locations but timeout from your VPS → network-level block
```

## Integration code

### `src/lib/server/rajaongkir.ts`

Full API client supporting city search and cost calculation. Key structure:

```typescript
const BASE_URL = 'https://api.rajaongkir.com/starter'

function headers(): Record<string, string> {
  return { key: RAJAONGKIR_KEY }
}

export async function searchCities(query: string): Promise<RajaOngkirCity[]>
export async function calculateCost(origin, destination, weightGrams, couriers?): Promise<RajaOngkirCost[]>
```

### City IDs

- Jepara: `205` (default origin for iki-tenun)
- Jakarta Pusat: `154`

### Couriers supported

`jne`, `pos`, `tiki`, `jnt`, `sicepat`, `anteraja`, `ninja`, `lion`, `idexpress`, `sap`

## Fallback strategy

When RajaOngkir is unreachable, fall back to:
1. **Biteship** — real-time rates from another provider (requires funded balance)
2. **Flat rate** — estimated rates by island (Java vs luar Jawa), stored in `biteship.ts:flatRates()`
