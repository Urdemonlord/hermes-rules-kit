---
name: android-fork-rebrand
description: Use when rebranding an Android fork into your own app.
category: android
version: 1.0.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [android, fork, rebrand, gpl, package-rename]
    related_skills: [android-ci-only-feature-development, android-ota-inapp-update]
---

# Rebrand fork Android jadi aplikasi sendiri

## When to Use — kapan skill ini dipakai

User minta "clone dan remake" repo Android milik orang lain — biasanya pemutar
musik GPL-3.0 — jadi aplikasi dengan nama, package, dan repo sendiri.

Bukan untuk: menambah fitur ke fork yang sudah di-rebrand (itu
`android-ci-only-feature-development`) atau menerbitkan rilisnya.

## Aturan yang berlaku di setiap instance

- **Lisensi dibaca sebelum satu berkas disentuh.** Baca `LICENSE` dan README
  upstream, lalu katakan konsekuensinya apa adanya: kode GPL-3.0 yang jadi
  basis mewajibkan aplikasi turunan tetap GPL-3.0, sumbernya dibuka, dan
  atribusinya dipertahankan. Permintaan penulis di README ("jangan
  di-monetize") bukan syarat lisensi — GPL-3.0 §7 melarang tambahan restriksi —
  tapi sampaikan itu sebagai fakta, bukan nasihat hukum.
- **Rename mekanis dulu, keputusan desain kemudian.** Package, nama app, nama
  proyek Gradle, versi = satu lapisan. Ikon, palet, dan tautan akun = lapisan
  berikutnya, dan yang belum dikerjakan **disebut di laporan + README**, bukan
  didiamkan.
- **Jangan rename namespace modul provider.** `com.music.*` / `com.my.kizzy`
  milik library upstream; mengubahnya memperbesar diff dan menyulitkan sinkron
  upstream. Yang di-rename hanya identitas app (`com.example.<app>`).
- **Verifikasi pakai `git grep`, bukan mata.** Setelah rename, hitungan sisa
  kata harus **nol** untuk semua varian huruf besar-kecil.
- **Identitas upstream lebih banyak daripada tautan GitHub.** Sisir semuanya
  sebelum melapor selesai: kanal donasi (Ko-fi, Sociabuzz, Buy Me a Coffee)
  beserta konstanta URL-nya, tautan sosial (Instagram), avatar pengembang basis
  di kartu Tentang, kalimat yang mengklaim diri ("I'm the main dev here"), dan
  URL yang ditanam di RPC/catatan pembaruan. Satu grep menemukan hampir semua:

  ```bash
  grep -rniE 'kofi|sociabuzz|buymeacoffee|instagram|<handle-basis>' --include='*.kt' .
  ```

  Tanya **sekali** (repo public/private, akun penggantinya, tautan mana yang
  dipakai), lalu kerjakan di commit yang sama. Tanpa akun pengganti, **hapus**
  barisnya — menunjuk ke halaman donasi yang tidak ada lebih buruk daripada
  tidak punya baris itu sama sekali. Salinan yang menggantung (layar donasi yang
  isinya nol kanal, teks ajakan milik pengembang basis) ikut disebut sebagai
  pekerjaan terbuka, bukan didiamkan.

## Varian: ganti nama app yang sudah dirilis (bukan fork baru)

Kadang permintaannya bukan rebrand fork, tapi **ganti/tukar nama** app yang sudah
punya user, rilis, domain, dan server unduhan. Aturannya berbeda, dan yang paling
penting: `applicationId` tidak ikut diganti.

- **`applicationId` app yang sudah terpasang tidak berubah.** ApplicationId baru
  = Android melihat app yang berbeda: install lama harus di-uninstall → Room,
  DataStore, playlist, unduhan offline, dan widget hilang, dan OTA putus karena
  user tidak akan pernah menerima versi baru. Yang berubah cukup label, teks,
  host, nama artefak, repo, dan dokumen hidup.
- **Dua app tidak bisa berbagi satu `applicationId` di satu perangkat.** Kalau
  nama ditukar antara dua app, pihak yang belum punya user boleh pindah paket
  (murah, satu rilis), pihak yang punya user tetap di paket lamanya. Sebutkan
  konsekuensinya apa adanya: paket ≠ label itu tersembunyi dari user.
- **Rename ini minimal-diff, bukan rename simbolis.** Ganti yang **user-lihat**
  (label, teks share/Tentang, konstanta endpoint, nama berkas APK, nama aset
  rilis, skrip rilis, README, dokumen hidup) dan **biarkan** simbol kode
  (`<Brand>Colors`, nama tema, skema URI internal, nama folder unduhan). Diff
  ribuan baris untuk nama kelas tidak menghasilkan apa pun bagi user. Sisa yang
  memang ditinggal **disebut di laporan**, jangan didiamkan.
- **Endpoint di dalam app hanya pindah setelah hostname baru melayani**, dan
  hostname lama tetap hidup untuk klien terpasang (urutan vhost + sertifikatnya
  ada di `domain-redirect-and-hostname-routing`).
- **Nama folder unduhan biasanya terikat ke pemindaian library.** Kalau app
  mengecualikan folder unduhannya dari `MediaStore`, mengganti nama folder
  membuat berkas lama dipindai sebagai duplikat dan status unduhan tampak
  hilang. Kecualikan **kedua** nama folder, atau jangan diganti.
- **Setiap daftar/allowlist yang memvalidasi nama artefak ikut berubah di commit
  yang sama.** Service penghitung unduhan, regex nama APK, dan nama aset rilis
  harus menerima nama baru — kalau tidak, `/dl/<APK baru>` menjawab 404 tanpa
  error apa pun di app, dan hanya ketahuan saat mencoba mengunduh.
- **Rename repo dikerjakan di tempat, dan urutannya: kosongkan nama dulu.** GitHub
  hanya menerima satu repo per nama di satu akun (tanpa beda huruf besar-kecil),
  jadi kalau nama tujuan masih dipakai repo lain, pindahkan repo lama itu dulu:

  ```bash
  gh api -X PATCH repos/<owner>/<lama-lain> -f name=<nama-pengganti> \
    -f description="di-rename supaya <tujuan> bisa dipakai"
  gh api -X PATCH repos/<owner>/<lama-ku> -f name=<tujuan>
  git remote set-url origin https://github.com/<owner>/<tujuan>.git
  git ls-remote origin refs/heads/main      # push masih hidup di nama baru
  ```

  Redirect dari nama lama membuat clone dan tautan lama tetap jalan, tapi remote
  lokal harus ikut diperbarui — kalau tidak, laporan dan perintah berikutnya
  menunjuk nama yang sudah tidak ada.
- **Izin mengikuti pemilik repo, bukan akun yang login.** `gh` yang berperan
  sebagai akun A tidak bisa mengubah repo akun B; jalankan perintah itu dengan
  token pemiliknya (`GH_TOKEN=<token> gh api ...`, cara mengambilnya ada di
  `github-auth`). Ini berlaku untuk rename repo dan set secret.
- **Rename label tidak butuh rilis.** User baru melihat nama baru di rilis
  berikutnya, jadi jangan menerbitkan rilis kosong hanya untuk menampilkan nama —
  dan jangan menaikkan versi kalau changelog-nya tidak punya isi.
- **Sesudah nama ditukar, nama app bukan penunjuk yang unik.** Kalau dua app bertukar
  nama (`~/player` = the music app, `~/musicfy` = the player), kalimat seperti "app
  the music app masih pakai palet lama" tidak menunjuk apa pun — pembaca harus menebak,
  dan pertanyaan balik seperti "kok X yang diubah?" adalah gejalanya. Setiap kalimat
  laporan, setiap opsi pertanyaan, dan setiap ringkasan menyebut ketiganya: **direktori
  + nama sekarang + paket** (tambah repo/hostname kalau itu pokok kalimatnya). Nama
  lama saja tidak pernah cukup: justru nama itulah yang berpindah tempat.
- **Catatan vault ditukar isinya juga, bukan cuma isinya di-update.** Nama berkas
  catatan harus sama dengan nama app sekarang (berkas `Projects/<nama>.md`), dengan
  header "nama tukar" berisi nama lama dan alasan `applicationId` tetap, supaya sesi
  berikutnya tidak membaca catatan lama sebagai kebenaran sekarang.

## Prosedur

### 1. Inventaris sebelum mengubah apa pun

```bash
grep -rhoE '^\s*(namespace|applicationId)\s*=\s*"[^"]+"' --include=build.gradle.kts . | sort | uniq -c
grep -rhoE '^package [a-zA-Z0-9_.]+' --include=*.kt . | sort | uniq -c | sort -rn | head -20
find . -type d -path "*com/example*" -not -path "./.git/*"
grep -ril "<brand>" . | grep -v "^./.git/" | wc -l
grep -nE "versionCode|versionName|compileSdk|minSdk|jvmToolchain" app/build.gradle.kts | head
grep -n "distributionUrl" gradle/wrapper/gradle-wrapper.properties
grep -nE "^(kotlin|androidGradlePlugin|compose|room|hilt)\s*=" gradle/libs.versions.toml | head
```

Yang dicari: package app, namespace tiap modul, **source set non-standar**
(`app/src/foss/`, `app/src/gms/`, `app/src/debug/` — masing-masing bisa punya
`com/example/<app>/` sendiri), daftar flavor, dan versi toolchain (menentukan
JDK CI).

### 2. Hapus identitas upstream — dan pasang CI sendiri di commit yang sama

CI upstream adalah **satu-satunya compiler** kalau build lokal dilarang. Kalau
berkas CI upstream dihapus tanpa penggantinya, repo jadi tanpa cara membuktikan
apa pun.

**Baca berkas CI upstream dulu, baru hapus.** Yang harus dibawa ke workflow
pengganti bukan cuma nama task-nya, tapi **prasyarat runner** yang dia siapkan:
generate `debug.keystore`, versi JDK, submodule, variabel lingkungan.

```bash
git show HEAD:.github/workflows/build.yml \
  | grep -nE 'keytool|keystore|java-version|submodules|env:' -A8
```

```bash
git rm -rq "<banner>.png" Roadmap.md crowdin.yml build.sh fastlane/ assets/ docs/ \
  .github/CONTRIBUTING.md .github/pull_request_template.md \
  .github/workflows/build.yml .github/workflows/build_pr.yml .github/workflows/stale.yml
```

Yang **jangan** dihapus: `LICENSE`, `gradle/`, `scripts/` yang masih relevan,
`renovate.json` (tidak berbahaya).

### 3. Rename mekanis — pakai `scripts/rebrand_fork.py`

Skrip itu melakukan tiga langkah **berurutan**, dan urutannya yang penting:
pindahkan direktori paket (`git mv`) → ganti token di berkas teks → pindahkan
berkas yang **namanya** memuat brand. Jalankan `--dry` dulu, dan jalankan pada
working tree yang bersih.

```bash
python3 scripts/rebrand_fork.py --root ~/<repo> \
  --pkg-from com.example.<lama> --pkg-to com.meowlabs.<baru> \
  --brand-from <lama> --brand-to <baru> --dry
```

### 4. Perbaikan yang tidak bisa dilakukan token replace

Urutannya sesuai daftar periksa ini, karena masing-masing menghasilkan error
compile yang menyebut simbol yang "jelas ada":

- **Nama berkas resource.** `ic_<brand>_mark.xml`, `values-*/<brand>_strings.xml`,
  `license_<brand>.xml`. Kode sudah menunjuk `R.drawable.ic_<baru>_mark`
  sementara berkasnya masih bernama lama → `Unresolved reference`.
- **Token huruf besar.** `MUSICFY` di nama enum dan teks recap tidak tertangkap
  replace `Musicfy`/`musicfy`.
- **Nama app dengan huruf besar.** Hasil replace memberi `>music-app<`; yang
  benar `>the music app<` — perbaiki di `res/values/app_name.xml` **dan** varian
  flavor/debug-nya.
- **Direktori skema Room harus sama dengan FQCN kelas database.** Rename token
  pada path menghasilkan `com.example.<baru>.db.InternalDatabase`; yang benar
  `com.meowlabs.<baru>.db.InternalDatabase`. Bandingkan dengan `@Database`
  class-nya sebelum push. Kalau `pkg_to` memakai akar lain (`id.`), namanya
  mengikuti `pkg_to`, bukan hasil replace brand — dan nama itu adalah FQCN
  lengkap, bukan `com/...` sisa dari paket lama.
- **Konstanta owner/repo updater.** Cari `GithubOwner`/`GithubRepo` dan URL
  `github.com/<owner>/<repo>` di modul updater, changelog, dan commit screen.
  Token replace juga menulis ulang URL upstream jadi bentuk yang salah
  (`<baru>-app/<baru>`) — perbaiki eksplisit, jangan dibiarkan.
- **Versi direset** ke `0.1.0` / `versionCode 1`, plus `rootProject.name`.

### 5. Atribusi dan dokumen

Tulis `NOTICE.md`: lisensi basis, alasan GPL-3.0, kewajiban pendistribusi
ulang, tabel perbedaan dari basis (package, nama, versi, CI, berkas yang
dihapus), dan daftar proyek yang menjadi dasar — README upstream biasanya
menyebutnya berlapis (basis app, framework, provider lirik, penyedia stream).
Ganti README dengan milik sendiri, dan tulis **apa yang belum dikerjakan**
(ikon, palet, tautan akun, belum diuji di perangkat) di sana.

### 6. CI sendiri

Ambil pola dari repo Android lain milik user: `setup-java` sesuai
`jvmToolchain(...)`, task per-varian yang benar, `retention-days` pendek,
laporan tes dengan `continue-on-error`. Dua dimensi flavor (`abi` × `variant`)
menghasilkan nama task panjang:

```
:app:assembleUniversalFossDebug
:app:lintUniversalFossDebug
:app:testUniversalFossDebugUnitTest     # plus :modules:*:test untuk modul JVM murni
```

**Baca workflow basis sampai habis sebelum menghapusnya.** Langkah yang terlihat
seperti urusan lingkungan (`keytool`, generate keystore, `sed` versi) adalah
satu-satunya alasan CI mereka bisa jalan — dan tidak akan pernah muncul di
log error sebagai "config hilang", hanya sebagai task `validateSigning*` gagal.

**Verifikasi lokasi artefak dari log runner, bukan dari nama task.** Berkas APK
**tidak** ada di `apk/<flavor>/<buildType>/`. Dua dimensi flavor digabung jadi
satu direktori bernama flavor gabungan: task `assembleUniversalFossDebug`
menulis ke `app/build/outputs/apk/universalFoss/debug/*.apk` (pola yang sama
seperti basis memakai `universalGms`). Path yang salah membuat langkah unggah
dan verifikasi gagal beberapa detik setelah `BUILD SUCCESSFUL` — jobnya merah padahal APK-nya
sudah jadi, dan log `--log-failed` cuma memuat langkah unggah yang gagal.
Awali langkah verifikasi dengan jalan keluar yang mencetak isi direktorinya,
supaya kegagalan path berikutnya menjelaskan dirinya sendiri:

```bash
APK=$(ls app/build/outputs/apk/universalFoss/release/*.apk 2>/dev/null | head -1)
[ -n "$APK" ] || { echo "::error::APK tidak ada di outputs/apk; isinya:"; \
  find app/build/outputs/apk -name '*.apk'; exit 1; }
```

Prasyarat runner yang wajib ada di **setiap** job yang meng-assemble — tanpa
ini job merah di `:app:validateSigning*` sebelum satu baris pun dikompilasi,
karena AGP menandatangani varian debug dengan `~/.android/debug.keystore` yang
tidak ada di runner:

```yaml
      - name: Generate debug.keystore
        run: |
          set -euo pipefail
          mkdir -p ~/.android
          keytool -genkeypair -v -keystore ~/.android/debug.keystore \
            -storepass android -keypass android -alias androiddebugkey \
            -keyalg RSA -keysize 2048 -validity 10000 \
            -dname "CN=Android Debug,O=Android,C=US"
```

Varian rilis pun butuh langkah ini selama secrets rilis belum ada, karena
`build.gradle.kts` yang belum menemukan kunci rilis jatuh ke debug keystore.

### 7. Serah terima repo

Repo baru dibuat di akun yang user sebut, dan itu keputusan yang tanyakan
sekali. Bentrok nama hanya berlaku di dalam satu akun, tapi di sana GitHub
memperlakukan nama repo tanpa beda huruf besar-kecil: bentuk judul dan bentuk
huruf kecil tidak bisa hidup bersama, jadi repo lama bernama sama di akun itu
diganti nama dulu, bukan ditimpa.

```bash
# bikin repo pakai token pemilik barunya
curl -s -X POST -H "Authorization: token $TOK" \
  -H 'Accept: application/vnd.github+json' \
  -d '{"name":"<app>","private":false}' https://api.github.com/user/repos

git remote rename origin upstream      # jalur sinkron basis, jangan hilang
git remote add origin https://github.com/<owner>/<repo>.git   # tanpa token di URL
git push "https://x-access-token:$user@example.com/<owner>/<repo>.git" main
```

Token disimpan untuk satu perintah push saja, bukan di URL remote: URL yang
memuat token ikut tertulis di `.git/config` dan di setiap laporan remote. Operasi
milik pemilik repo (bikin repo, batal run) butuh token akun itu — `gh` yang
login sebagai akun lain hanya bisa membaca repo public.

Owner dan nama repo final adalah input dari langkah 4: konstanta updater dan
semua URL `github.com/<owner>/<repo>` harus menunjuk ke sana sebelum commit
pertama, dalam huruf kecil seperti nama repo sebenarnya.

### 8. Kunci rilis — satu kunci, dipakai tiap rilis

Rilis publik **tidak boleh** ditandatangani debug keystore. Keystore debug di
runner dibuat baru tiap run, jadi tanda tangannya berganti tiap build dan APK
berikutnya tidak bisa menimpa yang sudah terpasang (installer menolak, user
harus uninstall dan kehilangan data). Rilis pertama adalah saat kunci itu
ditetapkan: menggantinya setelah ada yang memasang berarti memutus jalur update
untuk semua orang. Karena itu kunci rilis dibuat **sebelum** tag pertama, bukan
setelah ada keluhan.

Buat sekali, simpan di luar git, dan salurkan ke CI sebagai secret — keystore
base64 plus password, alias, dan key password:

```bash
mkdir -p app/keystore        # path ini masuk .gitignore
keytool -genkeypair -keystore app/keystore/release.keystore -storetype PKCS12 \
  -alias <app> -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass "$PW" -keypass "$PW" -dname "CN=<app>, O=<org>, C=ID"
openssl base64 -A -in app/keystore/release.keystore > /tmp/ks.b64
GH_TOKEN=$TOK gh secret set RELEASE_KEYSTORE_B64 -R <owner>/<repo> < /tmp/ks.b64
GH_TOKEN=$TOK gh secret set STORE_PASSWORD -R <owner>/<repo> --body "$PW"
```

Password disimpan di berkas kredensial **di sebelah keystore, di luar repo**, dan
diserahkan ke user untuk di-back-up. Hanya token pemilik repo yang bisa menulis
secret; `gh` yang login sebagai akun lain ditolak. Verifikasi dengan
`gh secret list -R <owner>/<repo>` — menyetel secret membuktikan perintahnya
jalan, bukan isinya terpasang.

Lalu di CI, sebelum Gradle: decode keystore dari secret, dan teruskan variabel
yang dibaca `build.gradle.kts` pada langkah build-nya.

```yaml
      - name: Decode release keystore
        env:
          KEYSTORE_B64: ${{ secrets.RELEASE_KEYSTORE_B64 }}
        run: |
          set -euo pipefail
          if [ -z "$KEYSTORE_B64" ]; then exit 0; fi
          mkdir -p app/keystore
          echo "$KEYSTORE_B64" | base64 -d > app/keystore/release.keystore
```

Kecocokan nama variabel itu yang menentukan: kalau salah satu kosong, Gradle
diam-diam jatuh ke debug keystore dan APK-nya tetap "rilis" — R8 jalan, tidak
debuggable, ukurannya masuk akal — hanya sertifikatnya yang salah. Jadi langkah
verifikasi wajib **menolak** sertifikat debug, bukan cuma mencetaknya:

```bash
CERTS=$("$APKSIGNER" verify --print-certs "$APK" | grep -E 'certificate DN|SHA-256 digest')
echo "$CERTS"
echo "$CERTS" | grep -q 'CN=Android Debug' && \
  { echo "::error::APK rilis ditandatangani debug keystore"; exit 1; }
```

## Jebakan

- **`git mv` direktori paket saja tidak cukup.** Deklarasi `package` di dalam
  berkas dan setiap `import` harus ikut, atau compiler melihat dua paket.
- **Akar paket jangan yang sering jadi nama variabel/properti.** Kotlin
  me-resolve FQN dari scope terdekat, jadi `id.meowlabs.<app>.ui.Foo()` gagal
  (`Unresolved reference 'meowlabs'`) di dalam lambda yang receiver-nya punya
  anggota `id` — `NavBackStackEntry.id`, properti umum di navigation-compose.
  Sama untuk akar `app`, `media`, `player`, `state`. Pakai akar yang tidak
  pernah jadi identifier (`com`, `io`, `dev`); kalau akar seperti itu sudah
  ditetapkan, ganti FQN inline jadi `import` + nama pendek — import tidak
  terpengaruh shadowing, dan satu berkas bisa memuat puluhan FQN inline.
- **Path paket mengikuti `pkg_to`, bukan brand.** `rename_files()` di skrip ini
  mengganti token brand pada *path* berkas, jadi `com.meowlabs.music-app`
  berpindah ke `com/meowlabs/player` walaupun `pkg_to` adalah
  `id.meowlabs.player`; source set flavor (`app/src/foss/`, `app/src/gms/`)
  bahkan tidak masuk daftar `SOURCE_BASES` sehingga berkas di sana dipindah ke
  path yang salah. Baca hasil dry run terhadap `pkg_to` sebelum menerapkan.
- **Nama berkas ≠ isi berkas.** Rename isi tanpa rename nama berkas (atau
  sebaliknya) menghasilkan error yang menunjuk simbol yang kelihatan ada.
- **Paket top-level di luar namespace app bisa ada** (`com/dpi/`, dst).
  Inventaris dulu; jangan asumsikan semua kode berada di bawah satu paket.
- **Tiga flavor berarti tiga aplikasi berbeda.** CI cukup membangun satu
  (biasanya `foss` universal); sebutkan yang lain belum diuji.
- **Menghapus CI upstream sebelum CI sendiri masuk** = repo tanpa compiler.
- **Kunci tanda tangan diputuskan SEBELUM tag pertama di-push, bukan sesudah.**
  Runner GitHub tidak punya debug keystore, dan yang dibuat di sana acak per run:
  APK rilis dari kunci itu tidak akan pernah bisa menimpa versi yang sudah
  terpasang (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`). Jadi: buat keystore rilis
  (RSA 4096, PKCS12), simpan di luar git, teruskan lewat secret
  (`RELEASE_KEYSTORE_B64` di-decode jadi `keystore/release.keystore` +
  `STORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD`), dan bikin langkah verifikasi
  menolak APK rilis yang DN-nya masih `CN=Android Debug`.
- **Verifikasi rilis dari luar, bukan dari halaman hijau.** Unduh aset publiknya:
  `sha256sum` dibanding checksum yang diterbitkan, `apksigner verify --print-certs`
  (digest harus sama dengan keystore), `aapt dump badging` (paket, versionName,
  minSdk). Halaman Release bisa terbit dengan aset yang salah di dalamnya.
- **`BUILD SUCCESSFUL` di Gradle bukan "job hijau".** Langkah unggah dan
  verifikasi punya path serta syaratnya sendiri; kegagalannya muncul sebagai
  `exit code 2` setelah build sukses.
- **Jangan dispatch manual kalau push sudah memicu run.** `concurrency` +
  `cancel-in-progress: true` berlaku lintas event: dispatch dan push ke ref yang
  sama berbagi satu grup, jadi yang mengantre membatalkan yang sedang jalan —
  lalu dispatch dibatalkan sendiri. Dua run mati, nol bukti. Backfill hanya
  setelah run push selesai.
- **Bentrok nama repo itu soal akun, bukan nama.** Nama repo case-insensitive
  dalam satu akun; kalau nama sudah dipakai repo lama (mis. situs statis 2024),
  pakai akun lain atau nama lain — jangan timpa tanpa izin.
- **Skrip rename itu operasi berurutan.** Kalau `git mv` gagal di tengah,
  jalankan ulang dari `--dry` dan baca mana yang belum pindah — jangan menambal
  dengan pengganti teks ad-hoc di tempat lain.
- **Repo bisa berlapis-lapis.** Upstream dari upstream (mis. app yang mengaku
  "musicfy" ternyata turunan repo lain) berarti atribusi harus menyebut
  keduanya; cek URL updater dan README untuk menemukan lapisan itu.
- **Skrip rename harus membuktikan daftar berkasnya sendiri.** Berkas yang isinya
  cuma brand (mis. `res/values/strings.xml`) tidak muncul di daftar berkas
  host/repo; kalau daftar target diambil dari sana, justru teks user yang tidak
  ikut berubah — dan dry-run tetap terlihat "sukses" karena melaporkan berkas
  lain. Baca daftar berkas di keluaran dry-run dan pastikan setiap berkas yang
  lo maksud ada di situ sebelum `--apply`.
- **Repo tujuan rename bisa sudah dipakai repo lain di akun itu.** Nama repo
  case-insensitive per akun, jadi cek dulu
  (`gh api repos/<owner>/<tujuan>`, `gh repo list <owner>`) sebelum menjanjikan
  nama repo baru; repo lama bernama sama harus diganti nama dulu, dan itu
  keputusan user.

## Batas bukti

"Nol sisa kata brand" hanya membuktikan teksnya bersih. Compile-nya baru
dibuktikan CI. Kegagalan pertama biasanya datang dari **prasyarat runner**
(keystore, JDK) atau dari nama task — dua hal yang tidak bisa dibuktikan dari
membaca kode, dan keduanya terlihat sama "pasti benar" saat ditulis. Sebutkan
itu di laporan — jangan klaim "sudah jadi" untuk hasil yang belum pernah
dikompilasi.