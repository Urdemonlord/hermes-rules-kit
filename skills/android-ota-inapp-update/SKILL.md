---
name: android-ota-inapp-update
description: "Use when an Android app updates itself in-app."
---

# In-app self-update (OTA) untuk Android

## Kapan skill ini dipakai

App mengunduh APK-nya sendiri lalu menyerahkan ke installer sistem:
manifest `update.json` di web, downloader, `FileProvider`, tombol Pasang,
skrip rilis.

Bukan untuk: distribusi lewat Play Store, atau analisis APK pihak ketiga
(itu `android-apk-reverse-engineering`).

## Jebakan utama: `<cache-path path="...">` berarti DIREKTORI, bukan nama berkas

Ini jebakan yang paling mahal di skill ini, karena gejalanya menipu dan
tidak pernah hilang sendiri.

```xml
<!-- SALAH -->
<cache-path name="update_apk" path="update.apk" />
```

Atribut `path` pada `<cache-path>` dibaca sebagai **direktori relatif ke
cacheDir**, bukan sebagai nama berkas. Jadi yang terdaftar sebagai root
adalah `cacheDir/update.apk` — yaitu berkas yang akan dipasang itu sendiri.

`FileProvider$SimplePathStrategy.getUriForFile` (androidx.core) melakukan:

```java
if (path.startsWith(rootPath)) {
    if (SEPARATOR.equals(path.substring(rootPath.length()))) {
        path = path.substring(rootPath.length());
    } else {
        path = path.substring(rootPath.length() + 1);   // melempar
    }
}
```

`path` dan `rootPath` sama persis, jadi `startsWith` benar dan
`substring(len + 1)` dipanggil pada string yang sudah habis:

```
StringIndexOutOfBoundsException: length=58; index=59
```

**Angka di pesan itu bukan tebakan.** `length` adalah panjang absolut path
berkas tersebut. Hitung ulang dari `applicationId` + nama berkas; kalau
cocok, root cause terkonfirmasi tanpa perlu perangkat atau logcat. Ini
mengubah "dialog hilang" jadi bug yang bisa dibuktikan.

**Perbaikan:**

```xml
<cache-path name="update_apk" path="." />
```

`path="."` mendaftarkan cacheDir sebagai root, sehingga hasil substring-nya
`update.apk` dan URI terbentuk benar.

Perbaikan ini **hanya benar karena kanonikalisasi**: `addRoot` melakukan
`new File(context.getCacheDir(), attr)` lalu menyimpan
`getCanonicalPath()`-nya, dan `new File(dir, ".")` menghasilkan `dir/.` yang
lalu menjadi `dir`. Tanpa langkah itu, `startsWith` bernilai false dan
error berubah bentuk dari crash ke `IllegalArgumentException: Failed to find
configured root` — tetap rusak, cuma kelihatan berbeda. Verifikasi dengan
probe Java asli, bukan reasoning:

```java
new java.io.File(cacheDir, ".").getCanonicalPath();   // -> cacheDir
```

## Tambahkan cache-path kedua? Ulangi assertion-nya, jangan tambah angkanya

Setelah `path="."` benar, masih godaan menambah cache-path lain saat fitur
baru butuh file yang dibagikan (kartu share, screenshot, ekspor). Yang
benar: tambah `<cache-path name="..." path="folder/"/>` dan **perbaiki test
kontrak di sesi yang sama** — bukan di rilis berikutnya.

Test kontrak di atas punya assertion berbentuk:

```kotlin
assertEquals("file_paths.xml harus punya tepat satu <cache-path>",
             1, doc.getElementsByTagName("cache-path").length)
```

Assertion itu **salah**, dan akan redden begitu cache-path kedua subtracted.
Yang dijaga sebenarnya adalah dua invarian: ada root yang mencakup
`update.apk`, dan tidak ada root yang keluar dari `cacheDir`. Cardinality
bukan salah satu dari keduanya.

Ganti dengan batas, bukan jumlah:

```kotlin
val cacheNodes = doc.getElementsByTagName("cache-path")
assertTrue("tidak ada <cache-path>; installer tidak bisa menjangkau update.apk",
           cacheNodes.length > 0)
for (i in 0 until cacheNodes.length) {
    val attr = (cacheNodes.item(i) as Element).attributes.getNamedItem("path").nodeValue
    assertFalse("<cache-path path=\"$attr\"> keluar dari cacheDir",
               File(attr).isAbsolute || attr.split("/").contains(".."))
}
```

Dua untung sekaligus: cache-path kedua tidak lagi merusak CI, dan pesan gagalnya menyebut nilai
`path` yang salah sehingga langsung menunjuk culprit-nya — bukan "harus punya
tepat satu" yang menyuruh pembaca mencari.

Setelah mengganti assertion, cek test lain di file yang sama: helper yang
mengembalikan daftar dari semua elemen tetap aman, helper yang mengambil
`item(0)` tidak.

## Jangan perluas jangkauan FileProvider demi memperbaiki ini

`path="."` cukup untuk membuka cacheDir. Menambahkan `<external-path>`,
`<root-path>`, atau `<external-files-path>` "agar pasti" jalan adalah
memperbesar jalan masuk ke storage user tanpa perlu. Kalau memang butuh
external, itu keputusan tersendiri yang harus disebut eksplisit — bukan
efek samping dari memperbaiki bug.

## Test harus menguji KONTRAK dua file, bukan masing-masingnya

Bug di atas bertahan belasan rilis karena **tidak ada yang menghubungkan**
`res/xml/file_paths.xml` dengan nama berkas yang dipakai downloader. Dua
file itu bisa tidak sinkron tanpa apa pun yang protes, dan tidak
sinkronnya baru ketahuan saat user menekan tombol.

Test kontrak bridging membuat ketiganya satu kesatuan:

1. Baca path yang terdaftar dari XML dengan parser (`javax.xml.parsers`
   sudah ada di JDK) — bukan regex atas teks mentah.
2. Baca nama berkas yang dipakai downloader **dari sumbernya** dengan
   regex, bukan tulis ulang sebagai literal test. Kalau downloader ganti
   nama, test ikut menangkap.
3. Jalankan tiruan algoritme FileProvider atas kombinasi keduanya, dan
   pastikan konfigurasi **lama** masih menghasilkan kondisi gagal
   (regresi terbukti, bukan diasumsikan).

## Tiruan algoritme library: salin SEMUA langkahnya, bukan intinya

Tiruan separuh jalan menghasilkan test yang gagal karena alasan yang salah —
lalu membuat Anda "memperbaiki" implementasi yang sebenarnya sudah benar.

Kasus nyata: tiruan `SimplePathStrategy` menyalin `substring(len + 1)` tapi
melewatkan `getCanonicalPath()`, sehingga root `cache/.` dicocokkan apa
adanya dan tidak pernah cocok dengan `cache/update.apk`. Test gagal, dan
bentuk gejalanya ("tidak terjangkau sama sekali") mirip dengan kegagalan
sebenarnya — tapi penyebabnya beda: kode produksi sudah benar, yang salah
adalah tiruannya.

Aturan: **sebelum percaya test tiruan, jalankan algoritme itu dengan Java
(asli) pada masukan nyata dan bandingkan keluarannya.** Kalau keduanya
tidak sama, tiruannya yang salah — bukan kodenya.

## Jangan grep tag terlarang di teks mentah XML

Mencari `"<external-path"` di teks mentah file akan cocok dengan komentar
yang justru **menjelaskan larangannya**. Gunakan elemen DOM:

```kotlin
DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
    .getElementsByTagName(tag).length   // 0 = benar-benar tidak ada
```

## `versionCode` harus naik monotonik; `versionName` untuk manusia

`update.json` dibandingkan terhadap `versionCode` terpasang, bukan nama.
Naikkan `versionCode` di setiap rilis, termasuk hotfix — rilis dengan nama
besar tapi `versionCode` sama tidak akan pernah menawarkan update ke user
yang sudah di versi itu.

## Signature harus identik, atau OTA tidak bisa menimpa

APK yang update di atas APK sebelumnya **wajib** ditandatangani key yang
sama. Kalau tidak, installer menolak dan user dipaksa uninstall (data
hilang). Bandingkan sebelum rilis:

```bash
apksigner verify --print-certs app-release.apk     # signer SHA-256
keytool -list -v -keystore debug.keystore
```

**Keystore debug yang dibuat baru tiap run CI berganti kunci setiap build**, jadi
dua rilis berturut-turut tidak bisa saling menimpa — dan itu baru terlihat setelah
ada user yang memasang rilis pertama. Rilis publik butuh kunci tetap yang
disalurkan ke CI sebagai secret; resep membuat dan memasangnya ada di skill
`android-fork-rebrand` bagian "Kunci rilis".

## Pisahkan tiga tahap secara eksplisit saat diagnosa

"Memasang update gagal" bisa berarti tiga hal berbeda, dan mengabaukannya
membuat user (dan Anda) mengejar bug yang salah:

| Tahap | Gejala | Bukti |
|---|---|---|
| Discovery | dialog tidak muncul / versi salah | respons manifest |
| Download | progres atau unduhan gagal | file di cache, ukuran |
| Install | dialog installer tidak naik, atau crash | `content://` URI, installer sistem |

Dialog yang menampilkan "Versi X tersedia" **hanya** membuktikan tahap
discovery — belum download, belum install, belum signature.

## Jangan pernah menelan kegagalan di jalur instalasi

Exception dari installer sistem harus tampil sebagai pesan, bukan hilang.
Tangkap `Throwable`, bukan hanya `Exception` — `NoClassDefFoundError`,
`NoSuchMethodError`, dan `StringIndexOutOfBoundsException` bukan subclass
`Exception` sehingga lolos dari `catch (e: Exception)`.

Perhatikan efek sampingnya: menangkap `Throwable` membuat bug yang tadinya
tidak terlihat menjadi terlihat. Itu bagus, tapi jelaskan ke user bahwa
pesan yang lebih aneh berarti lebih banyak bukti, bukan regresi.

## Rilis harus meninggalkan tag, dan tag dibuat setelah verifikasi

Tag `v<versionName>` adalah satu-satunya cara menjawab "versi mana yang sudah
tayang" dari riwayat repo. Kalau skrip rilis tidak pernah menyentuh git, history
tertinggal puluhan versi dan jawaban itu harus dicari ke server — yang sering
mati, karena hosting APK lama dihapus.

- Tag dibuat **setelah** verifikasi checksum ter-deploy. Tag untuk versi yang
  gagal dipasang tidak bisa ditarik kembali.
- Tag yang sudah ada dilewati, bukan ditulis ulang: tag lama menunjuk commit
  rilis asli, yang bisa sudah tidak menjadi HEAD sekarang.
- Skrip menolak men-tag kalau `HEAD:app/build.gradle.kts` belum mendeklarasikan
  `versionName` itu — kalau tidak, tag yang terlihat benar diam-diam menunjuk
  versi lain.
- Kalau tag tertinggal jauh dan harus diisi ulang, jangan menebak commitnya.
  Turunkan `versionName` dari tiap commit yang menyentuh build file, dan
  **validasi metodenya terhadap tag yang sudah ada** sebelum percaya hasilnya.

## Tes penjaga yang membaca teks skrip: mutation check wajib

Tes berbentuk `assertTrue(skrip.contains("..."))` untuk menjaga skrip rilis
mudah hijau tanpa menjaga apa pun. Contoh nyata: skrip memakai
`git -C "$REPO_ROOT" tag -a`, jadi teks `git tag` tidak pernah muncul, dan
asersi atas `git tag` hanya menguji inventaris.

Dua langkah wajib:

1. **Cocokkan substring yang benar-benar ada.** Buktikan dengan mencari string
   itu di berkas, bukan dengan menebak bentuk perintahnya.
2. **Mutation check.** Ubah skrip di memori dua kali: hapus blok fiturnya, lalu
   pindahkan blok itu ke sebelum verifikasi. Kalau asersi tetap hijau pada
   kedua mutasi, tesnya tidak berguna.

Logika shell yang merusak server tidak boleh dijalankan untuk tes. Ambil bloknya
ke `git clone . /tmp/x`, jalankan cabangnya di sana (tag baru / versi tidak
cocok / tag sudah ada), lalu pastikan repo utama tidak ikut berubah.

## Workflow rilis yang dipicu tag mengubah urutannya — dan tidak mengaktifkan OTA

Kalau repo punya `.github/workflows/release.yml` dengan `on: push: tags:`, tag adalah
**pemicu build**, bukan penanda sesudah verifikasi. Dua konsekuensinya, dan keduanya terlihat
seperti rilis sukses dari halaman GitHub:

- **Prasyarat harus lengkap SEBELUM tag di-push.** Tag yang tidak sama dengan `versionName` di
  `app/build.gradle.kts` ditolak langkah `Check tag matches versionName` — proteksi yang memang
  dipasang supaya APK tidak mengaku versi lain. Urutan yang benar: bump `versionCode` **dan**
  `versionName` → taruh entri changelog untuk versi itu → commit → push → baru tag → push tag.
  Entri changelog yang terlewat tidak menggagalkan build; akibatnya catatan rilis terbit kosong.
- **Terbitnya GitHub Release bukan OTA aktif.** Build tag hanya membangun APK, menerbitkannya
  sebagai aset Release, dan mengunggah `changelog.json`. Selama skrip deploy belum dijalankan,
  `update.json` di web root masih menunjuk versi sebelumnya dan **tidak ada satu pun perangkat
  terpasang yang melihat versi baru.** Buktikan dari manifest publiknya, bukan dari halaman
  Release yang hijau:

  ```bash
  curl -fsS https://<domain>/update.json \
    | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['versionName'], d['apkUrl'])"
  ```

  Laporkan "rilis terbit" dan "OTA aktif" sebagai dua fakta terpisah. Menggabungkannya membuat
  user mengira HP-nya sudah kebagian update, padahal belum ada yang berubah di sana.

## Ganti hostname: klien terpasang memanggil URL yang sudah mereka bawa

URL `update.json` dan URL APK ditanam di dalam APK yang sudah terpasang. Setelah host berganti
nama, vhost lama **tetap harus melayani** `update.json` beserta nama berkas APK lama; kalau tidak,
pemasangan yang belum diperbarui berhenti menerima update selamanya. Manifest baru boleh menunjuk
`apkUrl` ke host baru selama host itu hidup — klien lama sanggup mengunduh dari sana, yang tidak
bisa mereka lakukan hanyalah mencari manifest di sana. Verifikasi dengan membaca **kedua** host
(lama dan baru), bukan hanya yang baru saja selesai dikerjakan.

## Release: artifact CI, bukan build lokal

Build lokal inkremental; isi `build/` bergantung pada build sebelumnya, jadi
APK lokal dan APK CI bisa berbeda isi walau ukurannya sama. Yang layak
dirilis adalah artifact dari CI pada commit yang di-tag.

## Jangan serahkan APK yang nomor versinya sama dengan yang sudah terpasang

Saat menyerahkan APK langsung ke user (bukan lewat OTA), **bump `versionCode`
dan `versionName` plus entri changelog SEBELUM build yang menghasilkan APK itu**.
Build ulang pada versi yang sama tidak bisa dibedakan dari berkas lama di
perangkat: label versi satu-satunya sinyal yang user punya, dan installer bisa
terlihat tidak mengganti apa pun. User berhak menyebutnya aplikasi lama — dan
tidak ada bukti di layar yang membantahnya.

Kalau terlanjur build sebelum bump, jangan kirim artifact itu; bump, push,
tunggu run baru, baru kirim. Menjelaskan "isinya sebenarnya baru" setelah user
marah adalah round trip yang bisa dihindari satu baris versi.

Sebelum mengirim, buktikan identitas berkasnya, bukan cuma namanya:

```bash
aapt dump badging app-universal-foss-release.apk | head -1   # versionCode/versionName
apksigner verify --print-certs app-universal-foss-release.apk | head -2
```

Label versi saja masih bisa bohong soal isi. Untuk perubahan yang punya nilai
khas (konstanta warna baru, string resource baru), cek langsung ke dalam APK:
konstanta `Color(0xFF…)` ada sebagai little-endian 4-byte di `classes*.dex`,
string resource ada di `resources.arsc`; `unzip -p` + pencarian byte sudah
cukup untuk membuktikan build itu memang memuat perubahan yang dimaksud.

## Rilis hanya setelah CI hijau penuh dan test benar-benar jalan

Compile + lint + test tidak membuktikan apa pun soal runtime. Yang penting
bukti jumlah test: centang hijau tidak berarti ada test yang dieksekusi.
Unduh laporan test dari CI dan parse jumlahnya sebelum menyatakan rilis
aman — rilis tanpa test khusus fitur baru adalah hasil yang belum diuji, dan
hanya terlihat di perangkat user.

Dua jebakan saat mengambil laporan itu, keduanya tidak ada di `--help`:

```bash
rm -rf /tmp/rep-fresh          # direktori tujuan harus baru tiap download
gh run download <RUN_ID> -n <artifact-test-report> -D /tmp/rep-fresh
```

- **Download kedua ke direktori yang sama** gagal dengan
  `error extracting zip archive: ... file exists` — pesannya tidak menyebut
  download sama sekali.
- **Artifact laporan test berupa HTML, bukan XML.** `TEST-*.xml` tidak ikut,
  jadi `glob('**/TEST-*.xml')` mengembalikan nol suite padahal ratusan test
  jalan — dan nol suite itu terbaca "tidak ada test". Angkanya ada di
  `index.html` (`<div class="counter">`) dan daftar kelas di direktori
  `classes/`.

Lihat `references/release-checklist.md` untuk urutan rilis lengkap beserta
verifikasi tiap langkah.