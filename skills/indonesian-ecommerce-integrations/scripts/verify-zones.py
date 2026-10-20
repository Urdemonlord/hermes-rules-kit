#!/usr/bin/env python3
"""Verify zone classification produces correct results for known provinces."""
import sys

# Mirrors provinceToZone() from src/lib/server/biteship.ts
ZONE_MAP: list[tuple[list[str], int]] = [
    (['DKI Jakarta', 'Jawa Barat', 'Jawa Tengah', 'Jawa Timur', 'DI Yogyakarta', 'Banten', 'Bali'], 1),
    (['Sumatera Selatan', 'Sumatera Barat', 'Lampung', 'Bengkulu', 'Jambi', 'Riau', 'Kepulauan Riau', 'Sumatera Utara', 'Kepulauan Bangka Belitung', 'Bangka Belitung'], 2),
    (['Kalimantan Barat', 'Kalimantan Tengah', 'Kalimantan Selatan', 'Kalimantan Timur', 'Kalimantan Utara', 'Sulawesi Selatan', 'Sulawesi Tengah', 'Sulawesi Tenggara', 'Sulawesi Utara', 'Gorontalo', 'Sulawesi Barat'], 3),
    (['Aceh', 'Nusa Tenggara Timur', 'Nusa Tenggara Barat'], 4),
    (['Maluku', 'Maluku Utara', 'Papua', 'Papua Barat', 'Papua Selatan', 'Papua Tengah', 'Papua Pegunungan', 'Papua Barat Daya'], 5),
]

# Flat rate base prices: [500g, 1kg, 2kg, 5kg] per zone
ZONE_PRICES: dict[int, tuple[int, int, int, int]] = {
    1: (12000, 15000, 22000, 38000),
    2: (22000, 28000, 42000, 65000),
    3: (35000, 45000, 65000, 100000),
    4: (45000, 58000, 80000, 125000),
    5: (65000, 82000, 110000, 180000),
}

def province_to_zone(province: str) -> int:
    if not province:
        return 2
    p = province.lower()
    for names, z in ZONE_MAP:
        for name in names:
            if name.lower() in p:
                return z
    return 3  # unknown → conservative middle

def main() -> int:
    tests = [
        ('DKI Jakarta', 1),
        ('Jawa Barat', 1),
        ('Jawa Tengah', 1),
        ('Jawa Timur', 1),
        ('DI Yogyakarta', 1),
        ('Banten', 1),
        ('Bali', 1),
        ('Sumatera Selatan', 2),
        ('Sumatera Utara', 2),
        ('Sumatera Barat', 2),
        ('Lampung', 2),
        ('Bengkulu', 2),
        ('Jambi', 2),
        ('Riau', 2),
        ('Kepulauan Riau', 2),
        ('Kepulauan Bangka Belitung', 2),
        ('Bangka Belitung', 2),
        ('Kalimantan Timur', 3),
        ('Kalimantan Selatan', 3),
        ('Sulawesi Selatan', 3),
        ('Sulawesi Utara', 3),
        ('Gorontalo', 3),
        ('Aceh', 4),
        ('Nusa Tenggara Timur', 4),
        ('Nusa Tenggara Barat', 4),
        ('Papua', 5),
        ('Papua Barat', 5),
        ('Papua Selatan', 5),
        ('Maluku', 5),
        ('Maluku Utara', 5),
    ]

    passed = 0
    failed = 0

    print("Zone Classification Tests")
    print("=" * 60)
    for prov, expected_zone in tests:
        actual = province_to_zone(prov)
        pr500, pr1k, pr2k, pr5k = ZONE_PRICES[actual]
        status = '✅' if actual == expected_zone else '❌'
        print(f"  {status} {prov:30s} → Zone {actual}  (1kg: Rp{pr1k:,})")
        if actual == expected_zone:
            passed += 1
        else:
            failed += 1

    print(f"\n  {passed}/{passed+failed} passed")

    # Unknown province test
    unknown = province_to_zone('')
    print(f"\n  Unknown province → Zone {unknown} (expected 2)")
    unknown2 = province_to_zone('Provinsi Tidak Dikenal')
    print(f"  'Provinsi Tidak Dikenal' → Zone {unknown2} (expected 3)")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
