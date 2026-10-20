# MeowAttend API-key DB rollout (hash-only) + web alignment

## Context
MVP awal masih campur pola lama `X-Tenant-Id` di web static, sementara backend sudah pindah ke `X-API-Key`. Ini bikin auth mismatch walau endpoint backend terlihat sehat.

## Fix pattern (reusable)
1. Tambah tabel key di DB runtime:
   - `api_keys(id, tenant_id, name, key_hash UNIQUE, active, created_at)`.
2. Simpan **hash SHA-256** key saja (raw key tidak disimpan di DB).
3. Inisialisasi default key:
   - pakai `MEOWATTEND_API_KEY` bila ada,
   - jika tidak ada, generate random key saat startup.
4. Load active keys dari DB ke in-memory map untuk lookup cepat.
5. Resolusi tenant hanya dari `X-API-Key` (hapus ketergantungan header tenant manual di UI).
6. Selaraskan semua surface frontend (index/scan/dashboard) agar request API selalu kirim `X-API-Key`.

## Verification recipe
- Build/test backend:
  - `npm test`
  - `npm run build`
- Runtime probes:
  - `/health` tanpa key -> `200`
  - `/api/v1/me` tanpa key -> `401`
  - `/api/v1/me` dengan key valid -> `200` + `tenant_id`
  - create session via `X-API-Key` -> `201`
- DB probe:
  - hitung `active_api_keys` untuk memastikan key persistence aktif.

## Pitfalls
- Jangan klaim auth selesai kalau frontend masih pakai `X-Tenant-Id`.
- Saat logging startup, hanya tampilkan key **masked** (prefix/suffix), jangan raw.
- Jika ada proses dev lama, restart process dan re-probe endpoint agar hasil tidak false-positive dari binary lama.
