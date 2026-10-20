---
name: lyrics-lrclib
description: "Use when adding lyrics to a music player app."
---

# Lirik dari LRCLIB

Untuk menampilkan lirik lagu, termasuk yang tersinkron (disorot mengikuti lagu).

## Sumber: LRCLIB

`https://lrclib.net`, tanpa API key, tanpa akun, lirik berpenanda waktu.
Sertakan User-Agent yang menyebut app dan versi; itu syarat wajar layanan gratis.

Ambil versi dari `BuildConfig.VERSION_NAME`, JANGAN tulis ulang di kode. Versi
manual selalu tertinggal tiap rilis.

### Dua langkah, dan kenapa

1. `/api/get?artist_name=&track_name=&album_name=&duration=` — presisi, hanya
   cocok kalau ketiganya kira-kira sama. Paling akurat: durasi memisahkan versi
   studio dari live/remix yang judulnya sama.
2. `/api/search?q=` kalau langkah 1 gagal — longgar, lalu pilih hasil dengan
   mencocokkan durasi sendiri. Urutan hasil tidak dijamin relevan.

Satu perbedaan kecil di nama artist ("Aimer" vs "Aimer (エメ)") atau judul yang
ada tambahan "(Official Video)" membuat `/api/get` membalas 404 padahal liriknya
ada. Karena itu langkah 2 wajib, bukan opsional.

### Sifat layanan yang harus diantisipasi

- **503 ServerOverloaded dan timeout itu normal**, bukan tanda bug. Rancang
  dengan asumsi ini akan sering terjadi.
- **404 berarti tidak ketemu**, bukan kesalahan. Jangan dilempar sebagai exception.
- **Ada entri sampah.** Pernah menerima entri yang isinya cuma `[00:00.00]probe`.
  Jangan tampilkan tanpa pemeriksaan.
- **Field bisa hilang.** Semua field model harus opsional dengan default, dan
  parser JSON harus `ignoreUnknownKeys = true`.

### Kegagalan tidak boleh tampil sebagai galat

Lirik cuma pelengkap; lagunya tetap bisa diputar tanpa lirik. Kegagalan jaringan
berakhir sebagai "lirik belum tersedia" dengan tombol coba lagi, bukan pesan
galat. Bedakan EMPAT keadaan, jangan disamakan:

- tersedia tersinkron (ada penanda waktu)
- tersedia biasa (tanpa penanda waktu)
- instrumental — beda dari "tidak ketemu", dan user perlu tahu bedanya
- tidak tersedia / gagal

Cache hasilnya termasuk yang GAGAL, di memori. Tanpa itu, lagu yang liriknya
tidak ada memicu permintaan baru tiap kali diputar.

## Membersihkan judul YouTube

Ini yang menentukan fiturnya berguna atau tidak. Judul di YouTube adalah judul
VIDEONYA; LRCLIB menyimpan judul LAGUNYA. Kirim apa adanya, pencarian gagal
hampir selalu, dan liriknya terlihat "tidak ada" padahal ada.

**Buang penanda BENTUK VIDEO** (liriknya identik dengan versi asli):
`Official Video`, `Official Music Video`, `Official Audio`, `Lyrics`,
`Lyric Video`, `Visualizer`, `MV`, `M/V`, `PV`, `4K`, `HD`, `Color Coded`,
`Eng Sub`. Tangani juga kurung Asia `【】`.

**PERTAHANKAN penanda VERSI MUSIK**: `Live`, `Acoustic`, `Remix`, `Instrumental`,
`feat.`, tahun. Lagu live punya lirik yang bisa berbeda dari versi studio;
buang penandanya dan lagu live dicocokkan ke versi studio, menghasilkan lirik
yang meleset. Lebih baik tidak ketemu daripada ketemu tapi salah.

**Nama artist**: `"X - Topic"` adalah kanal otomatis YouTube Music berisi rilisan
resmi, jadi artistnya `X`. Buang juga akhiran `VEVO` dan ` Official`.

Pola pemisah harus tahan bentuk tanpa spasi: `removeSuffix("- Topic")` TIDAK
menangkap `"Aimer-Topic"`. Pakai regex `\s*-\s*Topic$` dengan IGNORE_CASE.

Coba hasil pembersihan lebih dulu, lalu judul asli sebagai cadangan (ada judul
yang tanda kurungnya memang bermakna). Kalau pembersihan tidak mengubah apa pun,
jangan kirim permintaan kedua yang identik.

## Parsing LRC

Format: `[mm:ss.xx]teks`, boleh banyak penanda waktu untuk satu teks.

- **Presisi desimal**: `12.3` = 300ms, `12.34` = 340ms, `12.345` = 345ms.
  Panjang digit menentukan skalanya. Salah di sini menggeser SELURUH lirik, dan
  tidak terlihat di lagu pendek. Uji ketiganya.
- **`[offset:±ms]`** menggeser seluruh berkas. Baca SEBELUM baris dipakai; kalau
  offset muncul di tengah, baris sebelumnya sudah terlanjur salah.
- **Baris tanpa teks = jeda instrumental.** Simpan, jangan dibuang, supaya baris
  berikutnya tidak menempel ke sebelumnya.
- **Metadata** `[ar:]`, `[ti:]`, `[al:]`, `[by:]` dilewati, bukan jadi lirik.
- **`activeIndex`** harus mengembalikan -1 sebelum baris pertama
  (`indexOfLast { it.timeMs <= positionMs }`). Tanpa itu, intro instrumental
  panjang menyorot baris pertama dari detik nol.
- Kalau lirik tersinkron gagal di-parse, jatuh ke lirik biasa. Lebih baik teks
tanpa sorotan daripada tidak ada apa pun.

## UI: lirik tersinkron

- **Baris aktif di TENGAH layar**, bukan di atas. Caranya: `contentPadding` atas
  dan bawah masing-masing setengah tinggi viewport (diukur `onSizeChanged`), lalu
  `animateScrollToItem(activeIndex)`. Mata sudah ada di tengah, jadi baris
  berikutnya muncul di tempat yang sudah dilihat.
- **Bedakan baris aktif dengan warna DAN ketebalan.** Warna saja hilang di layar
  redup atau bagi user yang sulit membedakan warna.
- **Hormati guliran user.** Kalau user menggulir sendiri, hentikan sorotan
  otomatis sementara. Dengarkan `interactionSource.interactions` dan cari
  `DragInteraction.Start`. Scroll dari kode tidak lewat interactionSource, jadi
  tidak ikut memicu jeda.
- **Reset timer dari saat jari DIANGKAT**, bukan saat menyentuh. Pakai penghitung
  generasi sebagai kunci `LaunchedEffect` supaya tiap sentuhan menghitung ulang.
  Tanpa itu, membaca bagian panjang lebih dari durasi jeda akan dilawan di tengah
  bacaan padahal jari masih di layar.
- **Panel lirik jangan menutupi kontrol playback.** Ganti artwork-nya, jangan
  jadi layar penuh. Kalau tidak, kontrolnya ikut tertutup.
- **Jangan reset pilihan tampil saat lagu berganti.** Yang berganti isinya, bukan
  pilihannya. Kalau direset, pendengar album harus membukanya lagi tiap lagu.

## Verifikasi tanpa perangkat

Parser LRC murni fungsi string, jadi bisa diuji lewat `kotlinc` tanpa emulator:

```bash
kotlinc Parser.kt Test.kt -include-runtime -d out/t.jar && java -jar out/t.jar
```

**Tapi lulus di `kotlinc` BUKAN jaminan lulus di build proyek.** `kotlinc` lepas
menerima `continue` di dalam lambda inline; konfigurasi compiler Gradle proyek
menolaknya dengan "break continue in inline lambdas is experimental". Selalu
compile lewat Gradle juga sebelum menganggap selesai.

## Jebakan Compose

Ditemukan dari membaca ulang kode, bukan dari compile:

- **Anak ber-`fillMaxSize` di dalam `Column` menghabiskan seluruh ruang** dan
  mendorong saudaranya keluar layar. Tombol yang dibungkus begini tidak akan
  pernah bisa ditekan. Pakai `Box(contentAlignment = Center)` yang membungkus
  `Column` berisi kontennya saja.
- **Urutan modifier menentukan hasil**: `height(14.dp).padding(vertical = 4.dp)`
  menyisakan bar 6dp. `padding` dulu, baru `height`.
- **`Idle` bukan `Loading`.** Kalau disamakan, kerangka loading tampil padahal
  tidak ada apa pun yang sedang dimuat, dan tidak akan pernah selesai.
- **State `remember` tanpa kunci hidup selama composable ada.** `remember(songId)`
  me-reset tiap lagu; `remember` saja tidak. Pilih sesuai perilaku yang diinginkan.
