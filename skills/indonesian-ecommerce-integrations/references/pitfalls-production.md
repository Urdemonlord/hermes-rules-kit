# Production Pitfalls — Indonesian E-Commerce

Lessons from deploying CLIENT-SITE (SvelteKit + Docker + Midtrans + Biteship + Resend).

## RajaOngkir Network Blocking

RajaOngkir blocks IPs from certain cloud providers (Huawei Cloud SG `129.226.x.x`) at the network level — TCP timeout, not API key whitelisting. Always test connectivity first:

```bash
timeout 5 curl -s -o /dev/null -w "%{http_code}" "https://api.rajaongkir.com/starter/province" -H "key: $KEY"
```

If blocked, migrate to **Biteship** (`api.biteship.com/v1`):
- `GET /maps/areas` — city search (free)
- `POST /rates/couriers` — shipping rates (needs balance)
- Flat-rate `flatRates(isJava, weightGrams)` fallback when balance empty

## Tracking: Never Simulate

**Do not generate mock tracking events.** The old `_simulated: true` pattern erodes trust. Instead:

1. Try real courier API (Biteship) first
2. On failure, return the courier's own tracking URL (JNE, J&T, etc.)
3. Customer gets real data from the source

```typescript
// Honest fallback
const result = {
  courier: 'JNE', awb: '1234567890',
  events: [],
  trackingUrl: 'https://www.jne.co.id/tracking/waybill/1234567890',
  message: 'Lacak langsung melalui halaman ekspedisi.'
}
```

## SvelteKit Rate Limiting

In-memory pattern for `$lib/server/ratelimit.ts`:
- `checkRateLimit(key, maxAttempts, windowMs): boolean`
- Cleanup interval every 5 min
- Apply to: login (5/15min/IP), forgot-password (3/15min/email), register (3/1hr/IP), order-lookup (10/1min/IP)

## Centralized Site Config

Indonesian storefronts hardcode URLs (Instagram, Tokopedia, Shopee, TikTok, WA, Maps, phone, address) across 7+ files. Centralize in `$lib/config.ts`:

```typescript
export const SITE = { name, tagline, description, domain }
export const CONTACT = { address, city, zip, phone, phoneRaw, email }
export const SOCIAL = { instagram, tokopedia, shopee, tiktok, whatsapp, googleMaps, googleMapsEmbed }
```

## Email Receipts

On Midtrans webhook `settlement`:
1. Fetch order items from DB
2. Extract email from order notes (guest checkout)
3. Fire-and-forget `sendOrderConfirmationEmail()` — don't block webhook

Newsletter subscribe should also fire a welcome email.

## Docker Optimization (SvelteKit)

Image ~3.9GB raw. Quick wins:
- `.dockerignore`: exclude `node_modules`, `.git`, `*.mov`, `.env*`
- `RUN npm prune --omit=dev` after build (~30% savings)
- Remove unconverted `.mov` files from static (71MB+ each)
- Result: ~1.1GB savings (3.9GB → 2.8GB)

## CSRF

SvelteKit has built-in CSRF via `checkOrigin`. Make it explicit:
```javascript
// svelte.config.js
kit: { csrf: { checkOrigin: true } }
```
