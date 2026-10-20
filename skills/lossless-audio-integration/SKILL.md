---
name: lossless-audio-integration
description: "Use when adding lossless FLAC playback, download, or format labeling."
---

# Integrasi sumber audio lossless

## Kapan dipakai

- "bisa ga app-nya ngeplay lagu lossless?"
- "udah bisa detek lagu FLAC belum?" / "kasih label biar tau mana yang lossless" — pertanyaan
  deteksi & pelabelan format, yang bukan hal yang sama dengan pemutaran (lihat bagian khususnya).
- "tambahin download FLAC dari <tool>"
- Menambah sumber audio baru ke pemutar musik, di luar streaming lossy yang sudah ada.
- User menolak berlangganan provider berbayar (Tidal/Qobuz/Deezer) → arahkan ke Soulseek,
  jangan ke instance publik.

## Fakta yang mengubah hampir semua permintaan ini

**Spotify tidak menyediakan audio lossless untuk pihak ketiga.** Bahkan Premium hanya Ogg
Vorbis 320 kbps. Jadi "unduh lossless dari Spotify" bukan hal yang ada — tidak ada endpoint,
resmi maupun tidak resmi, yang mengembalikan FLAC dari Spotify.

**Tool yang namanya menunjuk Spotify hampir selalu hanya memakai Spotify untuk METADATA.**
Audio FLAC-nya diambil dari layanan lain — umumnya Tidal dan Qobuz, kadang Amazon/Deezer.
Sebelum merencanakan apa pun, telusuri kode tool itu dan temukan endpoint yang benar-benar
mengambil payload-nya. Rencana yang dibangun di atas nama akan salah dari baris pertama.

Rantai yang sebenarnya, dan yang perlu dibangun:

```
  metadata (Spotify)  →  ISRC / ID lintas layanan  →  cari di provider  →  URL FLAC
                                                                          │
                                                          ┌───────────────┴───────────────┐
                                                          ▼                               ▼
                                                   putar (ExoPlayer)             unduh (OkHttp)
```

## Tidak ada jalur gratis di layanan berlangganan

Periksa ini SEBELUM menjanjikan apa pun, karena inilah yang paling sering membatalkan rencana:

| Sumber | Gratis? | Lossless? | Kenyataannya |
|---|---|---|---|
| Tidal | ya | **tidak** | Tier gratis 96–160 kbps AAC |
| Deezer | ya | **tidak** | 128 kbps MP3 |
| Qobuz | trial 30 hari | ya | wajib kartu kredit — bukan solusi tetap |
| **Soulseek (`slskd`)** | **ya** | **ya, FLAC asli** | P2P; butuh share; unduhan mengantre |

**Provider tanpa langganan tidak selalu gagal — ia bisa membalas SUKSES berisi potongan 30 detik.**
Tidal mengembalikan `assetPresentation: "PREVIEW"` dengan durasi `PT29.976S`. Ini jauh lebih
berbahaya daripada error: kalau tidak diperiksa, user menyimpan klip 30 detik dengan nama lagu
penuh dan baru sadar berbulan-bulan kemudian. Perlakukan nilai `assetPresentation` yang tidak
dikenal sebagai BUKAN trek utuh (gagal-tertutup), dan tampilkan sebagai kegagalan yang terlihat —
bukan sekadar masuk log.

Kalau user menolak berlangganan, jalur provider berbayar tertutup. **Soulseek adalah satu-satunya
jalur gratis yang benar-benar memberi FLAC.** Endpoint, bentuk respons, dan jebakannya ada di
`references/soulseek-slskd.md`.

Bentuk jalur Soulseek berbeda, dan perbedaan itu mengubah arsitektur — bukan sekadar mengganti URL:

- **Tidak ada pemetaan ID lintas layanan.** Soulseek mencari dengan teks bebas, bukan ISRC, jadi
  langkah "ISRC → id provider" tidak ada.
- **Server yang mengunduh, bukan aplikasi.** slskd menarik berkas dari peer ke disk server;
  aplikasi hanya memerintah dan memantau. Karena itu tidak ada URL bertanda tangan yang
  kedaluwarsa, dan `ResolvingDataSource` **tidak diperlukan** untuk sumber ini.
- Muncul masalah baru yang tidak ada di jalur URL: berkasnya mendarat di server, bukan di HP.

## Yang biasanya sudah gratis — periksa dulu, jangan bangun ulang

Di Android dengan Media3/ExoPlayer:

- **Pemutaran FLAC sudah didukung native** — 16/44.1 maupun 24/96–192. Tidak ada dekoder yang
  perlu ditulis. Yang belum ada hanya *sumber* FLAC-nya.
- **Pemindai file** biasanya sudah menyertakan `flac` di daftar ekstensinya.
- **`MediaStore.Audio` menerima FLAC** karena `MimeTypeMap` memetakan `flac` → `audio/flac`,
  jadi jalur unduhan yang memfilter lewat `MimeTypeMap` langsung lolos tanpa perubahan.

Konsekuensinya: pekerjaannya sering cuma **satu nilai enum + satu sumber data**, bukan
subsistem baru. Katakan bagian mana yang sudah gratis sebelum mengusulkan yang dibangun.

## Menandai format lossless di daftar lagu (deteksi & label)

Ini pekerjaan yang berbeda dari *memutar* atau *mengunduh* lossless, dan sering dikira sudah
selesai padahal belum: pemindai bisa sudah menerima ekstensi `flac` sehingga lagunya MASUK
library, sementara aplikasi tetap tidak tahu — dan tidak bisa menampilkan — bahwa lagu itu FLAC.
Pertanyaan "sudah bisa deteksi FLAC?" karena itu harus dijawab dengan menelusuri apakah
**formatnya benar-benar disimpan**, bukan apakah file-nya terpindai.

- **Ekstensi di daftar pemindai ≠ format tersimpan.** Pemindai yang sudah memuat `flac` hanya
  berarti file-nya ikut masuk; kalau tidak ada kolom yang menyimpan format, tidak ada apa pun
  yang bisa ditampilkan. Periksa kolom entitasnya, bukan hanya daftar ekstensi.
- **Ambil format dari sumber yang benar-benar membawanya.** Untuk MediaStore itu
  `MediaStore.MediaColumns.MIME_TYPE` (dan/atau `DISPLAY_NAME`) — pemindai MediaStore sering
  hanya membaca judul/artis/album dan tidak pernah menyentuh `MIME_TYPE` sama sekali. Untuk
  pemindai berbasis nama file, ekstensinya sudah di tangan.
- **Ekstensi lossy yang dikenali harus MENGHENTIKAN fallback MIME — bukan jatuh ke sana.**
  Urutan "ekstensi dulu, MIME sebagai cadangan" tidak lengkap tanpa cabang berhenti: kalau
  ekstensi tidak ada di daftar lossless dan langsung jatuh ke MIME, berkas `.mp3` dengan MIME
  yang salah (`audio/flac` — MediaStore OEM bisa menulis satu MIME untuk seluruh folder)
  berlabel FLAC. Urutan keputusannya tiga cabang: ekstensi lossless → label; ekstensi lossy
  yang dikenali → `null` (berhenti); ekstensi tidak dikenal → baru MIME boleh menjawab.
  Tulis tes konflik eksplisitnya (`mp3` + `audio/flac` → `null`) sejak awal — inilah tes yang
  menangkap cacat ini, dan tanpa cabang berhenti itu justru tes itulah yang gagal di CI.
- **Jangan pakai ulang kolom kualitas milik jalur lain.** Kolom seperti kualitas "menurut peer"
  (jalur Soulseek) punya asal-usul berbeda dari format file lokal. Memakai satu kolom untuk
  keduanya membuat salah satunya tidak pernah terisi dan artinya kabur; buat kolom terpisah
  untuk format lokal.
- **Kolom baru wajib masuk ke jalur upsert, bukan hanya ke entity + migrasi.** Ini jebakan yang
  paling sering lolos: kolom ditambahkan ke entity dan migrasi, tetapi query
  `updateMetadata`/`upsertAll` tidak ikut diperbarui. Akibatnya instalasi baru terisi, sementara
  baris LAMA tidak pernah mendapat nilainya walau user memindai ulang — gejalanya cuma
  "sebagian lagu tidak berlabel". Perbarui daftar kolom yang di-share dengan tes, query
  `updateMetadata`, dan `upsertAll` bersamaan.
- **Label menyatakan format yang TERDETEKSI, bukan lossless yang TERVERIFIKASI.** Ekstensi dan
  MIME bisa berbohong (`.flac` hasil transcode dari MP3 sangat umum). Teksnya harus faktual
  ("FLAC"), bukan klaim mutu ("Lossless terverifikasi"); verifikasi sungguhan butuh analisis
  spektrum yang biasanya belum ada. Sama seperti kualitas peer di jalur Soulseek, tampilkan apa
  yang dilaporkan, jangan lebih. Karena itu teks UI-nya berbunyi "Format FLAC" — kata "Format"
  yang membatasinya pada fakta wadah berkas, bukan penilaian kualitas.
- **Hanya format LOSSLESS yang dilabeli; format lossy sengaja TIDAK.** Ini keputusan, bukan
  kelalaian: hampir semua lagu lossy, jadi menandai setiap lagu dengan formatnya mengisi daftar
  dengan label yang tidak memberi keputusan apa pun. Yang perlu terlihat sekilas hanya yang
  istimewa. Kalau ditanya "kenapa MP3 tidak ada labelnya", jawabannya ini.
- **`.m4a` / ALAC sengaja TIDAK dilabeli walau ia lossless.** ALAC adalah satu-satunya lossless
  yang tidak punya ekstensi sendiri — ia hidup di dalam wadah `.m4a`, yang jauh lebih sering
  berisi AAC (lossy). Tidak ada cara membedakannya dari nama berkas, jadi menebak akan salah
  lebih sering daripada benar. Membiarkannya tanpa label lebih jujur daripada memberi label yang
  salah. Sebelum menambah ekstensi ke daftar lossless, periksa dulu apakah ekstensi itu juga
  wadah untuk format lossy — kalau ya, jangan masukkan.
- **Badge ditaruh di baris JUDUL, bukan baris subjudul.** Subjudul (artist · album) sering KOSONG
  pada lagu lossless hasil rip sendiri, karena tag ID3-nya tidak lengkap — sehingga badge yang
  ditaruh di sana justru hilang persis di kasus yang paling perlu ditandai. Baris judul selalu
  ada.
- **Jangan isi kolom baru itu di dalam migrasi.** Mengisinya butuh logika yang sama dengan
  pemindai; menyalinnya ke SQL migrasi berarti dua tempat yang harus dijaga tetap sinkron dan
  pasti menyimpang. Biarkan NULL pada baris lama — dan NULL di sini artinya jujur: "belum
  diketahui", bukan "bukan lossless". Pemindaian berikutnya yang mengisinya.

## Aturan yang mengikat

- **Jangan simpan URL audio provider di database.** URL provider berbayar bertanda tangan dan
  bermasa berlaku. Simpan penanda berskema sendiri, tukar jadi URL asli lewat
  `ResolvingDataSource` tepat sebelum ExoPlayer meminta data — detail dan cache TTL-nya di skill
  `media3-session-uri` (Jebakan ketujuh). Untuk sumber yang mengunduh ke disk (Soulseek), aturan
  ini tidak berlaku: tidak ada URL bertanda tangan, cukup path berkas lokal.
- **Satu tabel lagu, sumber baru sebagai nilai enum.** Jangan buat tabel terpisah per sumber;
  itulah yang menjaga "satu library, satu antrean" tetap mungkin.
- **Ambil bentuk respons dari sumbernya, jangan menebak dari nama field.** Kalau ragu, jalankan
  servernya dengan Swagger/OpenAPI aktif lalu baca skema yang benar-benar dikirim; kalau respons
  endpoint tidak dideklarasikan di skema, clone sumbernya dan baca controller/DTO-nya. Satu field
  yang salah nama tidak melempar error — ia diam-diam bernilai default, dan bug-nya baru muncul
  jauh di UI. Contoh nyata: `state` sebuah server dikirim sebagai STRING gabungan
  (`"Completed, Cancelled"`), bukan angka, karena enum di-serialize sebagai nama secara global —
  memeriksanya dengan `==` alih-alih `contains` akan selalu salah.
- **Periksa isi respons, bukan hanya kode status.** Endpoint "antre unduhan" bisa membalas 201
  Created dengan daftar sukses yang KOSONG. Kode status yang benar dengan hasil kosong berarti
  operasinya tidak terjadi, dan itu harus terlihat sebagai galat — bukan sukses palsu.
- **Provider yang mengembalikan URL `.flac` langsung lebih baik daripada manifest DASH.** Satu
  URL yang sama bisa dipakai ExoPlayer maupun diunduh OkHttp, tanpa parser manifest. Tapi jangan
  asumsikan ini: periksa payload sungguhan. (Untuk Tidal, asumsi URL langsung ternyata salah —
  yang keluar manifest DASH.)
- **Kualitas diminta eksplisit, dan provider bisa diam-diam menurunkan.** Kalau kualitas yang
  diminta tidak berhak/tersedia, provider bisa mengembalikan yang lebih rendah **tanpa error**.
  Periksa `mimeType`/`codecs` dan `assetPresentation` di respons, jangan asumsikan `LOSSLESS`
  berarti FLAC utuh keluar. Nilai yang tidak dikenal → anggap BUKAN trek utuh.
- **Fitur ini default MATI sampai user memasukkan endpoint-nya sendiri.** Instance-nya milik
  user (self-host), jangan dibundel, jangan ada default instance publik. Pola lengkap untuk
  kapabilitas yang ToS-nya abu-abu ada di skill `project-integration-assessment`.

## Prasyarat & risiko self-host

- **Ambil jalur mana pun dan buktikan sendiri, jangan simpulkan dari dokumentasi.** Dua asumsi
  wajar di skill ini pernah salah saat diverifikasi langsung: `/track/` dianggap URL `.flac`
  (ternyata manifest DASH), dan akun tanpa langganan dianggap turun kualitas (ternyata potongan
  30 detik). Bukti dari server mengalahkan dokumentasi.
- Risiko ban akun nyata. Mitigasi yang berlaku: **satu permintaan trek sekaligus, dari satu IP,
  jangan berpindah IP.** Ini membatasi seberapa agresif antrean unduhan boleh berjalan.
- **Jangan pernah mengekspos instance ke internet publik.** Cukup jaringan lokal atau tunnel
  terautentikasi. Instance terbuka = orang lain memakai akun user, dan ban datang lebih cepat.
- Instance publik gratis berbagi kuota dan tidak bisa diandalkan untuk pemakaian rutin;
  self-host lebih stabil tapi memindahkan biaya ke langganan.

## Urutan pengerjaan

1. **Buktikan jalur payload-nya lebih dulu, dengan `curl`, sebelum menulis kode.** Untuk provider
   berbasis URL: buktikan sebuah URL `.flac` benar-benar keluar (dan periksa
   `assetPresentation`/`mimeType`-nya, bukan hanya kode status). Untuk Soulseek: buktikan search
   mengembalikan hasil dan enqueue mengembalikan `Enqueued` yang tidak kosong.
2. Modul klien provider sebagai JVM murni (HTTP + JSON, tanpa Android) supaya bisa diuji tanpa
   emulator — pola yang sama dengan modul klien layanan lain di proyek.
3. Tambah nilai enum sumber + kolom provider yang nullable, lalu migrasi Room (kolom nullable
   tanpa `DEFAULT NULL`). **Tulis SQL migrasi dari daftar kolom yang di-share dengan tes**, jangan
   salin manual di dua tempat — lihat "Jebakan migrasi Room" di bawah.
4. Settings: alamat server, pilihan kualitas, tombol uji koneksi. Fitur tetap mati sampai ini diisi.
5. Pemutaran: untuk sumber berbasis URL, penanda URI + `ResolvingDataSource`; untuk sumber yang
   mengunduh ke disk (Soulseek), cukup `localPath` yang sudah ada — tidak ada URL bertanda tangan.
6. Unduhan: generalisasi penyalin byte yang ada agar tidak terikat ke satu sumber.
7. Kalau berkasnya mendarat di server (bukan di HP), selesaikan dulu cara memindahkannya ke
   perangkat — ini keputusan yang harus diambil bersama user dan bisa membatalkan asumsi lain.

## Jebakan migrasi Room saat menambah kolom sumber

Lima hal ini tidak ketahuan saat build, dan masing-masing menghasilkan kegagalan di perangkat
user atau bug yang sulit dilacak:

- **Kolom baru WAJIB diletakkan di AKHIR data class.** Instalasi baru membuat tabel mengikuti
  urutan deklarasi; instalasi hasil upgrade memakai `ALTER TABLE ... ADD COLUMN`, yang selalu
  menempel di akhir. Meletakkan kolom di tengah membuat dua jalur menghasilkan struktur fisik
  berbeda. Room membandingkan kolom sebagai himpunan sehingga keduanya tetap diterima — jadi
  tidak ada error, hanya skema yang tidak seragam.
- **Room TIDAK menulis ulang `<versi>.json` saat hanya urutan kolom berubah.** Berkas schema yang
  basi membuat tes migrasi gagal padahal migrasinya sudah benar. Hapus berkas schema versi baru
  itu lalu jalankan `kspDebugKotlin --rerun-tasks` untuk memaksanya ditulis ulang; KSP biasa akan
  di-skip karena file schema bukan declared output.
- **Verifikasi urutan dari `CREATE TABLE` yang Room generate sendiri**, bukan dari berkas schema —
  hasil generate di `build/generated/ksp/.../BlossomDatabase_Impl.java` adalah yang benar-benar
  dipakai Room saat memvalidasi.
- **Menambah nilai enum TIDAK mengubah skema kalau kolomnya TEXT.** Room menyimpan enum sebagai
  nama, jadi nilai baru cukup ditambah di kode. Ini hanya aman selama nilainya tidak disisipkan
  di tengah ordinal — kalau suatu saat kolomnya diubah jadi ordinal INTEGER, menyisipkan nilai
  di tengah akan menggeser arti data lama.
- **Berkas schema versi baru di-commit ke repo, dan ia baru ada SETELAH build.** Kalau
  `app/schemas/…/<versi>.json` ikut di-commit (konvensi yang umum), versi baru hanya tercipta
  saat KSP menjalankan Room — jadi commit kode migrasinya bisa lolos CI (KSP jalan sebelum tes,
  jadi tesnya tetap lulus) sementara berkasnya tidak pernah ikut ter-commit. Akibatnya repo
  tidak konsisten dengan konvensinya. Setelah menambah migrasi, pastikan berkas schema versi
  baru benar-benar ada dan ikut di-commit — bukan hanya tesnya hijau.

**Proyek ini tidak punya tes migrasi sama sekali sebelum ini.** Ketidakcocokan skema Room tidak
ketahuan saat build — build hijau, lalu user yang meng-update aplikasinya dapat
`IllegalStateException: Migration didn't properly handle` dan datanya tidak bisa dibuka. Kalau
proyeknya belum memakai `room-testing`/Robolectric, tes murni JVM yang membaca artefak schema Room
sendiri sudah cukup, dan lebih baik daripada tidak ada. Tiga pemeriksaan yang berharga:
skema baru = skema lama + kolom migrasi; kolom baru berada di akhir; kolom baru nullable dan TEXT.

Detail endpoint, bentuk respons, dan penyiapan server:

- `references/tidal-hifi-api.md` — jalur provider berbayar (butuh langganan).
- `references/soulseek-slskd.md` — jalur gratis; dipakai kalau user menolak berlangganan.
