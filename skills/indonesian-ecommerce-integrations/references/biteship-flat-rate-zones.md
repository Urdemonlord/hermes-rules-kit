# Biteship Flat Rate Fallback — Zone-Based Estimation

When Biteship `/rates/couriers` returns `"No sufficient balance"` (even with test key), fall back to zone-based flat rates using province info from free `/maps/areas`.

## Biteship Free Tier Reality

| Endpoint | Free? |
|----------|-------|
| `/maps/areas` (city search) | ✅ Free |
| `/rates/couriers` (ongkir) | ❌ Needs balance |
| `/trackings` (resi) | ❌ Needs balance |

Test/sandbox keys authenticate but still need balance for rates + tracking.

## Zone-Based Flat Rate Implementation

### 5 Shipping Zones (Origin: Jepara, Jawa Tengah)

| Zone | Provinces | Base 500g | Base 1kg | Base 2kg | Base 5kg |
|------|-----------|-----------|----------|----------|----------|
| 1 | DKI, Jabar, Jateng, Jatim, DIY, Banten, Bali | 12,000 | 15,000 | 22,000 | 38,000 |
| 2 | Sumsel, Sumbar, Lampung, Bengkulu, Jambi, Riau, Kepri, Sumut, Bangka | 22,000 | 28,000 | 42,000 | 65,000 |
| 3 | Kalimantan, Sulawesi (all provinces) | 35,000 | 45,000 | 65,000 | 100,000 |
| 4 | Aceh, NTT, NTB | 45,000 | 58,000 | 80,000 | 125,000 |
| 5 | Maluku, Papua (all) | 65,000 | 82,000 | 110,000 | 180,000 |

### Weight Tiers
- ≤500g → base500
- ≤1kg → base1k
- ≤2kg → base2k
- ≤5kg → base5k
- >5kg → base5k + per-kg surcharge (8k Zone 1 → 20k Zone 5)

### Courier Multipliers (relative to JNE REG base)

| Courier | Multiplier |
|---------|-----------|
| JNE REG | 1.00 |
| J&T EZ | 0.90 |
| SiCepat REG | 0.85 |
| AnterAja REG | 0.88 |
| Pos Indonesia REG | 0.95 |

### ETD Per Zone

| Zone | ETD |
|------|-----|
| 1 | 1-2 hari |
| 2 | 2-3 hari |
| 3 | 4-6 hari |
| 4 | 5-7 hari |
| 5 | 7-14 hari |

## Province → Zone Mapping

```typescript
const ZONE_MAP: Array<[string[], number]> = [
  [['DKI Jakarta', 'Jawa Barat', 'Jawa Tengah', 'Jawa Timur', 'DI Yogyakarta', 'Banten', 'Bali'], 1],
  [['Sumatera Selatan', 'Sumatera Barat', 'Lampung', 'Bengkulu', 'Jambi', 'Riau', 'Kepulauan Riau', 'Sumatera Utara', 'Kepulauan Bangka Belitung', 'Bangka Belitung'], 2],
  [['Kalimantan Barat', 'Kalimantan Tengah', 'Kalimantan Selatan', 'Kalimantan Timur', 'Kalimantan Utara', 'Sulawesi Selatan', 'Sulawesi Tengah', 'Sulawesi Tenggara', 'Sulawesi Utara', 'Gorontalo', 'Sulawesi Barat'], 3],
  [['Aceh', 'Nusa Tenggara Timur', 'Nusa Tenggara Barat'], 4],
  [['Maluku', 'Maluku Utara', 'Papua', 'Papua Barat', 'Papua Selatan', 'Papua Tengah', 'Papua Pegunungan', 'Papua Barat Daya'], 5],
]
```

Use `province.toLowerCase().includes(name.toLowerCase())` for fuzzy matching against Biteship `/maps/areas` province strings. Unknown provinces default to Zone 3 (Kalimantan/Sulawesi) as conservative middle.

## Workflow

1. Frontend sends `destinationProvince` from `/maps/areas` search result (free)
2. Backend tries Biteship `/rates/couriers` first
3. If error (no balance) → fallback to zone-based `flatRates(province, weightGrams)`
4. Return `{ data: rates, fallback: true, message: 'Estimasi ongkir. Akurat setelah konfirmasi.' }`

## Accuracy

- Old binary (Java/non-Java): ±50% error
- Zone-based (5 zones): ±15-20% error — good enough for estimation until balance topped up
