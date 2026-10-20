# Aturan "dengar cukup" dan pencatatan yang bisa dipercaya

Untuk fitur scrobbling atau reporting apa pun yang terpicu playback.

## Akumulasikan waktu dengar, jangan pakai selisih jam dinding

Pencatatan yang benar menjumlahkan tiap interval polling **selagi** audio benar
berbunyi. Selisih jam dinding ikut menghitung waktu saat dijeda, sehingga
"waktu dengar" membengkak tanpa ada suara yang keluar — dan ambang "dengar
cukup" jadi tidak pernah tercapai untuk lagu yang sering dijeda.

Bentuk yang sudah terbukti di player:

```kotlin
// dijumlahkan per interval, bukan dari startTime
private var listenedSongId: String? = null
private var listenedAccumMs: Long = 0L

// ditulis ke DB hanya saat lagunya berganti/berhenti,
// bukan tiap polling — ribuan tulis per lagu itu pemborosan
```

## Cuplikan lama harus ditulis sebelum item baru, berurutan

Saat transisi lagu terjadi, dua hal harus berjalan **berurutan dalam satu
coroutine**: simpan akumulasi lagu sebelumnya, lalu sisipkan riwayat baru.
Dua coroutine terpisah membuat Room bisa mengeksekusi sisipan lebih dulu — dan
untuk `repeat one`, update-lama lalu menimpa baris BARU sementara baris lama
tetap nol.

## Penjaga anti-dobel wajib, dan ambangnya diturunkan dari mekanismenya

Media3 bisa memanggil `onMediaItemTransition` **dua kali** untuk lagu yang sama
dalam hitungan milidetik: sekali saat `setMediaItems` memasang antrean, sekali
lagi saat lagu benar-benar mulai. Tanpa dedupe, satu kali dengar naik dua di
statistik dan muncul dua kali di Recently Played.

Ambang dedupe dipilih dari mekanismenya, bukan dari angka bulat:

```kotlin
private var lastMarkedId: String? = null
private var lastMarkedAtMs: Long = 0L

val isRapidDuplicate = id != null && id == lastMarkedId &&
    now - lastMarkedAtMs < MARK_DEDUPE_WINDOW_MS
```

~1,5 detik: pemutaran ulang yang disengaja tidak mungkin terjadi sedekat itu,
sementara dua callback untuk satu kejadian datang dalam hitungan milidetik.

## Transisi karena pemulihan antrean bukan pilihan pengguna

Memulihkan antrean memanggil `setMediaItems`, yang memicu callback yang sama
dengan yang mencatat riwayat. Tanpa penjaga, **membuka aplikasi saja** sudah
mencatat lagu sebagai diputar dan menaikkan `playCount`, walau user belum
menekan play.

Penjaganya harus **dipasang sebelum** `setMediaItems`, dan penandanya
`isRestoringQueue` — bukan mengandalkan urutan penetration `lastMarkedId`,
karena callback Media3 bisa datang sinkron maupun lewat looper.

Masalah turunannya: pemulihan sengaja tidak memicu pencatatan, jadi tidak ada
transisi yang menyusul saat user kemudian menekan play — dan tanpa penanda, lagu
itu tidak pernah masuk riwayat **sementara** akumulasi waktunya menimpa baris
LAMA dari sesi sebelumnya. Butuh penanda kedua (`pendingRestoredMarkId`).

## Timestamp yang dikirim harus milik lagu yang SELESAI, bukan yang baru

Setiap scrobble membawa `timestamp` — kapan listen dianggap selesai. Kalau
nilai itu diambil dari state transisi yang sama seperti `listenedSongId`, ada
dua jalan yang bisa salah:

1. Nilai itu di-*set* setelah nilai barunya dibaca → yang terkirim adalah
   nilai LAMA (lagu sebelumnya), dan yang di-*set* memakai nilai yang belum
   dideklarasikan → tidak kompilasi.
2. Semantiknya terbalik: yang dikirim adalah waktu mulai lagu BARU, padahal
   provider menandai lagu yang sudah selesai.

Bentuk yang benar — baca dulu, lalu simpan:

```kotlin
val mulaiLaguSebelumnya = mulaiLaguDetik   // milik lagu yang selesai
val mulaiLaguBaru = now / 1000L
scrobbleCoordinator.kirim(snapshot, mulaiLaguSebelumnya)
mulaiLaguDetik = mulaiLaguBaru             // disimpan untuk transisi berikutnya
```

Simpan waktu mulai **sebagai field class** yang di-*overwrite* di setiap
transisi; jangan hitung ulang dari `now` saat transisi, dan jangan pakai
`startTime` item untuk hal ini.

## Saldo listen untuk statistik dan untuk scrobble harus satu sumber

Kalau statistik lokal dan scrobble memakai akumulator waktu yang berbeda
(meski keduanya "seperti" yang sama), keduanya bisa memutuskan berbeda tentang
lagu mana yang cukup didengar. User melihat dua jawaban berbeda untuk satu
pertanyaan.

Gunakan **nilai yang sama persis** yang ditulis ke DB untuk menentukan apakah
scrobble layak — tidak ada pengulangan perhitungan, tidak ada peluang
menyimpang.

## Listener playback biasanya bukan suspend: jangan pakai Mutex.withLock di sana

`Mutex.withLock` adalah `suspend`. Listener transisi media dipanggil dari
framework yang harus segera kembali, jadi pemanggilnya fungsi biasa — dan
`withLock` di sana **tidak kompilasi**. Gejalanya muncul sebagai error compile
di lapisan integrasi, jauh dari listener yang menyebabkannya.

Bentuk dua tahap yang aman, sekaligus tidak compromising dedupe:

```kotlin
fun catatSelesai(songId: String, listenedMs: Long, mulaiDetik: Long) {
    val now = System.currentTimeMillis()
    // Tanpa lock: hanya menyaring sebelum kerja mahal (baca DB).
    if (queue.sudahBaruBaruDicatat(songId, now)) return

    scope.launch {
        // ... baca metadata, cek ambang ...
        kunci.withLock { queue.tambah(songId, scrobble, now) }   // keputusan final
        kirimTertunda()
    }
}
```

Pemeriksaan tanpa lock itu **aman**: kalau dua pemanggilan lolos bersamaan,
hanya satu yang lolos `tambah` di bawah lock. Yang menentukan tetap satu
tempat — jangan sampai aturan duplikasi
dipisah ke dua lokasi, karena itu yang membuat keduanya bisa berbeda pendapat.

## Rilis yang belum pernah menyentuh provider: cirip yang harus disebut

Integrasi bisa lolos compile + lint + test, lalu **tidak pernah mengirim satu
pun request** ke provider. Dua tanda yang harus dicek sebelum menyatakan
"fitur berfungsi":

- **Tidak ada satu pun nilai provider yang tertangkap nyata** — semua fixture
  berasal dari dugaan sendiri tentang format. Lihat bagian validator di
  `callback-bridge-pattern.md`; nilai nyata justru sering langsung mengungkap
  bug validasi yang tidak akan pernah ditemukan test.
- **Alur auth belum dieksekusi di perangkat** dan tidak ada respons provider
  di log server.

Test yang hijau membuktikan signature dan dedupe benar secara matematis.
Itu **tidak** membuktikan provider menerimanya. Untuk fitur yang terlihat
berhasil di UI tapi mengirim nol data, user tidak akan melaporkannya — dia
cuma berhenti memakainya. Sebutkan batas ini di closeout, jangan disamarkan
dengan "semua test hijau".

## Resilience: satu kegagalan jaringan jangan menjatuhkan playback

Semua reporting (scrobble, analytics, keepalive) adalah efek samping. Kalau
laporan gagal dan menjatuhkan antrean atau service, fitur pelaporan bisa
mematikan aplikasi. Bungkus per operasi, log, lalu lanjutkan.

Efek yang harus bertahan melewati akhir sesi — antrean scrobble, retry,
keepalive — inject dengan scope **aplikasi**, bukan scope service playback.
Scope service hilang begitu app ditutup, dan justru hasil yang sudah terkumpul
itu yang paling hilang. Detail dan bentuk kodenya di SKILL.md.

Pemisahan fase berlaku di sini: endpoint yang merespons hanya membuktikan
fase pertama. Kirim yang benar-benar diterima layanan adalah bukti terpisah
yang hanya ada di perangkat.

## Ambang provider harus terpisah dari ambang aplikasi sendiri

Provider punya aturan sendiri kapan sebuah listen dianggap selesai, dan
jarumnya **tidak sama** dengan ambang statistik aplikasi. Untuk Last.fm:
lebih dari setengah durasi **atau** lebih dari empat menit, mana yang lebih dulu.
Aplikasi sendiri sering memakai ambang berbeda untuk "sudah listened".

Jangan menyatukan keduanya supaya cuma ada satu angka — itu membuat salah
satu angka salah. Contoh nyatanya: lagu 6 menit yang sudah didengar 3 menit
sudah scrobble di Last.fm, sementara di aplikasi masih dihitung "setengah
jalan". Satu tempat di kode, dua aturan berbeda, dua test berbeda.

Dua test yang wajib ada di ambang provider:

```kotlin
// tepat setengah dianggap cukup (bukan "lebih dari" strict)
assertTrue(ScrobbleRule.layak(90_000L, 180_000L))

// durasi tidak diketahui -> tidak bisa hitung setengah, dan angka
// empat menit TETAP berlaku sendiri
assertFalse(ScrobbleRule.layak(60_000L, 0L))
assertTrue(ScrobbleRule.layak(ScrobbleRule.EMPAT_MENIT_MS, 0L))
```

Detail yang jarang dipikir: durasi 0 tidak boleh diperlakukan sebagai
"dengar 0%". Kalau tidak, `listenedMs >= 4 menit` ikut hilang bersama
syaratnya — jadi syarat empat menit berdiri sendiri, bukan bergantung pada
syarat setengah.

## Kirim batch, bukan satu-satu

Provider yang menerima batch scrobble tersedia untuk alasan kegagalan jaringan
lokal: kalau satu panggilan gagal, seluruh riwayat dengar hari itu hilang. Satu
batch per panggilan berarti hanya batch terakhir yang hilang.

Indeks parameter harus lengkap dan konsisten. Untuk batch, `track[0]`,
`artist[0]`, `album[0]`, `timestamp[0]` — album boleh kosong **tapi
parameternya tetap dikirim**. Provider memosisikan lagu berdasarkan nomor
indeks, jadi nomor yang meleset akan menempelkan album ke lagu yang salah.

## Menandatangani request dari client: shared secret ikut ke APK

`api_sig` wajib dihitung pemanggil, jadi shared secret harus ada di binary.
Yang tetap tidak masuk binary adalah **session key milik user**. Keduanya
harus disebut terpisah di closeout — kalau hanya disebut "kredensial", claims
tentang apa yang bocor dari APK jadi kabur.

Empat jebakan, semuanya bisa lolos proofreading:

- **Bangun parameter sekali, pakai dua kali.** Body dan string signature dari
  `Map` yang sama. Dua loop terpisah = signature tidak cocok saat hanya satu
  yang berubah.
- **Byte negatif saat format hex.** `"%02x".format(byte)` di JVM bisa mencetak
  `ffffffff` untuk -1, signature 64 karakter yang selalu ditolak. Pakai
  `it.toInt() and 0xff`.
- **Nilai harapan test harus berasal dari luar.** Kalau test memanggil helper
  MD5 yang sama dengan yang diuji, dua sisi bisa salah bareng. Hitung dengan
  `hashlib` di command terpisah, lalu tempel literal.
- **Verifikasi jumlah karakter di test.** Signature 32 hex adalah assertion
  paling murah yang menangkap bug byte negatif.

## Metadata untuk reporting: cek dulu apa yang sudah ada

Sebelum query database atau tambah field baru untuk nama artist/track/album,
periksa apakah `MediaMetadata` yang sudah dibangun untuk item playback sudah
membawanya. Kalau iya, reporting cukup membaca metadata yang sudah ada — nol
query baru, nol field baru.