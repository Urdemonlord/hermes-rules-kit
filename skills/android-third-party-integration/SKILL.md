---
name: android-third-party-integration
description: "Use when an Android app talks to an outside service."
---

# Integrasi layanan pihak ketiga di Android

## Kapan skill ini dipakai

Menambahkan integrasi yang butuh identitas app di luar prosesnya: API key,
session token, OAuth, scrobbling/event reporting, webhook.

Bukan untuk: playback, audio effects, atau UI murni — itu skill android lain.

## Tanya dulu: apakah aplikasi benar-benar perlu punya kredensial?

Sebelum menyiapkan build plumbing untuk API key, jawab pertanyaan ini: **apakah
key itu perlu ada di dalam APK, atau cukup hidup di server?**

Kalau integrasinya lewat auth berbasis web (scrobbling, OAuth yang butuh
callback URL), jawabannya hampir selalu **tidak**. Android tidak punya URL
publik untuk menerima callback, jadi callback-nya berada di server — dan kalau
callback sudah di server, tukar-kode juga bisa di server. Aplikasi lalu
mengambil hasilnya lewat nonce sekali-pakai. Dengan bentuk itu:

- key dan secret hanya ada di environment service, tidak pernah masuk repo
  maupun APK,
- app yang dibongkar tidak memberi akses apa pun,
- APK yang bocor tidak cukup untuk menyamar sebagai aplikasi lo.

Yang tersisa di app hanyalah session key milik **user yang sedang login** —
dan itu memang harus ada di perangkat, itu gunanya.

Pakai pola `local.properties` di bawah hanya kalau memang sudah memutuskan key
harus ikut ke binary. Jangan menambahkannya "siap-siap dipakai" — menambahkan
plumbing BuildConfig berarti membuat keputusan arsitektur yang belum dibuat.

## Kredensial masuk lewat local.properties, dan kosong itu keadaan sah

Berlaku kalau keputusan di atas jatuh ke "key ikut ke binary".

`local.properties` sudah gitignored dan hanya ada di mesin developer. Runner CI
**tidak punya file itu sama sekali**. Kalau build script memuat properties tanpa
guard, build gagal di CI padahal lolos lokal — dan yang lebih buruk, kalau
di-workaround dengan nilai dummy, key palsu ikut terbawa ke APK rilis.

Pola yang benar: helper yang mengembalikan string kosong saat file tidak ada, dan
field build yang dibungkus tanda kutip di sisi pemanggil.

```kotlin
val localProperties = java.util.Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun localProperty(key: String): String = localProperties.getProperty(key, "")
```

```kotlin
// di dalam android { buildConfig { } }
buildConfigField("String", "LASTFM_API_KEY", "\"${localProperty("LASTFM_API_KEY")}\"")
```

Letakkan helper di luar blok `android { }` — `buildConfigField` memanggilnya,
jadi harus terdefinisi di scope script.

**Key kosong bukan kondisi error, dan tidak boleh diperlakukan sebagai satu.**
Fitur yang butuh key harus memeriksanya di awal dan menampilkan langkah
pengguna sendiri, bukan melempar exception yang membuat pengguna melihat crash
alih-alih petunjuk.

## Formulir pendaftaran app biasanya bisa mengubah jalur auth yang dipakai

Sebelum menulis bridge, baca halaman pendaftaran akun API provider sampai bawah.
Satu field bisa saja membatalkan separuh rancangan.

Contoh nyata: kalau formulir menyediakan **Callback URL** dan itu diisi, provider
dipakai lewat jalur web — app cukup membuka halaman auth provider dan provider
sendiri yang mengarahkan ke callback. Jalur itu **tidak butuh request token
yang dibuat server lebih dulu**, dan tidak butuh satu panggilan pun ke provider
sebelum user grant. Jalur desktop (request token) dan jalur mobile (password
plaintext) jadi tidak terpakai sama sekali.

Kalau callback URL **tidak** diisi, provider memakai jalur desktop dan request
token wajib ada. Jadi field itu bukan informasi formality — ini yang memilih
bentuk bridge.

Cek juga field yang tidak ada di dokumentasi auth (mis. field logo, atau
field yang hanya muncul setelah syarat terpenuhi) supaya tidak kaget saat
submit.

## Bridge meneruskan SELURUH field yang dibutuhkan app, bukan hanya kredensial

Respons auth provider hampir selalu punya lebih dari satu field berguna —
Last.fm mengembalikan `session.key` **dan** `session.name` di balasan yang
sama. Bridge yang mengambil hanya `key` membuang `name`, lalu app membuat
placeholder seperti `sessionKey.take(0)`, atau memanggil API tambahan hanya
untuk mengambil satu baris teks yang sudah ada di balasan itu.

Aturannya: **bridge adalah satu-satunya tempat data provider melintasi ke
app**, jadi apa pun yang nanti dibutuhkan app harus ditangkap di situ. Kalau
nanti perlu field tambahan, itu berarti fetch ulang — satu perjalanan
jaringan, satu permukaan kegagalan, dan satu alasan kenapa bridge mulai
menyerupai API penuh.

Dua tempat yang harus dicek saat menambah field baru: signature fungsi
`take_*`/`put_*` di bridge, dan test yang memanggilnya. Test yang hanya
menyebut satu kunci akan lolos walau field lain tidak pernah sampai.

## Binding kecil untuk integrasi: @Provides tidak boleh cohabit dengan @Binds

Coordinator atau scrobbler biasanya butuh **antarmuka kecil** (mis. satu operasi
baca lagu), bukan repository utuh — supaya bisa diuji tanpa database. Antarmuka
itu disuplai lewat `@Provides`, dan itu bentrok dengan bentuk module yang sudah
ada di project.

`@Binds` hanya sah di `abstract class`; `@Provides` hanya sah di non-abstract;
Dagger menolak satu module yang mencampur keduanya
(`may not contain both non-static and abstract binding methods`). Jadi pisahkan:
module pemetaan interface-ke-implementasi tetap `abstract` + `@Binds`, module
penyedia antarmuka integrasi jadi `object` + `@Provides`.

`@Binds` untuk interface **tidak bisa dihapus** hanya karena implementasinya
punya `@Inject constructor`. Itu membuat Dagger bisa menyediakan *implementasi*
itu sendiri; ia tidak tahu bahwa interface-nya harus dipenuhi. Menghapusnya
menghasilkan `MissingBinding` yang baru muncul di tahap compile DI — setelah
semua Kotlin sudah hijau dan test sudah lulus.

## Kalau pemanggil bridge punya callback, callback-nya mengembalikan galat — jangan melempar

Alur auth berurutan: app suspend, memanggil callback pembuka browser, lalu
menunggu. Kalau callback itu melempar exception (mis. tidak ada browser yang
bisa membuka `ACTION_VIEW`), exception-nya membatalkan seluruh coroutine —
pesan error tidak pernah sampai ke state UI, dan `finally` pun tidak
menyiapkan apa pun.

Bentuk yang benar: callback mengembalikan `String?` (pesan galat atau null),
dan pemanggil memutuskan:

```kotlin
val galat = bukaBrowser(authUrl)          // String?
if (galat != null) return Gagal(galat)    // gagal cepat, tidak menunggu 3 menit
```

Bonus yang sama-sama penting: galat "browser tidak ada" harus **menghentikan**
penantian, bukan ditelan lalu menunggu timeout penuh — tidak akan pernah ada
callback kalau tabnya tidak pernah terbuka.

## Membuka URL dari Android: jalankan dan tangkap, jangan pakai resolveActivity

`Intent.resolveActivity()` mengembalikan null sejak Android 11 untuk intent
yang tetap bisa jalan, karena package visibility. Memakainya sebagai
pemeriksaan akan salah menyimpulkan "tidak ada browser" padahal ada — lalu
user diberi pesan yang salah.

Bentuk yang dipakai di project ini:

```kotlin
try {
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))
    null
} catch (e: ActivityNotFoundException) {
    "Tidak ada aplikasi browser di perangkat ini."
}
```

## Gerbang rilis: efek fitur harus tersambung, bukan cuma permukaannya

Integrasi yang belum tersambung ke playback **tidak boleh dirilis dengan
UI yang terlihat berhasil**. Scrobbler yang sudah ada tapi tidak ada yang
memanggilnya berarti user bisa menyambungkan akun, melihat "Terhubung",
lalu nol data terkirim — dan tidak ada apa pun yang salah.

Gerbang sebelum rilis:

1. Telusuri siapa yang memanggil fungsi efek (grep nama fungsi, bukan hanya
   tempatnya didefinisikan).
2. Kalau pemanggilnya belum ada: **tuntaskan, atau jangan rilis**. Halaman
   koneksi tanpa efek yang terhubung lebih buruk dari tidak ada halaman.
3. Sebutkan di closeout kalau wiring-nya belum ada. "Fondasi siap" bukan
   "fitur berfungsi" — dan untuk fitur yang terlihat berhasil di UI, itu
   perbedaan yang paling berbahaya.

Dua lapis yang sering tercampur: **lapisan repository/scrobbler lengkap dan
teruji** vs **jalur pemicu yang tersambung ke playback**. Yang kedua yang
menentukan fitur benar-benar bekerja. Test aturan ambang dan signature tidak
membuktikan satu pun scrobble terkirim.

## Verifikasi mandatory: pindai tulisan sendiri untuk CJK dan kata rusak

Tulisan yang dihasilkan sering memuat karakter CJK/Cyrillic yang tidak
dimaksud di dalam komentar, identifier, dan pesan error — dan kata Inggris
yang rusak di tengah kalimat Indonesia. Keduanya lolos proofreading karena
terlihat seperti huruf asing yang sah.

**Jalankan pindai di turn yang sama dengan penulisannya, sebelum patch
berikutnya.** Bukan sekali sebelum commit: pola yang berulang adalah menulis
file → patch → patch lagi → baru|nat-memindai di akhir, dan setiap patch
sembunyi Opportunity introduces artefak baru. Artefak yang lolos lebih sering
berupa kalimat yang **tidak valid sama sekali** (`suspend function_mintaUrlAuth()`)
bukan cuma salah eja — keduanya lolos pemeriksaan mata.

```bash
python3 -c "
import re,sys
for p in sys.argv[1:]:
    for i,l in enumerate(open(p,encoding='utf-8'),1):
        if re.search(r'[　-鿿가-힯Ѐ-ӿ]',l): print(f'{p}:{i}: {l.strip()[:60]}')
" <file-file-yang-diubah>
```

Sertakan scan **kata Inggris nyasar** (bukan cuma CJK): pola camelCase yang
muncul di dalam kalimat prose, dan pengantar yang menggantung setelah CJK
dihapus. Kalau yang perlu dihapus adalah pengantar bertanda backtick,
pertahankan pungutannya supaya baris tetap grammatik — menghapus CJK saja
akan meninggalkan kata menggantung. Perbaiki ke bahasa Indonesia yang
benar, lalu jalankan ulang sampai bersih.

Satu perintah yang menutup dua-duanya:

```bash
grep -nP '[^\x00-\x7F]' <file>   # CJK/emoji di tengah kode Indonesia
```

Efek samping yang berguna: pemindaian ini juga menangkap identifier yang
rusak yang **tidak bisa dikompilasi**, sehingga tidak akan pernah terlihat
di diff review.

## Nonce harus dibuat aplikasi, bukan server

Server yang membuat nonce lalu menampilkannya di halaman callback
membocorkan nonce itu ke **riwayat browser** perangkat user. Setelah itu
kredensial session bisa diambil siapa pun yang memegang device itu.

Aturannya: **server hanya menerima nonce dan mengikatnya.** Dia tidak pernah
menerbitkan apa pun yang perlu dirahasiakan. App mengacak nonce-nya sendiri
(acak cukup, base64-url atau hex), mengirimkannya saat meminta auth URL, lalu
polling hasilnya.

Konsekuensi yang harus ditulis eksplisit di catatan proyek: kalau callback URL
bersifat tetap (biasanya begitu), nonce tidak bisa ikut di URL, jadi server
tidak bisa tahu nonce mana yang sedang berjalan. Solusi yang bisa
dipertanggungjawabkan adalah mengikat ke nonce **paling lama menunggu**, dengan
syarat aplikasi menjaga hanya satu login aktif pada satu waktu. Tulis syarat itu
sebagai batasan yang diketahui, bukan disembunyikan sampai user bertanya.

## Kalau keputusan arsitektur berubah, buang plumbing-nya di repo yang sama

Plumbing yang ditambahkan karena satu asumsi, lalu dibatalkan asumsinya, jadi
jebak untuk pembaca diff dan untuk sesi berikutnya: saat key ditambahkan
benar-benar, orang tidak sadar masih ada field BuildConfig lama yang memaksa
key masuk binary tanpa sengaja.

Jadi ketika keputusan berubah (mis. ternyata API key cukup hidup di server),
hapus plumbing-nya seketika di repo itu juga — `git checkout` pada file build
script — dan sebutkan pembatalan itu beserta alasannya di closeout.

## Pilih permukaan auth: jangan pernah kirim password provider ke dalam app

Ada jalur auth yang secara resmi tersedia dan hampir tidak pernah benar untuk
Android: metodenya meminta **username + password plaintext** milik user. Jangan
pilih itu. App apa pun yang menyentuh password itu punya password itu — bukan
hanya session key — jadi kebocorannya lebih besar dan tidak bisa dibatasi.

Alternatifnya web auth lewat browser sistem (Custom Tab), yang tidak memberi app
akses ke password sama sekali.

Sisa keputusannya: apakah perantara token-nya server sendiri, atau app
mengambil token itu sendiri di luar app.

- **Lewat server sebagai perantara** — app buka Custom Tab ke URL server,
  server yang menukar kode, hasilnya dikembalikan lewat nonce sekali-pakai.
  Untuk **jalur auth saja**, kredensial provider tidak pernah masuk binary.
  Perlu satu service kecil. (Batas kalimat ini ada di bagian signing di bawah:
  kalau API juga menandatangani request pemanggil, shared secret tetap harus
  ikut ke binary — meski auth-nya lewat server.)
- **Token manual** — hanya mungkin kalau provider memberi kredensial yang
  berumur panjang dan bisa diambil di luar app. Kalau token-nya berumur
  pendek dan sekali pakai, opsi ini **tidak mungkin secara arsitektur**, bukan
  cuma merepotkan.

Web auth in-app (WebView + deep link handler) menambah **dua permukaan serangan
yang belum ada di aplikasi** sekaligus. Sebelum mengusulkan itu, cek apakah
aplikasi memang sudah punya:

- scheme/deep-link di manifest (`<data android:scheme>`),
- WebView + `webkit` dependency,
- activity yang menangani callback.

Kalau ketiganya belum ada, auth in-app adalah pekerjaan besar yang tidak terlihat
di diff.

Bandingkan jujur sebelum memilih, lalu tetapkan dengan satu rekomendasi yang
jelas — jangan endlessly menunggu konfirmasi sebelum mulai. Karena setiap opsi
selalu punya sisi baik dan buruk, pilih yang membuat **permukaan serang paling
sedikit**, lalu tulis trade-off-nya dalam satu kalimat.

Kalau server perantara dipilih, pola lengkapnya ada di
`references/callback-bridge-pattern.md`.

## Jangan pernah meminta kredensial di chat

Minta user menyimpannya sendiri di `local.properties` atau credential store.
Kalau token sudah keluar di chat, perlakukan sebagai bocor dan sarankan
rotasi — tanpa lama-lama berkhotbah, cukup satu kalimat.

## Sebelum mengerjakan item checklist: cek apakah dua dokumen itu memang bertentangan

Blueprint dan design-spec sering punya daftar fitur yang sama dengan status yang
bertentangan — checklist yang masih menandai `[ ]` sementara tabel keputusan
yang lebih baru sudah menandai "tidak dipakai / turun jadi nice-to-have".

Sebelum mengerjakan satu item dari checklist:

```bash
grep -n -i '<fitur>' docs/blueprint.md docs/design-spec.md
```

Kalau satu bilang "fitur inti" dan yang lain "tidak dipakai", yang menang adalah
**dokumen yang lebih spesifik dan pernah menyatakan berubah arah** — biasanya
tabel keputusan beserta catatan "… berubah arah". Kontradiksi itu harus
dibawa ke user sebagai temuan, bukan dikerjakan diam-diam lalu menemukan
kontradiksi setelah commit.

Checklist yang usang adalah indikasi paling umum untuk pekerjaan yang tidak
pernah jadi prioritas.

## API yang menandatangani request: shared secret PASTI masuk binary

"Api key cukup hidup di server" itu benar untuk jalur auth, dan **tidak
benar untuk jalur tulis**. API lawas (Last.fm, sebagian besar OAuth v1)
mewajibkan `api_sig` — MD5/HMAC dari parameter + shared secret — dihitung
di sisi pemanggil. Artinya tidak ada pilihan: kalau app yang memanggil
`track.scrobble`, shared secret harus ada di dalam APK.

Ini bukan kelalaian dan bukan fitur yang bisa dihindari. Jangan ulangi klaim
"tidak ada kredensial di APK" tanpa batasnya — yang tidak masuk binary adalah
**session key milik user**, bukan shared secret. Bedakan keduanya secara
eksplisit di closeout, karena keduanya berbeda dan risikonya berbeda.

Empat jebakan saat menandatangani request dari client:

- **Bangun parameter sekali, pakai dua kali.** Body request dan string
  signature harus berasal dari `Map` yang sama. Kalau dua loop terpisah yang
  membangunnya, mengubah satu tanpa yang lain menghasilkan signature yang
  tidak cocok — dan API menolaknya dengan kode error generik.
- **Byte negatif saat memformat hex.** Di Kotlin/JVM, `"%02x".format(byte)`
  bisa mencetak `ffffffff` untuk nilai `-1`, bikin signature 64 karakter yang
  selalu ditolak. Pakai `it.toInt() and 0xff`.
- **Jangan pakai helper yang sama untuk menghitung nilai harapan test.**
  Kalau test `apiSig` memanggil helper MD5 yang sama, dua sisi bisa salah
  bareng dan test tetap hijau. Hitung nilainya di luar (python `hashlib`,
  satu command terpisah) lalu tempel sebagai literal.
- **Parameter berindeks harus dikirim lengkap.** Untuk batch, `track[0]`,
  `artist[0]`, `album[0]`, `timestamp[0]` — album boleh kosong tapi
  parameternya tetap dikirim. Provider memosisikan lagu berdasarkan nomor
  indeks, jadi nomor yang meleset menempelkan album ke lagu berikutnya.

Detail dan test-nya ada di `references/scrobbling-and-event-reporting.md`.

## Jangan berulang kali peringatan kredensial di closeout

Kalau user mengirim API key + shared secret lewat chat (dan di Last.fm memang
wajar — form pendaftaran menampilkannya), perlakukan sebagai hal yang sudah
ada di riwayat percakapan: sebutkan sekali bahwa rotasi secret gratis dan
boleh dilakukan, lalu **lanjut**. Jangan mengulang-ulang peringatan di setiap
pesan berikutnya, dan jangan menulis nilai penuhnya ke catatan vault, log, atau
pesan status — cukup `<ada>` atau `[REDACTED]`.

## Test integrasi: artifact nyata, bukan dokumentasi

Setiap nama API yang dipanggil app harus diverifikasi terhadap JAR yang benar-benar
dipakai build, bukan dari dokumentasi atau ingatan. Assertion test hanya boleh
mengutip nama yang muncul di output `javap`.

Dua jebakan yang berulang:

- `javap` **tidak menampilkan method yang diwarisi** dari superclass atau
  interface. "Tidak ada di output" belum berarti tidak ada. Cek kedua artifact
  (mis. `media3-common` vs `media3-exoplayer`) sebelum menyimpulkan.
- `javap` juga **tidak menampilkan private field**. `enabled` yang kelihatan
  sebagai field di subclass mungkin accessor-nya diwarisi dari parent — atau
  memang tidak ada sama sekali.

Kalau butuh method yang benar-benar ada tapi tidak muncul, dump seluruh API
publik lalu pilih dari daftar itu:

```bash
javap -p <Class>.class | grep -E 'public|protected'
```

Untuk memastikan aturan wiring (bukan hanya keberadaan API), test boleh membaca
sumber aplikasi — tapi **path relatifnya harus mengikuti konvensi project yang
sudah hijau**, bukan tebakan. Cari precedent lebih dulu:

```bash
grep -rn 'File("src/main' app/src/test/ | head
```

Gradle menjalankan unit test dari direktori modul, bukan direktori paket — tebakan
yang terlihat benar di diff tetap menghasilkan `FileNotFoundException` di CI.

## Cek kemampuan mocking project SEBELUM menulis test yang butuh mock

Test untuk kelas yang bergantung pada collaborator tidak bisa diuji dengan
JUnit polos kalau collaborator-nya `final class` (default di Kotlin) dan repo
tidak punya mocking library.

Cek dulu, satu perintah:

```bash
grep -n 'testImplementation' app/build.gradle.kts
```

Kalau tidak ada `mockk`/`mockito`, hand-rolled subclass tidak akan berhasil —
dan menambah dependency hanya untuk satu file test melanggar aturan
"jangan tambah dependency baru". Jalur yang benar: **ekstrak keputusannya ke
objek murni** dan biarkan I/O di kelas pendamping.

```kotlin
// kelas murni: antrean, dedupe, ambang -> bisa diuji dengan JUnit polos
class ScrobbleQueue { fun take(): ...; fun snapshot(): ... }

// pendamping: jaringan I/O, hanya meneruskan
class ScrobbleCoordinator(private val queue: ScrobbleQueue, ...)
```

Kelas murni yang lahir dari pemisahan ini biasanya paling banyak menyimpan
bug, karena semua cabang (dedupe, pembuangan entri lama, batas antrean) jadi
dapat diuji tanpa jaringan. Kalau pemisahan terasa boros, cek dulu apakah test
bisa membaca dan menulis state lewat seam non-I/O — sering sudah cukup tanpa
kelas baru.

## Efek tertunda (antrean scrobble, retry, keepalive) tidak boleh ikut mati bersama playback

Side effect yang butuh bertahan melewati akhir sesi punya scope sendiri. Kalau
antrean scrobble, retry, atau analytics di-`inject` dengan scope playback
service, seluruh antrean hilang begitu service dihentikan — dan user menutup
app adalah kejadian yang paling sering terjadi.

Pakai scope aplikasi:

```kotlin
@Inject @ApplicationScope private val scope: CoroutineScope
```

Elsa tanpa scope aplikasi, antrean hanya bertahan selama service hidup, dan
efek yang justru paling penting (mengirim hasil yang sudah terkumpul) justru
yang paling sering hilang.

## Aturan bukti yang tidak bisa diuji tanpa perangkat

Integrasi yang memanggil API luar punya batas bukti yang sama dengan fitur
audio: compile + lint + test hanya membuktikan bentuk statis. Yang perlu
disebutkan apa adanya di closeout:

- permintaan benar-benar terkirim dan diterima layanan,
- respons error ditampilkan ke pengguna, bukan tertelan,
- retry / rate limit tidak membuat antrean playback macet.

Verifikasi yang bisa dilakukan tanpa perangkat: nama API benar-benar ada di JAR,
kode fitur benar-benar ada di dex APK, dan kunci DataStore punya nama yang stabil
(mengganti nama kunci = membuang setelan milik pengguna yang sudah menyimpannya).

Lihat `references/scrobbling-and-event-reporting.md` untuk aturan kapan sebuah
listen dianggap selesai, dan kontrapola pencatatan yang sudah terbukti dalam
arsitektur player.