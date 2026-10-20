# MeowAttend scan-qr route hardening + production verification

## Context
User meminta route publik yang sederhana untuk member scan QR, bukan hanya hash route internal. Sebelumnya hanya ada `app.html#member-scan` dan user melihat route scan belum ada.

## Durable pattern
1. **Sediakan entrypoint publik khusus** untuk member scan:
   - Keep existing hash route: `/app.html#member-scan`
   - Tambahkan route publik: `/scan-qr` (user-facing)
2. Untuk static hosting sederhana (contoh Python `http.server`), route clean tanpa rewrite server bisa dicapai dengan:
   - Buat folder `scan-qr/`
   - Isi `scan-qr/index.html` yang redirect ke `/app.html#member-scan`
   - Hasil: `/scan-qr` -> 301 `/scan-qr/` -> redirect ke hash route
3. **Landing CTA wajib diarahkan ke route publik** (`/scan-qr`) agar flow member non-teknis tetap jelas.

## Why this approach
- Tidak bergantung pada perubahan nginx/reverse-proxy untuk alias path.
- Stabil di static file server lokal maupun jalur prod yang mem-proxy static origin.
- Memisahkan UX member dari rute admin/auth.

## Verification checklist (harus ada bukti)
- `curl` marker check di landing untuk CTA scan:
  - cari teks tombol `Scan QR Sekarang` dan `href="/scan-qr"`
- Header probes:
  - `GET /scan-qr` -> expected 301 ke `/scan-qr/`
  - `GET /scan-qr/` -> 200 `text/html`
- Content probe:
  - body `/scan-qr/` mengandung redirect ke `/app.html#member-scan`
- Browser probe:
  - buka `/scan-qr` dan pastikan final URL jadi `.../app.html#member-scan`
  - pastikan halaman tidak blank/error JS

## Pitfalls
- Membuat file `scan-qr` (tanpa extension) bisa memicu `content-type: application/octet-stream` di beberapa jalur proxy/CDN, bukan route HTML yang jelas.
- Mengandalkan hash route saja (`#member-scan`) tanpa entrypoint publik bikin user menganggap “route belum ada”.
- Verifikasi hanya dari satu tool kurang kuat; kombinasikan terminal (`curl`) + browser navigation.

## Minimal implementation snippet
Landing CTA:
```html
<a class="btn" href="/scan-qr">Scan QR Sekarang</a>
```

Redirect page (`scan-qr/index.html`):
```html
<meta http-equiv="refresh" content="0;url=/app.html#member-scan" />
<script>window.location.replace('/app.html#member-scan')</script>
```
