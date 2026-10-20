# MeowAttend-v2: active-session scan tanpa QR token + CTA Indonesia

## Kapan dipakai
- User bilang flow scan terlalu ribet (harus isi QR token manual).
- Dashboard dianggap membingungkan dan CTA campur bahasa.
- Produk absensi menuntut speed + simplicity untuk admin dan member.

## Pola implementasi yang terbukti
1. Tambah endpoint backend `GET /api/v1/events/active` (tenant-scoped, now within starts_at..ends_at).
2. Ubah flow member scan: pilih sesi aktif (`event_id`) lalu check-in langsung, tanpa input `qr_token`.
3. Tetap pertahankan flow admin QR di layar sesi (untuk display/scanning), tapi jangan wajibkan token manual di form user.
4. Lokalkan CTA/nav/action ke Bahasa Indonesia konsisten di semua surface (nav, tombol utama, helper text).

## Dampak UX
- Mengurangi langkah user scan.
- Menurunkan error input token.
- Dashboard lebih mudah dipahami karena action utama lebih eksplisit.

## Verifikasi minimum
- Backend test pass (`go test ./...` via Docker bila Go host tidak tersedia).
- Probe endpoint aktif mengembalikan `items` untuk sesi berjalan.
- UI member-scan memuat daftar sesi aktif dan bisa check-in sukses tanpa `qr_token`.
- Public app.html sudah menunjuk cache-bust JS terbaru.