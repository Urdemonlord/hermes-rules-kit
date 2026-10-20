---
name: lyrics-translation-subtitles
description: "Use when adding translated or romanized lyrics to a player."
---

# Terjemahan & Subtitle Lirik

Lapisan kedua di atas pemutaran lirik: terjemahan bahasa, romanisasi, dan
penampilannya. Berlaku untuk app apa pun yang sudah bisa mengambil dan menampilkan
lirik — bukan untuk pengambilan lirik itu sendiri.

## Tetapkan dulu: layer ini butuh sumber sendiri

Sebagian besar API lirik **tidak punya field terjemahan sama sekali**. Hanya
`plainLyrics` dan `syncedLyrics`. Kalau desain mengbarskan kolom terjemahan, itu
salah sebelum permintaan pertama dikirim. Periksa skema API sumber lirik dulu, dan
pilih sumber terjemahan secara terpisah.

Pilih sumber dengan jujur:

| Opsi | Ukuran | Butuh GMS | Offline | Verdict |
|---|---|---|---|---|
| ML Kit translate | ~30 MB per pasangan bahasa | **ya** | ya | Tolak untuk app kecil: perangkat tanpa Play Services dapat nol fitur, dan bundel model menaikkan APK |
| Model lokal | puluhan MB | tidak | ya | Tolak kecuali app memang besar dan offline-first |
| Remote LLM (OpenAI-compatible) | 0 byte | tidak | tidak | Pilihan DEFAULT untuk terjemahan + romanisasi |
| Lewat saja | 0 | tidak | tidak | Selalu tersedia sebagai fallback |

Remote menang karena subtitle itu pelengkap: hilang karena offline jauh lebih buruk
daripada beberapa ratus ms latency tambahan.

### Cek ukuran TRANSITIF, bukan ukuran artifact

Kandidat kanji→romaji yang terlihat ideal (jar 9 KB) bisa menarik kamus 13,3 MB
lewat modul lain — lebih dari seluruh APK app 2 MB. Sebelum menambahkan
dependency apa pun, cek ukuran dependency-nya juga:

```bash
curl -sI '<artifact-url>' | grep -i content-length
curl -s '<artifact-url>.pom' | sed -n '/<dependencies>/,/<\/dependencies>/p'
```

Kalau sudah ada panggilan LLM untuk fitur yang sama, **tanyakan romanisasi di
respons yang sama**. Nol dependency baru, dan pembacaan kanji datang dari model
bahasa, bukan kamus statis yang bisa basi.

### Aturan isi prompt yang wajib ada

- **Romaji hanya untuk baris yang memang Japanese**, string kosong untuk yang lain.
  Tanpa aturan ini, model meromakan semua baris termasuk yang bahasa Inggris, dan
  UI harus mendeteksi lalu membuang noise-nya.
- **Terjemahan harus diminta "short and singable"** — terjemahan harfiah
  terbaca hasil mesin di layar yang memang dibaca sambil lagu berjalan.
- **Beri indeks di tiap baris input** dan minta indeks itu dikembalikan. Lihat
  bagian batch di bawah.
- **Persona di-inline ke pesan user** bila endpoint menjatuhkan
  `role: "system"` — probe dulu sebelum menulis prompt.

## Batch: cocokkan lewat indeks, bukan urutan array

Beri setiap baris indeks di prompt, lalu cocokkan respons lewat `i` itu —
**bukan lewat urutan respons**. Model boleh melewati satu baris, dan
pencocokan berbasis posisi akan menempelkan jawaban baris 3 ke baris 4 tanpa error
yang terlihat.

Kembalikan daftar dengan panjang yang **sama dengan input**, termasuk baris yang
tidak dijawab model (isi kosong). Kalau panjangnya bisa berbeda, setiap pemanggil
kehilangan mapping-nya dan UI harus menebak sendiri.

**Baris tanpa teks (jeda instrumental) jangan pernah dikirim** — LLM tidak bisa
menerjemahkan ketiadaan. Tapi **posisi baris itu tetap harus dipulihkan** di
hasil, kalau tidak satu jeda di tengah lagu menggeser seluruh subtitle sesudahnya.

Verifikasi dengan probe **campur**: dua baris Japaniya dan satu baris Inggris dalam
satu panggilan. Probe homogen tidak bisa membuktikan model menggate field khusus
bahasa dengan benar, karena semua baris akan memenuhi syarat.

## Kunci API: milik user, dan itu sah

Terjemahan butuh kredensial. Simpan di Settings dengan default string kosong —
bukan key bawaan yang tertanam di APK — dan field-nya wajib
`PasswordVisualTransformation`. Key yang tertanam bisa diekstrak dari APK mana pun
yang membawanya.

Kegagalan berakhir sebagai "subtitle tidak tersedia" dengan penjelasan ke mana
harus mengisi kunci, **bukan** pesan error jaringan. Yang belum dikonfigurasi dan
yang rusak menampilkan pesan yang sama untuk user.

Dua key terpisah (api key + endpoint), bukan satu string gabungan, supaya endpoint
bisa dikembalikan ke default tanpa ikut menghapus kunci.

## Cache turunan: jangan disatukan dengan cache dasar

Kalau lirik di-cache dari sumber A dan terjemahan datang dari sumber B, simpan
**dua cache terpisah** dan pasang kembali turunan setiap kali yang dasar dipasang.
Kalau terjemahan menempel pada entri cache yang sama, memutar ulang lagu yang
tadi sudah pernah diterjemahkan akan menghapus subtitle-nya sampai user menekan
tombol lagi — cache yang seharusnya menghemat kuota justru menghapus fitur.

## UI subtitle

- **Baris aktif di tengah layar** dengan `contentPadding` separuh tinggi viewport
  di atas dan bawah, lalu `animateScrollToItem(activeIndex)`.
- **Hormati guliran user**: dengarkan `DragInteraction.Start` di
  `interactionSource`, jeda sorotan, lanjutkan setelah timer yang dihitung dari saat
  jari **DIANGKAT** (pakai penghitung generasi sebagai kunci `LaunchedEffect`).
- **Bedakan baris aktif dengan warna DAN ketebalan** — warna saja hilang di layar
  redup.
- **Subtitle lebih kecil dan lebih redup** daripada lirik aslinya, dan hanya satu
  tingkat ketebalan. Warna yang sama persis membuat dua baris terbaca sebagai dua
  lirik yang setara, padahal yang translate cuma pelengkap.
- **Romanisasi di atas terjemahan** kalau keduanya tampil: romaji membantu yang
  sudah bisa baca huruf latin mengeja aslinya; terjemahan adalah tambahan kedua.
  Membalik urutan membuat dua teks latin sejajar tanpa jelas mana aslinya.
- **Baris tanpa teks tidak mencari subtitle.** Menerjemahkan ketiadaan tidak
  menghasilkan apa pun, dan subtitle di atas "♪" hanya menambah ruang kosong
  yang bergerak.
- **Status muat/gagal adalah `item` di BAWAH daftar, dengan `key` eksplisit**, bukan
  disisipkan sebagai baris di tengah. Dicampur ke daftar, orang mengira itu lirik
  yang gagal dimuat; tanpa `key`, sisipan di tengah membuat Compose menganggap
  seluruh item bergeser karena `itemsIndexed` memakai posisi sebagai identitas.
- **Panel subtitle jangan menutupi kontrol playback.** Ganti artwork, jangan jadi
  layar penuh.
- **Tombol subtitle mati, jangan hilang, saat prerequisite-nya belum terpenuhi**
  (lirik belum tampil / belum ada). Tombol yang hilang membuat orang
  mencari-cari letaknya; tombol yang kelihatan mati menjelaskan dirinya sendiri.

## Jebakan penulisan

- **Periksa ulang file Kotlin yang baru ditulis kalau komentarnya panjang dan
  non-ASCII.** Menulis blok komentar dari kalimat yang lebih panjang bisa
  menyisipkan fragmen asing yang lolos penulisan dan lolos build — kompilasi
  tidak menangkap karakter aneh di dalam `//` atau `* */`. Setelah menulis file
  panjang, `grep` baris komentar untuk non-ASCII tak terduga dan baca ulang hunk
  yang ditunjuk.
- **Base URL dan path.** Kalau konfigurasi menyimpan BASE (`https://host/v1`),
  tambahkan `chat/completions` saat dipakai lewat
  `HttpUrl.newBuilder().addPathSegments(...)` — penyambungan string menghasilkan
  path ganda begitu ada trailing slash.

## Cross-reference

`lyrics-lrclib` menangani pengambilan, pembersihan judul, parsing LRC, dan panel
lirik tersinkron dari LRCLIB. Skill ini menangani lapisan terjemahan di atasnya.

`openai-compatible-gateway-integration` carries endpoint probing rules, termasuk
bagaimana mematikan thinking model supaya `content` tidak kosong.