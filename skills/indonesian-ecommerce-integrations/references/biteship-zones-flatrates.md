## Biteship Free Tier Reality

| Endpoint | Free? | Notes |
|----------|-------|-------|
| `/maps/areas` (city search) | ✅ Free | No balance needed |
| `/rates/couriers` (ongkir) | ❌ | Returns `"No sufficient balance to call rates API. Please top up your balance"` |
| `/trackings` (resi/tracking) | ❌ | Same balance requirement |

Key insight: even in "test mode" with an active test key, Biteship requires a funded account balance for rates and tracking. The "free tier" gives you 1,000-5,000 API calls but all rate/tracking calls deduct from balance. Minimum top-up is ~Rp 50,000.

## Zone-Based Flat Rate Fallback

When Biteship has no balance, use a 5-zone province-based estimation instead of a naive Java/non-Java binary.

### Zone Classification

| Zone | Provinces | ETD |
|------|-----------|-----|
| 1 | Java (DKI Jakarta, Jawa Barat, Jawa Tengah, Jawa Timur, DIY, Banten), Bali | 1-2 hari |
| 2 | Sumatra (Semua kecuali Aceh), Bangka Belitung | 2-3 hari |
| 3 | Kalimantan, Sulawesi | 4-6 hari |
| 4 | Aceh, NTT, NTB | 5-7 hari |
| 5 | Maluku, Papua | 7-14 hari |

### Base Prices (JNE REG benchmark, per weight tier)

| Zone | ≤500g | ≤1kg | ≤2kg | ≤5kg | >5kg surcharge/kg |
|------|-------|------|------|------|-------------------|
| 1 | 12,000 | 15,000 | 22,000 | 38,000 | 8,000 |
| 2 | 22,000 | 28,000 | 42,000 | 65,000 | 10,000 |
| 3 | 35,000 | 45,000 | 65,000 | 100,000 | 14,000 |
| 4 | 45,000 | 58,000 | 80,000 | 125,000 | 16,000 |
| 5 | 65,000 | 82,000 | 110,000 | 180,000 | 20,000 |

### Courier Multipliers (relative to JNE base)

| Courier | Multiplier |
|---------|-----------|
| SiCepat | 0.85 |
| AnterAja | 0.88 |
| J&T | 0.90 |
| Pos Indonesia | 0.95 |
| JNE | 1.00 |

Rates sorted cheapest first. Round costs with `Math.round()`.

### Implementation Pattern (SvelteKit)

**Frontend** sends `destinationProvince` from Biteship `/maps/areas` response alongside the area ID:

```ts
// +page.svelte — fetchCosts()
body: JSON.stringify({
  originAreaId: 'IDNP10IDNC157IDND1009IDZ59411',  // Jepara
  destinationAreaId: destinationId,
  weight: cartWeight,
  destinationProvince: selectedProvince  // from Biteship area search
})
```

**Backend** tries Biteship first, falls back to zone-based:

```ts
// /api/ongkir/cost/+server.ts
try {
  const rates = await calculateRates(originAreaId, destinationAreaId, weight, value, couriers)
  return json({ data: rates })
} catch (e) {
  console.warn('[ongkir] Biteship rates failed, using zone flat rates:', e?.message)
}
// Fallback
const rates = flatRates(destinationProvince || '', weight)
return json({ data: rates, fallback: true, message: 'Estimasi ongkir. Akurat setelah konfirmasi.' })
```

### Province Matching

Use substring match on lowercase province name. Biteship returns province as `administrative_division_level_1_name` with values like `"DKI Jakarta"`, `"Sumatera Selatan"`, `"Papua"`. Unknown provinces default to Zone 3 (conservative middle).

## Common Pitfalls

### Parameter Mismatch: originId vs originAreaId

Frontend might send `originId`/`destinationId` while backend expects `originAreaId`/`destinationAreaId`. This causes silent failures — no shipping options appear. Verify parameter names match exactly between frontend body and backend destructuring.

### Hardcoded Java Fallback

Before zone-based, the fallback was `flatRates(true, weight)` — always using Java rates regardless of destination. This made Papua shipping massively undercharged. Always pass the actual province.
