# Frontend Rebase from External Repo + Static Fallback Serve (VPS)

## Kapan dipakai
- User minta frontend diganti total dari repo lain (bukan patch incremental).
- Proxy production (Nginx) sudah mengarah ke port statis tertentu (mis. `127.0.0.1:4173`).
- Tujuan: cutover cepat, minim downtime, tetap bisa diverifikasi publik.

## Pola eksekusi yang terbukti
1. **Replace total frontend directory** (backup dulu), jangan merge parsial jika arsitektur beda jauh.
2. **Build frontend baru** sampai artifact final tersedia (contoh: `dist/client`).
3. Jika preview server framework bermasalah/konflik port, pakai **fallback static serve** dari artifact build pada port target proxy.
4. Verifikasi berlapis:
   - local listener port aktif,
   - domain publik HTTP status sesuai,
   - route penting (`/landing.html`, `/app.html`, `/scan-qr`) valid (termasuk redirect yang diharapkan).
5. Setelah stabil, baru commit + push.

## Pitfall yang harus dihindari
- Menganggap `vite preview` selalu cocok untuk jalur prod proxy; saat error modul/server-entry, jangan memaksa, langsung fallback ke static serve artifact.
- Membiarkan proses lama masih bind port target (hasilnya directory listing/asset mismatch atau service conflict).
- Klaim deploy sukses hanya dari build PASS tanpa probe URL publik.

## Bukti minimum handoff
- Build success.
- Port target listen.
- Probe domain publik untuk route inti (status code + marker konten/redirect).
- Commit SHA + push status.
