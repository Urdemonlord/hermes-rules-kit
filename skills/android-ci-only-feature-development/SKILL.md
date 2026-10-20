---
name: android-ci-only-feature-development
description: Use when an Android feature compiles only via CI.
category: android
---

# Fitur Android yang dikompilasi hanya oleh CI

## Kapan skill ini dipakai

Menulis fitur Android di repo yang build lokalnya dilarang — VPS shared,
RAM kecil, atau ada aturan repo yang melarang Gradle. CI adalah satu-satunya
compiler, jadi ini bukan workaround: itu memang alurnya.

Bukan untuk: build lokal yang boleh, atau fitur yang sudah hijau dan tinggal
dirilis (itu `android-ota-inapp-update`).

Perbedaan dari skill fitur Android lain: skill itu mengatur *apa* yang
dibangun. Skill ini mengatur *bagaimana* build-nya yang tidak bisa
dijalankan di mesin ini, dan compile error apa yang muncul sebagai akibatnya.

## Aturan yang berlaku di setiap instance

- **Jalur build lokal tetap di tempat yang sama.** Kalau ada `AGENTS.md`
  yang melarang Gradle di mesin ini, larangan itu mengikat fitur berikutnya
  juga — termasuk saat user bilang "lanjut".
- **Kegagalan CI pertama itu gate bekerja, bukan kesalahan approach.**
  Jangan menebak-nebak berulang sebelum push. Tapi begitu CI sudah
  menyebut **baris persisnya**, berhenti menebak di baris itu — baca
  kode yang sebenarnya, bukan rely pada ingatan syntax. Lihat bagian
  "Jangan menebak syntax".
- **Satu run gagal = satu hipotesis. Dua run gagal pada baris yang sama =
  hipotesis itu salah.** Menyusun fix kedua, ketiga, keempat pada
  penyebab yang sama adalah tanda tidak menguji asumsi, bukan tanda kurang
  gigih. Kalau struktur kode terus berubah sementara errornya tidak
  berubah, diagnosisnya salah — dan tiap struktur baru menutupi bukti yang
  masih ada di diff lama.
- **"Lanjut" berarti lanjut sampai habis, bukan berhenti buat nanya lagi.**
  Kalau user bilang lanjut dan masih ada langkah tersisa, kerjakan sampai
  commit + push + CI hijau, unduh APK, lalu lapor bukti. Jangan tutup turn
  dengan rangkuman status dan tawaran pilihan — user akan mengulang
  "lanjut" dengan nada kesal, dan instruksi yang diulang adalah kegagalan.
  Ringkasan hanya setelah daftar selesai atau ada blocker yang benar-benar
  butuh keputusan user.
- **Pisahkan yang terbukti dari yang diasumsikan di setiap laporan.**
  Compiler membenarkan bentuk; tidak ada yang memberitahukan bentuk itu
  benar di user surface. Lihat "Batas bukti".
- **Jawab pertanyaan status dengan status.** Kalau user tanya "udah
  rilis belum" atau "cek", jawaban pertama adalah hijau / merah / belum
  rilis beserta run ID-nya. Post-mortem dan daftar tebakan yang gagal
  menyusul setelah itu kalau relevan — bukan menggantikannya. Kalau sesi
  menyentuh lebih dari satu repo, **setiap run ID disertai nama app,
  direktorinya, dan repo-nya**: user yang mengelola beberapa app sekeluarga
  akan bertanya "ini run buat aplikasi yang mana" kalau yang disebut cuma
  nomor run — dan app yang bertukar nama membuat tebakan dari nama repo
  justru menyesatkan.
- **Naikkan versi dan asset changelog dalam satu commit.** Kalau ada
  test yang membandingkan entri teratas changelog dengan
  `BuildConfig.VERSION_NAME`, menaikkan `build.gradle.kts` saja akan
  menggigit di CI pada commit berikutnya.
- **Tidak ada yang terlihat dari membaca kode.** Sebagian besar error compile
  di satu sesi tidak terlihat di diff review. Compiler biasanya tidak
  sepakat dengan pembacaan kode.
- **Jangan pernah menyatakan jumlah test, jumlah file, atau jumlah error
  tanpa menghitungnya.** Angka yang dikira-kira jadi salah yang berulang,
  dan angka salah merendahkan credibility seluruh laporan.
- **"Pola sudah ada di repo" harus dibuktikan di call site, bukan di import.**
  `grep` nama API sering kena blok `import` di kepala file, bukan pemakaiannya.
  Yang membuktikan adalah pemanggilan (`launcher.launch(`, nama kontrak yang
  dipakai, modifier yang disisipkan). Lihat "Pola yang dikira ada".
- **Setelah setiap patch ke file sumber, baca ulang byte-nya di disk.** Laporan
  hasil tool bisa terlihat utuh sementara isinya korup. Lihat "Patch panjang
  merusak file".
- **Merah belum berarti kodemu salah.** Sebelum menyentuh satu baris kode,
  cek **langkah mana** yang gagal di job itu. Kegagalan di langkah unggah
  artifact memerahkan job padahal `./gradlew test` dan `assembleRelease` di
  atasnya `BUILD SUCCESSFUL`. Sebab yang sama bentuknya: **prasyarat runner**
  yang tidak ada. `:app:validateSigning*` merah karena runner tidak punya
  `~/.android/debug.keystore` — memperbaiki kode tidak mengubah apa pun di
  sana. Lihat "Job merah karena langkah bantu".
- **Kuota artifact itu milik AKUN, dan pemakannya biasanya CACHE, bukan
  artefak.** Repo yang artefaknya nol bisa tetap merah karena repo lain di akun
  yang sama yang menahannya. Tapi menghitung artefak saja sering **tidak
  menemukan penyebabnya**: `actions/cache` ikut dihitung ke penyimpanan
  Actions, dan cache Gradle untuk app Android mudah menahan puluhan kali lebih
  besar daripada seluruh artefak akun itu (11 GB cache versus ~118 MB artefak
  di akun yang sama). Dua angka ini dibaca sebelum menyentuh kode apa pun:

  ```bash
  gh api "repos/<OWNER>/<REPO>/actions/cache/usage" \
    --jq '"\(.active_caches_count) entri, \(.active_caches_size_in_bytes/1048576|floor) MB"'
  ```

  Kalau angkanya GB sementara artefaknya ratusan MB, yang perlu dibersihkan
  cache-nya — bukan kodenya, dan bukan cuma artefaknya. Resep lengkapnya di
  `references/ci-run-reading.md`; workflow pencegahnya disalin dari
  `templates/prune-caches.yml`.
- **Sebelum bilang "sudah rilis", cek dari mana app membaca pembaruan.**
  Kalau pemeriksa pembaruan membaca manifest milik sendiri (`update.json` di
  domain sendiri), menerbitkan GitHub Release tidak menyalurkan apa pun ke
  user — release itu hanya tempat menaruh berkas. Menyebut "sudah rilis"
  setelah release GitHub sementara app membaca manifest lain adalah klaim
  yang salah.
- **Naikkan versi sebelum push tag, bukan sesudah.** Tag yang menunjuk commit
  ber-`versionName` lama membangun APK yang mengaku versi lain, dan tidak ada
  job yang merah untuk itu.

## The loop

```
tulis satu lapisan koheren
  -> commit
  -> push branch
  -> pastikan run-nya ADA dan milik SHA kamu
  -> baca error dari log, bukan dari tebakan
  -> perbaiki, ulangi
```

Langkah "pastikan run-nya ADA" bukan formalitas. Workflow yang hanya memicu
pada `push: branches: [main]` akan **diam** untuk push ke branch fitur —
lalu terlihat seolah-olah CI tidak jalan sama sekali.

```bash
# 1. trigger workflow dulu sudah benar?
grep -A5 '^on:' .github/workflows/*.yml

# 2. konfirmasi run muncul, dan milik SHA kamu
sleep 8
gh run list --branch <branch> --limit 3 \
  --json databaseId,status,headSha \
  --jq '.[] | (.databaseId|tostring)+"  "+.status+"  "+(.headSha[0:7])'
```

**Selalu cocokkan run ke `headSha`.** Kalau ada run lama yang masih
`in_progress` dan run baru belum terdaftar, `gh run list --limit 1`
membaca run yang salah — dan pesan errornya milik kode yang sudah tidak
lagi ada di HEAD.

**`gh` di repo fork bisa membaca repo UPSTREAM, bukan fork-nya.** `git remote
-v` menunjukkan `origin` milik fork, tapi `gh repo view`/`gh run list` memakai
default repo yang mungkin upstream (hasil clone atau `gh repo set-default`).
Gejalanya: push sukses, `gh run list` tidak pernah menampilkan run baru, dan
workflow terlihat tidak terpicu padahal run-nya ada di fork. Cek dulu:

```bash
gh repo view --json nameWithOwner
gh run list -R <owner-fork>/<repo> --limit 3 --json databaseId,status,headSha
```

Selalu lewatkan `-R <owner>/<repo>` untuk run, release, artifact, dan download
saat repo punya remote upstream; jangan menyimpulkan "CI tidak jalan" dari
output `gh` yang menunjuk repo lain.

**Catatan hash rilis:** aset GitHub Release dibangun ulang oleh workflow, jadi
sha256-nya wajar berbeda dari artifact CI untuk commit yang sama. Jangan
menyebutnya "APK berbeda/versi lama"; yang harus dibandingkan adalah
`versionName`/`versionCode`, package, cert digest, dan isi yang diperiksa.

**Kalau tidak ada run baru sama sekali, periksa yang lokal dulu.**
`git commit` berulang tanpa `git push` terlihat persis seperti workflow yang
tidak terpicu — dan mudah disalahkan ke trigger. Satu perintah membedakannya:

```bash
git log --oneline origin/main..HEAD     # kosong = semua sudah terkirim
```

Kalau ada commit di daftar itu, penyebabnya bukan CI. Push dulu, baru tunggu
run muncul. Ini juga alasan untuk mem-push tiap checkpoint alih-alih
menumpuk commit lokal: run yang tidak pernah ada tidak memberi bukti apa pun.

### Run merah: tentukan JOB mana dulu, baru baca lognya

`gh run view --log-failed` pada run yang baru dibuat sering mengembalikan
output kosong atau potongan tidak berguna. Dua langkah yang berhasil:

```bash
# 1. job mana yang merah, dan id-nya
gh run view <RUN> --json jobs --jq '.jobs[] | "\(.name) \(.conclusion) \(.databaseId)"'

# 2. baru ambil log job itu
gh api repos/<OWNER>/<REPO>/actions/jobs/<JOB_ID>/logs | grep -nE '^e: |Lint found|error:|AssertionError' | head -30
```

Melompat langsung ke grep pada output `--log-failed` membuang satu putaran
dan sering menghasilkan "tidak ada error" yang salah — job yang merah bisa
jadi Unit test, sementara yang kamu asumsikan Lint. Di log job test,
`AssertionError` dan `FAILED` ada di tempat yang sama; merah tidak selalu
berarti compile error.

### Job merah karena langkah bantu, bukan karena kodemu

`conclusion` sebuah job adalah gabungan **semua** langkahnya. Langkah unggah
artifact yang gagal membuat job `failure` walaupun seluruh langkah compile,
test, dan assemble di atasnya `success` — lalu job build yang memakai
`needs: [lint, test]` ikut `skipped`. Yang terlihat: "CI merah, build tidak
jalan". Yang sebenarnya: kodemu lolos, hanya artefaknya yang tidak bisa
diunggah.

Bedakan di tingkat **langkah**, bukan tingkat job:

```bash
gh run view <RUN> --json jobs \
  --jq '.jobs[] | .name, (.steps[]? | "  " + (.conclusion//"?") + "  " + .name)'
```

Yang membuktikan kodenya baik-baik saja adalah `BUILD SUCCESSFUL` di log job
itu, beserta task yang benar-benar dieksekusi:

```bash
gh run view --job <JOB_ID> --log 2>&1 \
  | grep -E ':app:compile|assembleDebug|assembleRelease|testDebugUnitTest|BUILD SUCCESSFUL'
```

Jangan mengubah kode selagi semua yang merah adalah langkah unggah. Kalau
memang diubah, kamu "memperbaiki" kode yang sudah benar sementara penyebab
sebenarnya masih di tempatnya — dan run berikutnya merah dengan pesan yang
sama.

**Dua sebab langkah unggah tetap gagal walau build hijau**, dan keduanya tidak
ada hubungannya dengan kode: kuota artifact akun penuh, atau **pola path-nya
salah**. Yang kedua khas proyek dengan lebih dari satu dimensi flavor — nama
flavor digabung jadi satu direktori (`apk/universalFoss/debug/`), bukan
`apk/foss/debug/`. Pola yang salah membuat langkah verifikasi mencari berkas di
direktori yang tidak pernah ada, jadi jangan menebaknya: cetak isi direktori
itu dari runner, lalu beri langkah verifikasi jalan keluar yang mencetak isinya
supaya run berikutnya menjelaskan dirinya sendiri, bukan cuma berbeda
"No such file or directory".

```bash
APK=$(ls app/build/outputs/apk/<flavor-gabungan>/release/*.apk 2>/dev/null | head -1)
[ -n "$APK" ] || { echo "::error::APK tidak ada di outputs/apk; isinya:"; \
  find app/build/outputs/apk -name '*.apk'; exit 1; }
```

Resep mengenali dan mencegahnya (kuota artifact, `retention-days`,
`continue-on-error`) ada di `references/ci-run-reading.md`.

## Jebakan git push yang tidak memberi error

`git push origin <branch>` yang salah tidak gagal diam-diam:

```bash
# sedang di feat/widget, tapi kamu menulis:
git push origin main
# -> "Everything up-to-date"   <- bukan error, tidak ada yang dipush
```

Perintah itu mendorong ref `main` **lokal**, yang tidak punya commit baru.
Selalu: `git push origin <branch>` dengan nama branch eksplisit, atau
`git push origin HEAD:<tujuan>`.

### `Everything up-to-date` juga muncul saat commit-nya tidak pernah jadi

Pesan yang sama keluar kalau `git commit` tidak menghasilkan commit sama
sekali — mis. pesan multi-baris yang dikirim lewat heredoc di dalam string
yang di-interpolasi: shell menerima teksnya, commit tidak jadi, dan
`git push` melaporkan "Everything up-to-date" yang terbaca seperti "sudah
beres".

Untuk pesan commit multi-baris: tulis ke berkas dulu, lalu `-F`.

```bash
python3 - <<'PY'
open('/tmp/cimsg.txt', 'w').write("""judul singkat

kenapa, bukan apa
""")
PY
git add -A && git commit -F /tmp/cimsg.txt
```

Dan verifikasi commit-nya benar-benar ada — jangan percaya output push:

```bash
git log --oneline -1      # SHA baru? kalau masih SHA lama, commit gagal
git status --porcelain    # masih ada " M ..."? berarti belum ter-commit
```

## Jangan polling CI di dalam loop

`execute_code` punya batas keras (~300 detik). Loop `while: sleep 30` di
dalamnya mati di tengah tunggu, kernel hilang, dan state-nya ikut hilang
bersama.

Dua cara yang benar:

```
# foreground dengan notifikasi
terminal(background=True, notify=True, command="gh run watch <ID> --exit-status")

# atau: satu panggilan foreground di bawah batas
gh run watch <ID> --exit-status --interval 30
```

Kalau konteks sedang penuh, lakukan pekerjaan lain saat menunggu — bukan
memanggil `wait` berulang.

### Hitung dulu: iterasi x sleep harus di bawah batas

`seq 1 70; sleep 45` = 52 menit. Foreground akan timeout di 400-600 detik,
selalu. Hitung perkiraannya sebelum menulis loop, dan potong ke rentang yang
benar-benar muat: 40 x 40 = 26 menit juga tidak muat, 15 x 40 = 10 menit
masih tidak. Yang muat: ~8 iterasi x 40 detik. Untuk menunggu lebih lama,
`background=True` + `notify=True`, bukan foreground yang diperpanjang.

### Notifikasi watcher = pemicu cek ulang, bukan kabar baru

Poller di background memberi tahu saat prosesnya **keluar**, yang bisa jauh
setelah kamu sudah melaporkan hasil run itu. lebih buruk: watcher untuk run lama
menyala setelah run yang lebih baru sudah selesai. Saat notifikasi masuk,
`gh run view <ID>` dulu sebelum menulis laporan — kalau hasilnya sudah kamu
laporkan, jawabannya satu baris "notifikasi basi" plus status run yang
sekarang, bukan laporan ulang.

### Jangan menggabungkan status dua run ke satu string

Pola `s="$a$b"` lalu `case "$s" in completed*in_progress*)` rapuh: itu hanya
break kalau **pasangan** status cocok salah satu literal. Dua run berubah
pada waktunya masing-masing, jadi salah satu kombinasi sering tidak pernah
terjadi — loop keluar lebih awal atau tidak sama sekali. Kalau memang harus
memantau dua run, cek satu per satu dalam iterasi yang sama.

### `cd` gagal = perintahnya tidak jalan sama sekali

`cd: /tmp/...: No such file or directory` dengan exit 126 membuat seluruh
perintah berikutnya batal, dan output kosongnya terbaca sebagai "tidak ada
yang ditemukan". Loloskan `workdir` atau path absolut, dan perlakukan
exit != 0 pada langkah pertama sebagai "belum ada data", bukan sebagai
hasil negatif.

## Rilis: verifikasi isi APK, bukan cuma checksum

`scripts/release.sh` sudah memverifikasi SHA-256 APK publik sama dengan
lokal, `update.json` bisa dibaca, dan tag menunjuk commit yang mendeklarasikan
versionName yang benar. Itu membuktikan **keutuhan transfer**, bukan isi.

### Laporan skrip bukan bukti — ambil sendiri dari jaringan

Skrip menulis "OK" untuk checksum dan halaman karena ia membandingkan berkas
lokal dengan hasil unggahannya sendiri. Sesudah skrip selesai, verifikasi
terpisah dari luar:

```bash
curl -fsS https://<domain>/update.json        # versionCode/versionName baru?
curl -fsS -o /tmp/publik.apk -w 'http=%{http_code} bytes=%{size_download}\n' \
  https://<domain>/<nama-apk>
sha256sum /tmp/publik.apk <apk-lokal>          # dua hash harus identik
curl -fsS https://<domain>/ | grep -oE '<versi-baru>|<tanggal-id>'
```

### Gerbang sebelum menerbitkan: package sama, sertifikat sama

Dua nilai yang menentukan update bisa menimpa versi terpasang tanpa uninstall —
dan keduanya tidak dilihat oleh checksum mana pun:

```bash
aapt dump badging <apk> | grep -E '^package:|application-debuggable'
apksigner verify --print-certs <apk> | grep 'SHA-256 digest'
```

Bandingkan APK baru dengan APK yang **sedang tayang**, bukan dengan berkas lain
di repo. `package` berbeda = Android menganggapnya aplikasi lain; digest
sertifikat berbeda = update ditolak dan user harus uninstall (database, cache,
playlist ikut hilang). Yang boleh berubah hanya `versionCode`/`versionName`.

Kalau repo memakai `applicationIdSuffix` di buildType **release** dengan alasan
yang didokumentasikan di `build.gradle.kts` (supaya rilis bisa menimpa versi
debug yang sudah terpasang di perangkat user), package berakhiran `.debug` itu
**memang** yang benar. Baca file itu sebelum "memperbaikinya".

### `git rev-parse v<versi>` pada tag anotasi bukan commit

Tag dari `git tag -a` punya objek tag sendiri, jadi `git rev-parse v0.41.0`
mengembalikan SHA objek tag. Saat membuktikan tag menunjuk commit mana, pakai
dereference-nya:

```bash
git rev-parse v<versi>^{}     # commit yang ditunjuk
git cat-file -t v<versi>      # "tag" = anotasi, "commit" = lightweight
```

Satu cek lagi yang murah sebelum menyatakan rilis selesai: APK itu zip, jadi
`assets/changelog.json` di dalamnya bisa dibaca langsung dan dibandingkan
dengan `versionName` di `build.gradle.kts`. Kalau entri teratasnya versi
lain, yang tayang bukan rilis yang dimaksud — dan tidak ada job yang merah
yang akan memperingatkanmu.

Assertion jumlah di changelog juga worth dicek: `publishedAt` harus tanggal
yang benar-benar terjadi (bukan tanggal Server yang bisa satu hari beda
karena zona waktu), dan urutan entri harus menurun.

### Cek sertifikat tanda tangan SEBELUM rilis hotfix

Satu cek yang murah, dan kalau gagal berarti hotfix you've done is worth
nothing to the user: ** bandingkan sidik jari sertifikat signing APK baru
dengan APK yang sedang tayang.** Hotfix dengan `versionCode` naik tapi kunci
berbeda tidak akan ter-install di atas app lama — Android menolak, dan user
dipaksa uninstall, kehilangan database, cache, dan playlist.

```bash
apksigner verify --print-certs <apk-lama-tayang>
apksigner verify --print-certs <apk-baru-dari-ci>
# bandingkan SHA-256 certificate digest: harus identik
```

Membandingkan bytes atau ukuran APK tidak membuktikan apa pun soal ini —
APK dari build berbeda hampir selalu berbeda byte, dan itu normal.

`apksigner` cek dulu; kalau memang tidak ada di mesin itu, jadikan signing
check sebagai job CI yang wajib hijau sebelum deploy, bukan langkah manual
yang sering terlewat. Kesalahan yang lebih halus: hotfix yang **tidak
menaikkan `versionCode`**.
Deploy ulang APK dengan versi sama menghasilkan file publik yang
berganti isi tanpa nomor versi yang berubah — user yang sudah pernah mengunduh
tidak pernah melihat perubahan, dan app yang sudah terpasang tidak pernah
memperbarui.

### Jalankan ulang untuk memperbaiki halaman saja, tanpa naikkan versi

`release.sh` tidak selalu berarti rilis baru. Kalau hanya template halaman
unduh yang berubah — tombol, gaya, hitungan — jalankan ulang skripnya dengan
APK yang **sama persis** dari CI sebelumnya:

```bash
gh run download <RUN_ID_LAMA> -n <artifact-apk> -D /tmp/dir-baru
./scripts/release.sh /tmp/dir-baru/app-release.apk "<catatan sama persis>"
```

Skrip akan menulis ulang `index.html` dari template baru, dan karena
`versionCode`/`versionName` tidak berubah, skrip itu tidak menerbitkan
rilis kedua. Bagian tag otomatis dilewati (`sudah ada — dilewati`), jadi
tidak ada tag yang berubah arah.

Dua hal yang wajib dijaga supaya ini tidak merusak rilis yang sedang tayang:

- **APK harus dari run yang sama.** Mengambil APK dari build lain dengan
  nomor versi sama akan menimpa aset publik dengan isi berbeda, sedangkan
  verifikasi checksum di akhir skrip tetap hijau karena yang dibandingkan
  adalah berkas lokal dengan berkas publik hasil unggahan itu sendiri.
- **`update.json` ditulis ulang.** Isinya catatan, `publishedAt`, dan
  `sha256`; verify lagi bahwa tanggal dan nomor versinya masih cocok dengan
  entri `changelog.json`.

### Urutan output harus datang dari manifest, bukan `sorted(glob())`

Segera setelah reorder pertama, carousel-nya tetap keluar dalam urutan
huruf. Akar masalahnya bukan logikanya — logikanya sudah benar. **Data-nya
yang salah**: file yang berisi urutan+capan sudah ditulis dalam abjad.
Pelajaran yang lebih besar bukan soal abjadnya, tapi diagnosenya:

> Kalau urutan yang dihasilkan benar dan urutannya tetap salah, jangan
> patch ulang logikanya — periksa isi sumbernya.

Urutan `sorted(glob('*.webp'))` menaruh "Now Playing" di belakang "library"
karena 'n' > 'l'. Urutan itu hanya benar untuk asset yang tidak punya urutan
dipilih manusia. Begitu **urutan bermakna** (alur pemakaian, urutan slide,
prioritas), beritahu generator dari mana. Satu file yang berfungsi ganda —
`namafile<tab>caption` per baris — adalah sumber yang cukup untuk urutan dan
teks, dan menghindari dua daftar yang harus selalu sinkron.

Perhatikan juga `continue` di dalam loop penghasil: kondisi yang dibalik
(`if nama and not (folder / nama).exists(): continue`) membuang file yang
**ada**, bukan yang hilang — deploy lolos, filenya hilang). Tulis logikanya
sebagai kondisi **mau dipakai**: `if nama and not ada: continue` →
`if nama and ada: pakai`. Frasa "skip yang tidak ada" jauh lebih sulit dibaca
terbalik daripada "pakai yang ada".

Sebelum swap `sorted(glob(...))` ke sumber manifest, jalankan generator pada
data contoh dan **cetak urutan hasilnya** — Bug yang hanya terlihat setelah
deploy ke halaman publik bisa dicegah dengan satu baris print.

## Handoff APK ke user: setiap build harus bisa dibedakan

Selama fitur masih diiterasi, user memasang APK berkali-kali. Tanpa identitas,
semua build terlihat sama dan satu putaran kerja dibuang untuk mendebat berkas,
bukan bug.

- **Naikkan `versionCode`/`versionName` di commit yang mengirim perubahan itu,**
  bukan hanya saat rilis. Nama berkasnya juga memuat versi (`App-0.4.0.apk`),
  bukan nama artifact CI (`app-universal-foss-release.apk`).
- **Ukuran byte yang sama bukan bukti isinya sama.** `0.2.0` → `0.3.0` dan
  versionCode `2` → `3` tidak mengubah satu pun panjang string/integer, jadi dua
  build berbeda isi bisa mendarat di jumlah byte identik. User yang membandingkan
  berkas di chat melihat "APK yang sama" — dan itu kesimpulan yang benar dari
  satu-satunya bukti yang dia punya. Sertakan `aapt dump badging <apk> | head -1`
  dan `sha256sum` di laporan supaya bedanya bisa dibaca tanpa memasang.
- **Satu-satunya yang bisa dibaca user setelah memasang adalah versi di layar
  Settings/Profile.** Sebut di mana membacanya, jangan cuma "ini build terbaru".
- **Kalau user bilang "gada yang berubah", verifikasi versi terpasang dulu —
  jangan patch ulang kode.** Menambal bug yang di `main` sudah benar membakar
  satu putaran penuh dan terbaca sebagai tidak becus. Penyebab yang jauh lebih
  sering: install tidak masuk — signature berubah setelah rebrand, Play Protect
  memblokir sideload diam-diam, atau user membuka unduhan lama dari riwayat chat.
  Perbaikannya uninstall lalu reinstall, bukan commit baru.

## Bukti test: centang hijau bukan bukti

Compile + lint + test hijau tidak berarti ada test yang dieksekusi.
Unduh laporan, parse jumlahnya, bandingkan dengan rilis sebelumnya — selisihnya
yang membuktikan test baru benar-benar jalan.

```bash
gh run download <RUN_ID> -n <artifact-name> -D /tmp/rep
grep -oE '<div class="counter">[^<]+' /tmp/rep/**/index.html | head
```

Catatan: `gh run download` **tidak punya flag `-A`**. Dengan run-id, `-n`
saja sudah cukup; `-A` muncul di help lalu menggagalkan seluruh perintah.

### Test yang ditulis SETELAH push tidak ada di run yang hijau

Jebakan urutan yang tidak terlihat di laporan mana pun: kamu push feature, CI
hijau, lalu sambil menulis test untuk menutup celah, baru push lagi. Run hijau
pertama **tidak pernah menjalankan test itu** — jumlah test yang dibaca dari
laporan adalah angka dari SEBELUM test baru ada, jadi selisihnya nol dan
terlihat seperti "test saya sudah tercakup".

Tandanya: kamu baru sadar file test belum ikut commit **setelah** menyebut
jumlah test sebagai bukti. Aturannya sederhana — tulis test-nya sebelum commit
yang memuat fiturnya, bukan sesudah. Kalau memang terlanjur, sebutkan bahwa
run hijau itu tidak mencakup test baru, dan jangan melaporkan jumlahnya seolah
sudah terbukti.

Dua kalimat ini harus terpisah dan keduanya jujur: "run hijau ini tidak
menjalankan test yang baru ditulis" (belum terbukti) dan "test yang ditulis
belakangan itu sendiri bisa salah" (bisa saja merusak run berikutnya yang
tadinya hijau). Test yang mengunci indeks adalah contoh yang mudah salah —
ia menguji asumsi tentang perilaku, bukan bentuk kode.

## Test yang mengunci interpretasi parameter, bukan perilakunya

Fungsi dengan parameter opsional punya dua interpretasi yang sama-sama mungkin
dibaca orang, dan hanya satu yang benar:

| Tafsiran | Arti `count` | Test yang mengunci |
|---|---|---|
| jumlah tepat | selalu mengembalikan 2 baris | rapuh — merah begitu parameternya diubah |
| batas atas | mengembalikan sampai 2 baris | tahan — tetap benar saat data bertambah |

Tanda tafsiran salah ada di assertion-nya: `assertEquals(2, f(x, count = 10).size)`
pada data yang cuma punya 3 baris. Kalau kodenya mengembalikan 3, yang
pertanyaannya bukan "kodenya salah" tapi "**apa arti parameter ini**".

Bedakan dalam satu putaran: baca KDoc parameternya. Kalau KDoc bilang "berapa
banyak baris", itu jumlah tepat; kalau bilang "batas atas" atau default-nya
berarti "sampai", itu batas atas. Nama dan KDoc yang tidak satu arah berarti
KDoc-nya yang salah — bukan implementasi.

Yang tidak boleh terjadi: "memperbaiki" implementasi supaya merah test hilang
padahal semantik parameter memang berbeda. Itu menukar bug test dengan bug
kode dan menambah satu run lagi. Tentukan dulu artinya, baru putuskan sisi
mana yang salah.

Saat sudah yakin tesnya yang salah, tulis **alasan di komentar test** — satu
kalimat yang menyebut kenapa bentuk itu yang benar. Kalau alasan itu sendiri
salah, run berikutnya hijau untuk alasan yang salah lagi.

## Assertion jumlah itu bom waktu: assert invarian, bukan hitungan

Test yang membandingkan **jumlah** elemen resource akan redden begitu fitur
legit menambah satu elemen lagi. Contoh nyata: `FileProviderPathsTest` punya
`assertEquals(1, doc.getElementsByTagName("cache-path").length)`, lalu fitur
kartu share menambah `<cache-path name="share_cards" path="share/"/>`. Dua
`cache-path` itu **benar dan memang dibutuhkan** — assertion-nya yang salah,
karena yang dijaga sebenarnya adalah "tidak ada provider yang keluar dari
`cacheDir`", bukan "berapa banyak yang terdaftar".

| Rapuh (hilang begitu fiturnya bertambah) | Tahan (tetap benar saat bertambah) |
|---|---|
| `assertEquals(1, node.length)` | `assertTrue(node.length > 0)` |
| "hanya satu prefix yang boleh" | "semua prefix wajib di dalam dir yang diizinkan" |
| "jumlah tabnya empat" | "setiap tab yang didaftarkan ada di kodenya" |

Aturan: kalau angka itu menghitung hal yang **memang sengaja bertambah**,
tulis assertion-nya sebagai batas — minimal satu, tidak keluar dari
`cacheDir` — bukan sebagai syarat jumlah. Invariant yang membuat
`Failed to find configured root` dan `StringIndexOutOfBoundsException` itu
yang harus dicegah, bukan cardinality.

Bonus: assertion per-tag menghasilkan pesan gagal yang jauh lebih berguna.
"Tepat satu `<cache-path>`" menyuruh pembaca mencari sendiri mana yang salah;
loop yang menyebut nilai `path`-nya langsung menunjuk culprit-nya.

Setelah mengganti assertion, cek test lain di file yang sama — helper yang
mengembalikan `List<String>` dari semua elemen tetap aman, helper yang
mengambil `item(0)` tidak.

## Dua jebakan `gh run download` yang tidak ada di help-nya

1. **Direktori tujuan harus baru.** Download kedua ke direktori yang sama gagal
   dengan pesan yang tidak menyebut download sama sekali:
   `error extracting zip archive: ... open /tmp/x/app-release.apk: file exists`.
   Gunakan `rm -rf <dir>` atau direktori baru per artifact.
2. **Laporan Gradle yang ter-upload HTML saja.** `TEST-*.xml` tidak ikut, jadi
   `glob('**/TEST-*.xml')` mengembalikan nol suite padahal ratusan test jalan
   — dan nol suite itu baca sebagai "tidak ada test", bukan "format berbeda".

   3. **Nama artifact bukan nama rilisnya, dan menebak itu membuang satu
   putaran.** Download `-n release-apk` gagal padahal APK-nya ada, karena
   artifact-nya bernama `player-release-apk`. Ambil nama aslinya dari
   daftar, jangan dari ingat-ingat:

   ```bash
   gh api repos/<OWNER>/<REPO>/actions/runs/<RUN>/artifacts \
     --jq '.artifacts[] | "\\(.name)  \\(.size_in_bytes) bytes"'
   ```

   Nama yang benar ada di `name:` pada step upload-artifact di workflow,
   sering berawalan nama app atau prefix environment.

   Sumber angka yang benar ada di `index.html` dan di direktori `classes/`:

```bash
gh run download <RUN_ID> -n <artifact-name> -D /tmp/rep-fresh
grep -oE '<div class="counter">[^<]+' /tmp/rep-fresh/**/index.html | head -4
ls /tmp/rep-fresh/**/classes/ | wc -l                    # jumlah kelas test
ls /tmp/rep-fresh/**/classes/ | grep -iE '<KelasBaru>'  # bukti test baru jalan
```

Empat counter di `index.html` adalah tests, failures, ignored, duration. Dua
yang pertama yang dilaporkan.

## File yang di-generate tapi BUKAN output task: hilang saat cache hit

Kelas jebakan yang paling mahal, karena ia muncul di commit yang **tidak
menyentuh apa pun yang relevan** — commit docs, README, atau web. Semua test
hijau di run rilis, lalu merah di run berikutnya tanpa satu baris kode yang berubah.

Mekanismenya: Gradle memulihkan `FROM-CACHE` **output task** sebuah task. Berkas
yang ditulis processor ke dalam source tree bukan output task, jadi tidak ikut
dipulihkan. Test yang membacanya dari working tree langsung gagal.

Kasus nyata: Room menulis `app/schemas/<DbClass>/<version>.json` saat KSP jalan,
tetapi `schemas/` bukan output `kspDebugKotlin`. Run rilis hijau (entitas Room
berubah → cache miss → KSP jalan → file tertulis). Commit README berikutnya
cache-hit → file tidak ada → `Migration7To8Test` 4 test gagal di
`assertTrue(file.exists())`, sementara tidak ada satu pun perubahan Room.

### Diagnosis: `FROM-CACHE` di log, bukan di git

```bash
gh api "repos/<O>/<R>/actions/jobs/$JOB/logs" | grep -i 'FROM-CACHE'
gh run list --limit 5 --json databaseId,conclusion,createdAt  # run hijau jauh lebih LAMBAT = cache miss
```

Run hijau yang butuh ~15 menit dan run merah yang selesai dalam ~2 menit adalah
tanda yang sama: merah itu cache hit. Runs yang kompilasi penuh lambat; yang
memakai cache selesai instan.

### Bedakan dari gitignore dan urutan commit

Sebelum menyimpulkan, dua cek murah yang sering salah menyalahkan:

```bash
git check-ignore -v <path-yang-hilang>   # exit!=0 = TIDAK di-ignore
git log --all --oneline -- '<path>*<n>.json'   # kosong = belum pernah ada di git
```

Kalau bukan gitignore dan memang belum pernah ter-commit, itu bug cache — bukan
urutan commit dan bukan aturan ignore yang salah.

### Fix permanen: commit filenya

File yang di-generate tapi dibaca test **wajib masuk version control**. Assert
yang bergantung pada side-effect cache akan merah lagi di run berikutnya kalau
filenya tidak ada.

Sebelum commit, verifikasi isinya benar-benar memenuhi assert yang ada — jangan
asal ambil karena test sudah hijau. Untuk skema Room, bandingkan versi baru dengan
sebelumnya: tabel yang bertambah atau berkurang, `createSql` tiap tabel lama harus
identik, daftar `indices` harus sama. Kalau ada yang berubah diam-diam, artefaknya
bukan hasil Room yang benar.

### Pemulihan saat file belum ada di repo

Jangan build lokal (dilarang). Ambil dari CI sebagai artifact, dan **pasang step
upload-nya dengan `if: always()`** supaya artefaknya tetap ada walau job-nya
merah:

```yaml
      - name: Upload Room schema
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: room-schema
          path: app/schemas/**/*.json
```

`gh run download <RUN> -n room-schema -D <dir-baru>` lalu. Jalur ini berguna
tidak hanya untuk Room: apa pun yang di-generate KSP/annotation-processor dan
dibaca test punya masalah yang sama.

### Flag generator: cek versi sebelum menyentuh

Percobaan "matikan incremental" (`room.incremental=false`) terdengar masuk akal
dan justru membuat `kspReleaseKotlin` gagal compile — flag itu deprecated di
Room 2.6.x dan nilainya ditolak. Kalau sebuah flag generator dicurigai, **cek
versi generator yang terpasang dulu** (`grep room gradle/libs.versions.toml`)
sebelum mengubah build file; flag usang lebih sering menolak build daripada
memperbaikinya. Revert begitu CI melaporkan compile error, jangan menahan
perubahan yang belum terbukti.

## Buktikan isi APK: cek dulu alatnya, jangan Assume

`aapt`, `aapt2`, dan `apksigner` **ada di `/usr/bin`** di VPS Meow Labs. Cek
`command -v` sebelum menyimpulkan tidak ada — jangan hanya melihat
`build-tools/` di `$ANDROID_HOME` lalu menyerah, karena binary-nya bisa saja
di PATH sistem.

Dengan `aapt`, manifest dan nomor versi bisa dibaca langsung:

```bash
aapt dump badging <apk> | grep -E "^package:|sdkVersion:|targetSdkVersion:"
apksigner verify --print-certs <apk> | grep 'SHA-256 digest'
```

Bandingkan **APK baru dari CI dengan APK yang sedang tayang**: `versionCode`
harus naik dan cert digest harus identik. Certificate digest yang berubah
berarti user dipaksa uninstall — kehilangan database dan playlist — dan
tidak ada job merah yang memperingatkanmu.

Kalau `aapt` ternyata tidak ada di mesin lain, jalur zip tetap berlaku: APK itu
zip, dan berkas yang kamu pedulikan bisa dibaca langsung.
Untuk membuktikan `assets/changelog.json` yang ikut APK sesuai
`BuildConfig.VERSION_NAME` — yaitu bahwa yang benar-benar terpasang ke HP user
adalah versi yang kamu kira:

```bash
python3 - <<'PY'
import zipfile, json
apk = '<path-app-release.apk>'
z = zipfile.ZipFile(apk)
name = [n for n in z.namelist() if n.endswith('assets/changelog.json')][0]
top = json.loads(z.read(name).decode('utf-8'))[0]
print('changelog top:', top['versionName'], top['publishedAt'])
PY
```

Bandingkan hasilnya dengan `versionName` di `build.gradle.kts`. Kalau
berbeda, yang dipublikasikan bukan versi yang kamu kira — dan itu baru
ketahuan setelah APK terpasang di HP user.

### Perubahan warna/konstanta: pindai `classes.dex`, bukan cuma manifest

Warna tema, konstanta, dan string yang di-inline compiler tidak muncul di
manifest maupun asset, jadi `aapt` dan `changelog.json` tidak bisa
membuktikan build itu memuat perubahan terbaru. Nilai ARGB tersimpan sebagai
int little-endian di dex:

```python
import zipfile, struct
z = zipfile.ZipFile('<apk>')
for name in z.namelist():
    if name.startswith('classes') and name.endswith('.dex'):
        b = z.read(name)
        print(name, b.count(struct.pack('<I', 0xFFE8F3FE)))
```

Hasil `> 0` membuktikan konstanta baru benar-benar ikut dikompilasi — bukan
artifact lawas yang namanya kebetulan sama. Ini bukti **isi**, bukan bukti
tampilan: konstanta bisa ada di dex tapi tidak terpakai di layar, jadi
screenshot perangkat tetap oracle terakhir.

`AndroidManifest.xml` di dalam APK itu biner AXML, tidak bisa dibaca
`ElementTree`. Untuk permission dan versi dari manifest, andalkan job
`Verify APK` di CI atau `apkanalyzer` — jangan menebak dari bytes.

## Kelas compile error yang berulang di Android

| Gejala dari CI | Penyebab | Perbaikan |
|---|---|---|
| `Unresolved reference 'AndroidEntryPoint'` | Anotasi dipakai tanpa import | **Tanyakan dulu apakah anotasi itu perlu.** Kalau kelasnya tidak punya `@Inject`, Hilt tidak punya apa-apa untuk disuntikkan — hapus anotasinya, jangan tambahkan import |
| `'onDestroy' overrides nothing` | Method itu milik `Service`, bukan `BroadcastReceiver`/`AppWidgetProvider` | Cek body-nya: kalau identik dengan hook di sebelahnya (`onDisabled`), hapus yang kembar |
| `Smart cast to 'String' is impossible, because 'x' is a delegated property` | Smart cast tidak berlaku ke property | Hoist ke `val` lokal: `val aksi = intent.action ?: return` |
| `actual type is 'String?' but 'String' was expected` | Property nullable diteruskan ke fungsi non-null, walau `when` sudah menjamin | Hoist nullable sekali di awal, lalu pakai `val` itu di semua cabang |
| `suspend fun Mutex.withLock` dipanggil dari fungsi non-suspend | Pengaman dipindah ke jalur yang dipanggil listener / callback sinkron | Jangan paksa jadi `suspend`. Jadikan pemeriksa awal **tanpa lock** sebagai pre-filter, dan biarkan versi yang terkunci yang memutuskan. Aman selama versi terkunci mengulang cek itu sendiri |
| `'when' must be exhaustive` + `Unresolved reference 'Gagal'` | Dua sealed interface dengan nama sama di satu file | Kualifikasi: `is HasilUrlAuth.Gagal`, bukan `is Gagal` |
| `'return' is prohibited here` | `return` telanjang di dalam lambda — Kotlin membacanya sebagai non-local return dari fungsi luar | Tanyakan dulu apakah keluar dari lambda memang perlu. Kalau cabangnya memang tidak melakukan apa-apa (mis. "tidak ada tombol untuk dipicu"), `Unit` sudah setara dan kodenya lebih jujur tanpa label |
| `Unresolved reference 'namaFungsi'` muncul bersamaan dengan error lain di file yang sama | Efek cascade dari error pertama, bukan masalah sendiri | Perbaiki error yang disebut lebih dulu, lalu baca ulang baris tersebut. Jangan memperbaikinya sebagai referensi tak dikenal |
| `Unresolved reference 'namaFungsi'` **sendirian**, dan deklarasinya jelas ada di file yang sama | Deklarasi dan pemanggil berbeda nama nyaris identik — beda satu huruf (`kendelkan` vs `kendalikan`) | Bandingkan byte kedua nama, bukan tampilan teksnya. Rujukan yang gagal hampir selalu punya nama yang **mirip** di file itu: cari yang bedanya satu karakter, termasuk huruf yang tertukar (`i`/`l`/`k`) |
| `Unresolved reference 'index'` di kode yang menulis `index.index` | Destructure `IndexedValue`/`Map.Entry` sudah menghasilkan key sebagai `Int`; `index` bukan objek yang punya `.index` | Pakai `index` langsung. Kalau memang butuh posisi, `.index` ada di `mapIndexed`/`.withIndex()`, **bukan** di hasil destructure |
| `None of the following candidates can be called...` untuk method yang jelas ada di file itu | Method-nya dideklarasikan di **parent atau interface**, bukan di kelas yang dipanggil | Lihat tempat deklarasi sebenarnya. Helper turunan `Available` yang dipakai di `Available` tidak terlihat karena compiler hanya melihat kontrak interface-nya. Pindahkan ke kelas yang benar, jangan tambahkan stub kompatibilitas |
| Error yang sama muncul lagi padahal deklarasinya sudah terbukti ada | Salah baca yang konsisten di beberapa alat, bukan isi file | Lihat "Ketika alat baca tidak sepakat dengan compiler" — turun ke byte, dan ambil file yang benar-benar di-build CI |

## Cek versi library sebelum menulis accessor-nya

`Unresolved reference 'boolean'` pada `jsonPrimitive.boolean` gagal compile
padahal nama itu **ada** di dokumentasi kotlinx-serialization — versi yang
terpasang di repo tidak punya accessor itu. Tiga API bergantian nama atau
berpindah tempat antar rilis, dan ketiganya dibaca dari hafalan.

Cek versi dulu, lalu pakai accessor yang **file itu sendiri sudah pakai**:

```bash
grep -nE 'serialization|room|compose' gradle/libs.versions.toml
grep -rn '\.jsonPrimitive\.' --include=*.kt app/src/test   # preseden yang sudah lolos
```

Kalau nama accessor meragukan, pilih bentuk yang sudah terbukti jalan di file
atau repo yang sama — `jsonPrimitive.content` daripada accessor baru yang
membutuhkan import tambahan. Sedikit lebih banyak kode, tapi tidak menolak build.

Perhatikan bentuk data saat memilih string untuk dibandingkan. Room menulis
boolean sebagai JSON boolean, jadi accessor `content` mengembalikannya sebagai
**string** `"false"` — bukan boolean, dan bukan `"null"` (yang berarti kuncinya
tidak ada). Assertion yang membandingkan ke bentuk yang salah akan gagal terus
meski skema sudah benar, dan gejalanya identik dengan "implementasi memang salah".

## Verifikasi signature API dari sumbernya, sebelum menulis

Di repo yang Gradle-nya dilarang, sebagian besar `Unresolved reference` bisa
dibunuh tanpa satu pun run CI: unduh `-sources.jar` dari `maven.google.com`,
baca signature sebenarnya, dan cek keberadaan nama ikon. Yang wajib dibaca dari
hasil itu: nama parameter, default-nya, dan anotasi opt-in
(`@ExperimentalMaterial3Api` dan sejenisnya).

Resep lengkapnya (URL Maven, cara membaca signature, pembagian
core-vs-extended untuk ikon, dan ikon arah yang deprecated) ada di
`references/api-signature-verification.md`.

**Batcher jadi satu panggilan.** Unduh, unzip, cetak signature, dan cek ikon
semuanya dalam satu `execute_code`. Verifikasi satu artefak per tool call
membakar iterasi yang seharusnya dipakai untuk menulis kodenya — dan batas
iterasi adalah runway yang habis sebelum commit, bukan sesudah.

## Assertion tentang skema Room: jangan menebak bentuk JSON

Test skema gagal dengan `AssertionError` padahal artefaknya benar. Dua sebab
yang keduanya berakar dari mengira bentuk JSON:

- **Room menulis boolean, bukan string.** `notNull` muncul sebagai boolean
  `false`; membandingkannya ke string `"null"` selalu gagal.
- **`createSql` diakhiri constraint, bukan kolom.** Ujung string adalah
  `PRIMARY KEY(...)`, jadi assertion "kolom terakhir" dari ujung string tidak akan
  pernah benar — `trimEnd(')')` hanya membuang satu karakter.

Kolom terakhir harus dibaca dari daftar `fields`, dan nilai boolean dari
representasi sebenarnya di file. Sebelum push ulang, replikasi seluruh assert
terhadap JSON yang sama di luar Gradle:

```python
import json
d = '<direktori-skema>'
e = {x['tableName']: x for x in json.load(open(f'{d}/9.json'))['database']['entities']}
cols = [f['columnName'] for f in e['songs']['fields']]
print('terakhir:', cols[-1])
print('notNull:', [f for f in e['songs']['fields'] if f['columnName'] == cols[-1]][0].get('notNull'))
```

Replikasi lokal ini bukan bukti compile, tapi ia membedakan "test yang salah"
dari "implementasi yang salah" dalam satu putaran — bukan tiga.

## Menyetakkan string itu unik, bukan cuma cocok di satu tempat

Menyisipkan blok dengan jangkar `assert s.count(blok) == 1` sebelum
`str.replace` terlihat sederhana, tapi jangkar itu hanya benar kalau string itu
benar-benar unik di file. Kalau ada beberapa call site, file lain yang punya
blok serupa, atau pemanggilan yang di dalam fungsi berbeda, syaratnya bisa
lolos **di tempat yang salah** — dan kode mendarat di composable yang tidak
punya variabel yang dirujuk.

Setelah menyisipkan, buktikan pemiliknya, bukan cuma jumlah hitungannya:

```python
lines = open(p, encoding='utf-8').read().split('\n')
for i, l in enumerate(lines):
    if 'namaBlokYangDisisipkan' in l:
        owner = next(lines[j].strip() for j in range(i, -1, -1)
                     if lines[j].strip().startswith(('fun ', 'private fun ')))
        print(i + 1, owner)
```

Untuk perubahan state yang dideklarasikan di satu composable tapi dipakai di
tab lain, cek mana yang **memanggil** mana. Tab menerima parameter sendiri;
menyimpan state di layar induk tidak otomatis meneruskannya ke tab.

## Jangan menebak syntax, terutama di baris yang sudah disebut CI

Kegagalan yang mahal: CI sudah melaporkan `file:117:59 'return' is
prohibited here`, lalu dua fix berturut-turut menebak nama label
(`return@namaFungsi`, lalu `return@namaParameter`) dan keduanya ditolak
dengan pesan yang sama. Dua run CI terbuang untuk satu baris.

Aturannya:

1. **Baca baris itu dan seluruh bloknya** sebelum menulis fix. Sebagian
   besar "salah label" sebenarnya "kode itu memang tidak butuh keluar".
2. **Label `return@x` hanya menunjuk lambda literal yang ditulis inline.**
   Nama fungsi dan nama parameter fungsi bukan label yang sah.
3. **Periksa cek yang murah sebelum push ulang.** Untuk Kotlin, `kotlinc`
   standalone di `/tmp` pada ekspresi yang pendek diperbolehkan di repo
   yang melarang Gradle — baca `AGENTS.md` repo untuk konfirmasi. Dua run
   di atas bisa digantikan satu cek lokal yang legal.
4. **Dua fix yang ditolak = berhenti menebak, bukan menambah tebakan.**
   Satu baris yang sama sudah menolak tiga perbaikan berturut-turut berarti
  hipotesis awal salah, bukan salah ketik pada label. Empat tebakan
   berturut-turut pada satu baris membakar seluruh runway debugging.

   Urutan setelah dua penolakan:

   a. Ambil file yang **benar-benar di-build CI**, bukan dari disk dan bukan
      dari cache alat baca:

      ```bash
      gh api repos/<OWNER>/<REPO>/contents/<path>\\?ref=<SHA> \\
        --jq '.content' | base64 -d > /tmp/built.kt
      sha256sum /tmp/built.kt <path-di-disk>   # harus sama
      ```

   b. Bandingkan **byte** untuk nama-nama yang disebut compiler:

      ```bash
      python3 -c "raw=open('/tmp/built.kt','rb').read(); \\
        print(raw.count(b'namaFungsi')); i=raw.find(b'private fun'); \\
        print(repr(raw[i:i+34]))"
      ```

      Lihat `repr()` dan `hex`, bukan `sed`/`grep` — output teks bisa
      menampilkan nama yang salah sementara byte-nya benar.

   c. Kalau nama di deklarasi dan di pemanggil berbeda satu huruf, itu
      penyebabnya. Perbaiki keduanya ke satu nama dalam satu operasi, lalu
      verifikasi hitungannya — `count` untuk kedua nama, bukan `sed -n`.

Verifikasi lokal yang sah untuk mendeteksi kerusakan struktural (bukan
bukti compile, dan tidak boleh disebut begitu):

```bash
python3 - <<'PY'
import re
src = open('<file>', encoding='utf-8').read()
print("brace balance:", src.count('{') - src.count('}'))
print("return@labels:", sorted(set(re.findall(r'return@(\w+)', src))))
PY
```

`return@launch` dari `scope.launch { }` itu sah. Label yang tidak kamu
temani titik pemanggilnya di file yang sama adalah tanda menebak.

## Ketika alat baca tidak sepakat dengan compiler

Gejalanya: beberapa alat baca menampilkan isi yang **tidak sama** untuk file
yang sama, dan tidak ada yang sepakat. Yang muncul di satu sesi:

```
python split('\n')      -> baris 104 = 'private fun kendalkan(aksi: String) {'
sha256 file vs GitHub   -> identik
grep -n 'kendel'        -> hanya baris 94
raw.count(b'kendelkan') -> 1
raw[i:i+34]             -> b'private fun kendalkan(aksi: String) {'
```

Lima "pembuktian" beruntun saling menyangkal. Penyebabnya bukan kode dan bukan
lingkungan — nama yang dicari punya satu huruf berbeda, dan beberapa jalur baca
memenormalisasikannya ke bentuk yang lebih familiar.

Aturan yang berhasil menembus ini:

1. **Compiler tidak pernah salah soal nama.** Kalau `Unresolved reference`
   disebut untuk nama yang menurutmu ada, itu benar. Jangan pernah
   "membuktikan" sebaliknya — itu membatalkan bukti yang paling tepercaya.
2. **`sha256sum` yang sama tidak berarti isinya sama yang dibaca.** Hash
   membuktikan file-nya identik; tidak membuktikan penampakanmu benar.
3. **Turun ke byte begitu dua alat berbeda berbeda.** `repr()` dan `count()`
   pada `bytes`, bukan `sed`/`grep`/`read_file`. Lihat setiap karakter dalam
   hex untuk nama yang pendek.
4. **Cari nama yang mirip, bukan yang identik.** Kalau yang dicari tidak ada,
   jangan simpulkan file-nya rusak — cari yang bedanya satu karakter. Huruf
   `i`, `l`, dan `k` yang tertukar tidak terbaca di teks yang dirender.
5. **Satu operasi untuk satu perbaikan.** Mengganti nama secara bertahap
   bisa menghapus deklarasinya sendiri dan menghasilkan duplikat. Terapkan
   ke kedua nama dalam satu operasi, lalu hitung keduanya.

Yang **tidak** boleh dilakukan setelah alat berselisih: menambah tebakan
syntax, mengganti struktur yang belum terbukti salah, atau menyatakan
"hampir beres". Yang benar adalah turun ke byte.

## Area ketuk di dalam area gesture: jangan assume urutan pointer

Menambah `clickable` di layar yang **sudah punya gesture sendiri** di area yang
sama berarti gesture itu saling berebut. Yang paling sering: swipe untuk
menutup, drag untuk mengubah nilai, atau scroll.

Periksa dulu apa gesture induknya membungkus area itu:

```python
lines = open(p, encoding='utf-8').read().split('\n')
for i, l in enumerate(lines):
    if 'detectVerticalDragGestures' in l:
        # naik sampai baris pembungkus Modifier
        j = next(k for k in range(i, 0, -1) if lines[k].strip().startswith(('Column(', 'Box(')))
        # dan turun sampai pemanggilan komponen yang mau diketuk
        print(i + 1, 'dibungkus oleh', lines[j].strip())
```

Kalau ternyata area itu sama, taruh `clickable` di **Box pembungkus** milik
komponen itu, bukan di modifier komponen gambar:

- Modifier `graphicsLayer` (skala saat dijeda, `clip`, `shadowElevation`)
  ikut ter-`clickable` kalau disambungkan langsung, dan `clip` ikut
  menggeser hitbox saat skalanya berubah — ketuk meleset tepat saat animasi jalan.
- Box pembungkus memberi area ketuk yang diam, terpisah dari animasi.

Lalu **katakan batasnya di laporan**: "ketuk dan swipe ada di area sama,
keduanya secara teori tidak berebut selama jari tidak bergerak, tapi belum
diuji di perangkat". Jangan klaim gesture-nya aman hanya karena modifier-nya
terpisah — urutan pointer input Compose tidak bisa dibuktikan dari membaca kode.

## Bias add-vs-delete

Dua dari error di atas **tidak seharusnya diperbaiki dengan menambahkan
sesuatu**. Setelah compiler menyebut sebuah simbol, urutannya:

1. Apakah simbol ini memang perlu ada?
2. Kalau tidak perlu — hapus.
3. Kalau perlu — baru cari cara membuatnya compile.

Menambahkan import atau method stub untuk membuat compiler senang adalah
default yang lebih lambat: ia meninggalkan kode mati yang tidak akan pernah
dipanggil, dan sesi berikutnya harus membersihkannya lagi.

## Ekstrak keputusan ke objek murni kalau collaborator-nya final

Test untuk kelas yang bergantung pada collaborator tidak bisa ditulis dengan
JUnit polos kalau collaborator-nya `final class` (default Kotlin) dan repo
tidak punya mocking library. Cek dulu:

```bash
grep -n 'testImplementation' app/build.gradle.kts
```

Kalau tidak ada `mockk`/`mockito`, hand-rolled subclass tidak akan berhasil, dan
menambah dependency hanya untuk satu file test melanggar aturan "jangan tambah
dependency baru". Jalur yang benar: **ekstrak keputusannya ke objek murni**
(`when`/`if` yang tidak butuh Android) dan biarkan I/O di kelas pendamping.

Ini juga satu-satunya cara menguji **`RemoteViews`** — kelasnya hanya bisa
dibangun di dalam proses app, jadi tidak ada yang bisa memanggilnya dari test.
Dan kelas yang layak diekstrak adalah yang keputusannya kalau salah **tidak
melempar exception**: ikon yang tertukar hanya menampilkan tombol yang salah,
tanpa jejak di log.

### Nilai yang tertanam di APK juga layak diekstrak ke objek murni

Bukan cuma keputusan. URL yang di-hardcode di dalam composable — tautan repo,
sosial, donasi — tidak bisa diperbaiki lewat terjemahan atau setelan setelah
APK terkirim, dan satu-satunya cara memeriksanya kalau ia di dalam composable
adalah membuka app di perangkat lalu mengetuk tiap baris.

Pindahkan ke satu objek di file terpisah, dengan **satu daftar `all`** yang
memuat semuanya, supaya tes "semua https dan tidak kosong" otomatis mencakup
tautan yang ditambahkan nanti — bukan mengharuskan tesnya diperbarui juga tiap
kali ada tautan baru.

```kotlin
internal object AboutLinks {
    const val Repo = "https://github.com/<owner>/<repo>"
    val all = listOf(Repo, Profile, Instagram, Donate)
}
```

Yang perlu dijaga: komentar KDoc di objek itu menjelaskan **kenapa** ia
terpisah (tautan tertanam di APK, salah ketik tidak bisa diperbaiki setelah
rilis). Tanpa itu, sesi berikutnya mengembalikannya ke dalam composable karena
"lebih dekat ke pemakaiannya".

## `git add <subfolder>` bisa tidak mencakup berkas yang kamu ubah

`git add <path-subfolder>` hanya mengambil yang ada di path itu. Kalau satu
fitur menyentuh berkas di beberapa paket terpisah — `data/db/` untuk skema,
`di/` untuk registrasi DI, `ui/` untuk layar — commit per lapisan akan
**diam-diam meninggalkan sebagian berkas di luar staging**.

Bentuk paling berbahaya: registrasi migrasi database. Skema Room naik versi di
`data/db/`, migration object ditulis di `data/db/`, tapi daftar migrasi yang
dipakai saat runtime ada di `di/DatabaseModule.kt`. Kalau file itu tidak ikut,
CI tetap hijau — Room baru gagal **saat aplikasi dijalankan**, di perangkat
user, bukan di log mana pun.

Gejalanya: commit terasa lengkap, `git status` bersih setelah commit untuk
path yang kamu staging, tapi `git show HEAD:<path-di-luar>` tidak punya
simbol yang baru kamu tambahkan.

Dua pengaman yang murah:

```bash
# sebelum commit: seluruh perubahan yang ada di working tree
git status --porcelain            # harus kosong setelah commit

# verifikasi simbol yang baru ada benar-benar ada di HEAD
git show HEAD:app/src/main/kotlin/<pkg>/di/DatabaseModule.kt | grep -c 'MIGRATION_8_9'
# 0 = tidak ikut ter-commit

# atau add per-file dengan -A supaya tidak ada yang tertinggal
git add -A <path-yang-dimaksud> && git commit
```

Daftar periksa untuk fitur yang menyentuh skema Room: entitas, objek migrasi,
**pendaftaran migrasi**, file Room DB (versi), modul DI, test migrasi.
Lima berkas di empat direktori berbeda — `git add data/db/` menutupi tiga.

## Sebelum mengedit file sumber: cek test yang MEMBACA file itu

Test di repo ini tidak semuanya menguji perilaku. Sebagian membaca **teks file
sumber** dan mengunci strukturnya — urutan `SectionTitle(` terhadap
`HorizontalDivider(`, keberadaan sebuah import, jumlah baris. Test itu merah
karena file-nya berubah, bukan karena kodenya salah, dan tidak ada cara melihat
itu dari diff.

Daftar file yang dibaca test **ada di build file**, dan itu indeks yang bisa
dibaca sebelum menulis:

```bash
grep -A25 'testOptions' app/build.gradle.kts
# it.inputs.file(...) menyebut tiap file yang jadi input test

grep -rln 'SettingsScreen\|strings.xml\|README' app/src/test/kotlin
```

Jalankan itu **sebelum** patch pertama ke layar atau resource bersama, bukan
sesudah CI merah. Yang paling sering menggigit:

- **Menghapus atau memindahkan section** di layar yang punya test struktur —
test-nya menghitung kemunculan, jadi section yang hilang menggeser semuanya.
- **Mengubah `strings.xml`** — test yang membandingkan kosakata peran/status
  membaca resource yang sama.
- **Memindahkan komponen dari satu layar ke layar lain** — test yang mengunci
  "komponen ini dipakai dari ui/components, bukan didefinisikan lokal" ikut
  terbaca.

Kalau file itu memang harus berubah, sebutkan di laporan test mana yang perlu
ditinjau — jangan menunggu CI menemukannya.

## Pola yang dikira ada, ternyata tidak

Sebelum menyebut "pola ini sudah dipakai di repo, tinggal diikuti", buktikan
di **call site**, bukan di blok import.

```bash
grep -rn 'rememberLauncherForActivityResult' app/src/main/kotlin
# bisa saja yang cocok cuma baris import di kepala file

# yang membuktikan: pemakaiannya
grep -rn 'launcher.launch(\|ActivityResultContracts\.' app/src/main/kotlin
grep -rn 'PickVisualMedia\|GetContent' app/src/main/kotlin
```

Mekanismenya: blok import memuat banyak nama API yang dipakai di **satu**
tempat, dan grep yang longgar akan mencocokkan import itu. Kesimpulan "sudah
ada pola Photo Picker di Settings" yang terambil dari baris import membuat
sesi berikutnya merancang fitur yang sebetulnya belum pernah dipakai di repo.

Aturan yang lebih umum: **nama API yang kamu sebut sebagai "sudah ada" harus
muncul sebagai pemanggilan, di file yang berbeda dari import-nya.** Kalau satu
file saja yang cocok, belum ada pola.

## Mengubah kontrak komponen yang dipakai bersama: hitung pemanggil dulu

Satu fitur di app ini butuh nilai baru dialirkan ke isi dialog share — pilihan
format. Bentuk lambdanya berubah dari `@Composable () -> Unit` jadi
`@Composable (CardFormat) -> Unit`, dan setiap pemanggil lama harus ditambah
`_ ->`. Kalau pemanggil tidak ditemukan lebih dulu, yang tidak dikompilasi baru
ketahuan lewat error, dan itu satu putaran terbuang.

1. **Cari semua pemanggil SEBELUM mengubah signature.**

   ```bash
   grep -rn 'ShareCardDialog(' app/src/main/kotlin
   ```

   Hasilnya adalah daftar kerja: mana yang berubah, mana yang sengaja dibiarkan.

2. **Tambah kemampuan tanpa mengubah bentuk kalau bisa.** Kalau hanya sebagian
   pemanggil yang butuh nilai baru, tambahkan parameter opsional
   (`allowFormatChoice: Boolean = false`, `onShareLyrics: (() -> Unit)? = null`)
   alih-alih mengubah bentuk lambda. Pemanggil lama compiles tanpa disentuh
   dan perilakunya tidak bergeser diam-diam. Mengubah bentuk lambda hanya
   benar kalau **semua** pemanggil memang butuh nilai barunya — itu keputusan
   desain, bukan pilihan teknis.

3. **Perhatikan pemakaian yang keluar dari ekspektasi.** Getter enum yang
   dipanggil sebagai fungsi — `format.labelRes()` di tempat deklarasinya
   `@get:StringRes val labelRes: Int` — adalah error compile. Cek ulang setiap
   pemakaian setelah mengubah bentuk tipe, jangan hanya yang kelihatan di diff.

### Mempromosikan `private` helper jadi shared: pindahkan, jangan salin

Komponen kartu baru butuh helper yang prosedurunya sudah ada, tapi `private` di
file lama. Dua jalan:

- **Salin** → tiap kartu diam-diam punya versinya sendiri; bug yang sama
  diperbaiki dua kali, atau tidak sama sekali.
- **Pindahkan** → satu implementasi, satu tempat diperbaiki.

Kalau dipindahkan, dalam **commit yang sama**:

- hapus versi lama beserta `import` yang jadi yatim (`Brush`, `Offset`,
  `CircleShape` di sini — `grep -c` per nama: kalau sekarang hanya sisa satu,
  itu baris import, bukan pemakaian),
- arahkan call site di file lama ke nama baru (`VibeBackground` →
  `CardBackground`),
- jalankan `git status --porcelain` — kalau file lama masih muncul tidak
  terstag, pemindahanmu belum utuh.

Setelah memindahkan helper ke file bersama, pindahkan juga soal domainnya ke
KDoc: kenapa helper ini dipakai bersama, dan kenapa komponen tertentu tidak
memakainya. Tanpa itu, sesi berikutnya memindahkan atau mengganti lagi tanpa
tahu bedanya.

## Patch panjang merusak file

Tool patch berbasis fuzzy-match-aturan, bukan editor. Dua mode kerusakan yang
terbukti: menulis ribuan karakter pengulangan (CJK) ke baris yang berbatasan
  dengan string panjang, dan menulis literal penanda pemotongan
(`...[truncated]`) sambil **menghapus baris kode yang seharusnya dipertahankan**.

Keduanya lolos karena laporan hasil tool menampilkan diff yang terlihat wajar.
Yang menyelamatkan hanya satu langkah: baca ulang byte di disk.

```python
p = '<file>'
lines = open(p, encoding='utf-8').read().split('\n')
for i in range(max(0, 71), min(len(lines), 84)):
    print(i + 1, repr(lines[i]))          # repr, bukan print biasa
src = '\n'.join(lines)
print('truncated marker:', '[truncated]' in src)
print('brace balance:', src.count('{') - src.count('}'))
print('non-latin:', [l for l in lines if any(ord(c) > 0x2FFF for c in l)])
```

Empat cek yang harus berjalan setelah patch apa pun ke file kode:

1. **Balancedness kurung kurawal** nol — mendeteksi penghapusan blok.
2. **Literal penanda pemotongan nihil** — mendeteksi pen-writing terputus.
3. **Nol karakter non-Latin** di baris yang disentuh.
4. **Simbol yang seharusnya ada masih ada** (`grep -c` untuk nama fungsi dan
   parameternya) — mendeteksi penggantian yang menimpa baris lain.

### Anchor multi-baris harus memuat SETIAP baris di antaranya

Kerusakan paling sering pada sweep massal (ganti satu nilai di puluhan tempat)
muncul justru dari anchor yang **ditulis ulang dari ingatan**: blok lama ditulis
ulang lebih pendek, satu baris yang tidak relevan (mis. `overflow = …` di sebelah
`color = …`) hilang tanpa terlihat di diff, dan `}` tambahan masuk ke tempat yang
sama. Diff-nya terlihat wajar, brace balance tetap nol **kalau `}` pasangannya
juga ikut**.

Dua aturan yang mencegahnya:

- **Ganti ekspresi, bukan blok.** `replace_all=True` pada string pendek yang unik
  (`Color.White.copy(alpha = 0.4f)`) tidak bisa menghapus baris tetangga.
- **Kalau anchor blok memang perlu, salin dari file yang baru dibaca**, jangan
  dari pemahamanmu tentang bentuknya. Setelah itu cek baris pertama dan terakhir
  blok hasil, plus `git diff <file>` untuk baris yang hilang — bukan hanya
  `success: true` dari tool.

Sweep yang menyentuh belasan file hampir selalu menyisakan satu file yang brace-nya
tidak seimbang; jalankan cek nomor 1 untuk **semua file yang diubah** sebelum
push, bukan hanya file yang terasa berisiko.

### Saat CI melaporkan `Name expected`, hitung kurungnyalah lebih dulu

Kurung-kurawal yang tidak seimbang menghasilkan pesan yang **menyebut baris yang
benar, dengan alasan yang salah**. `Name expected` di baris `private companion
object` sebenarnya artinya ada satu `{` yang hilang di baris 60-an — tempat
constructor diketik ulang. `Expecting a top level declaration` di baris terakhir
adalah gejalanya: satu `}` menutup kelas lebih awal, jadi companion object
jatuh ke luar scope.

Jadi pesan syntax yang tidak masuk akal **bukan** alasan untuk menebak baris yang
disebut. Hitung dulu:

```python
lines = open(p, encoding='utf-8').read().split('\n')
depth = 0
for i, l in enumerate(lines, 1):
    depth += l.count('{') - l.count('}')
    if '{' in l or '}' in l:
        print('%4d depth=%3d %s' % (i, depth, l[:70]))
print('FINAL DEPTH:', depth)      # harus 0
```

`FINAL DEPTH` negatif berarti ada `}` berlebih; baris di mana depth pertama kali
turun di bawah 0 adalah lokasi penutup yang salah. Depth positif di akhir
berarti ada blok yang tidak pernah ditutup — sering di fungsi yang dipotong
saat penggantian.

Bedakan dari kasus nama yang mirip satu huruf (lihat di bawah): di sana
`grep`/`sed`/reader saling berbeda soal isi file; di sini **semua reader
konsisten dan semuanya salah**, karena file-nya memang tidak seimbang. Keduanya menunjuk ke bawah, bukan ke reader yang lain.

Kabar baiknya `git checkout <file>` masih membatalkan kerusakan selama belum
di-commit — itulah alasan commit per lapisan segera setelah verifikasi.

Kalau satu gagal: `git checkout <file>` untuk mengembalikan, lalu tulis ulang
dengan **Python** (`open(p).write()` atau `lines[i:j] = [...]`) yang deterministik
dan tidak punya fuzzy match. Patch pendek tetap aman; yang berbahaya adalah
patch panjang multi-baris pada prose dan KDoc.

Kabar baik: `git checkout <file>` membatalkan damage dengan utuh selama
perubahan belum di-commit — kenapa setiap lapisan harus di-commit segera setelah
diverifikasi, bukan dikumpulkan.

## Kolom baru di entitas Room: bentukkan nullable tanpa DEFAULT NULL

Menambah kolom nullable ke entitas Room punya satu jebakan yang jarang kepikiran: Room
menulis ulang `createSql` dengan `DEFAULT NULL` eksplisit kalau default-nya
disebutkan, sehingga `PRAGMA table_info` mengembalikan string `'NULL'`
kecuali kolomnya nullable kosong — dan Room sendiri menolak database itu.
Kolom nullable baru **biarkan kosong** di deklarasi entity dan di
`COLUMNS_ADDED_IN_*`; migrasi `ALTER TABLE ... ADD COLUMN` harus tanpa
`DEFAULT`.

Aturan kedua yang berlaku untuk setiap skema: **kolom baru menempel di akhir**.
Kolom `ALTER TABLE ADD COLUMN` selalu paling kanan, jadi field baru di data
class harus deklarasikan paling akhir — kalau tidak, pemetaan Room ke kolom
meleset pada database yang sudah dimigrasikan.

Test migrasi yang mengunci ini cukup membandingkan `COLUMNS_ADDED_IN_X` dengan
selisih nama kolom antara skema versi sebelum dan sesudah, plus assert bahwa
tabel dan indeks lama tidak berubah. Bandingkan **`createSql` tiap tabel lama
harus identik** — kalau ada yang bergeser, artefak bukan hasil Room yang benar.

## Pilih sumber gambar: salin ke internal, jangan simpan URI

Untuk artwork atau lampiran yang dipilih user, komponen `@Singleton` +
`@Inject constructor` + `@ApplicationContext` yang punya `Context` adalah
pola yang sudah ada di repo — tidak perlu interface baru.

Dua keputusan yang salah mahal kalau dibalik:

- **Salin berkasnya ke `filesDir`, jangan simpan `content://`.** Photo Picker
  memberi izin sementara yang bisa dicabut; URI-nya mati setelahnya. Path di
  `filesDir` tidak bergantung pada itu. (`cacheDir` juga salah untuk nilai yang
  memang harus bertahan — Android boleh menghapusnya.)
- **Nama berkas dari hash id, bukan dari id mentah.** Id bisa mengandung
  pemisah direktori, jadi apa pun yang dibangun dari id mentah berisiko menulis
  ke luar folder. Dan **ganti semua karakter non-alfanumerik dengan satu
  karakter itu sendirinya tidak aman**: `ms:1` dan `ms_1` jadi nama yang sama,
  satu berkas menimpa yang lain. Pakai hash yang sudah ada di repo kalau ada
  (misalnya helper SHA-1 di scanner), dan uji tabrakannya dengan beberapa id
  sekaligus sebelum commit:

```python
import hashlib
def stable(s): return hashlib.sha1(s.encode()).hexdigest()[:16]
ids = ['ms:1234', 'yt:abc-def', 'slskd:user/song.flac', 'ms:1', 'ms_1', '../escape']
names = {i: stable(i) for i in ids}
print(len(set(names.values())), 'dari', len(ids), 'unik')
print([n for n in names.values() if '/' in n or '..' in n])   # harus kosong
```

- **Hapus berkas lama setelah kolom terisi, bukan sebelum.** Membalik urutan ini
  menghapus sampul yang masih tampil kalau penulisan kolom gagal.

## Ganti satu baris di titik yang dipakai semua, bukan di tiap call site

Sebelum menambah kontrol baru di banyak tempat, cari **satu tempat** yang sudah
merender objek itu. Kalau artwork semua layar datang dari satu komponen yang
membaca kolom yang sama, override cukup jadi satu baris di sana
(`custom ?: aslinya`) dan satu kolom di entitas — bukan puluhan berkas.

### Tapi "satu komponen" tidak berarti "satu jalur baca"

Baris tunggal itu benar **hanya kalau tidak ada pembaca lain**. Sebelum
mengklaim perubahan berlaku global, grep nama field itu sendiri di seluruh
tree dan lihat semua yang membacanya langsung, bukan lewat komponen itu:

```bash
grep -rn '<namaField>' --include=*.kt app/src/main/kotlin
```

Tiga hasil yang harus dibedakan:

- **Pembaca lewat komponen** — otomatis dapat override.
- **Pembaca langsung dari model** (`imageUrl = song.thumbnailUrl`) — tidak dapat
  override. Satu baris per tempat.
- **Pembaca dari sumber lain** (mis. `metadata?.artworkUri` dari MediaSession,
  atau `BitmapFactory` di `RemoteViews`) — di luar jangkauan model sama sekali.
  Jangan memperbaikinya; catat sebagai batas, atau cari siapa
  yang sebenarnya menulis sumber itu.

Kelas ketiga perlu dibedakan dari bug. `FolderCover` yang memilih gambar saat
pemindaian **bukan** jalur tampilan — ia hanya memberi nilai ke kolom yang
kemudian dibaca komponen. Menyebutnya bug adalah salah baca.

Kalau grep tidak menemukan pembaca langsung di luar komponen, itu bukti
"satu titik" — bukan asumsi. Kalau ada, catat satu per satu di laporan, jangan
diam-diam.

Untuk interaksi, parameter opsional yang bernilai `null` adalah cara menambah
kemampuan tanpa mengubah pemanggil yang tidak butuh:

```kotlin
onArtworkClick: (() -> Unit)? = null,
// ...
modifier = if (onArtworkClick != null) Modifier.clickable(onClick = onArtworkClick) else Modifier
```

Pemanggil lama compiles tanpa perubahan dan perilakunya tidak berubah — dan
menambah ikon atau kontrol visual di tiap baris membuat baris itu penuh serta
menutupi objek yang justru harus terlihat.

### Membuat gambar bisa diketuk = regresi accessibility kalau tanpa label

Menambahkan `Modifier.clickable` pada gambar **membuatnya jadi elemen fokus
yang bisa dibaca pembaca layar**. Tanpa `contentDescription`, TalkBack
mengumumkannya sebagai "tombol" tanpa nama — itu lebih buruk daripada gambar
dekoratif yang sebelumnya bisa dilewati.

Jadi `clickable` pada artwork **wajib** berpasangan dengan label. Kalau
komponen gambar yang dipakai bersama belum punya parameter
`contentDescription`, itu pekerjaan terpisah yang menyentuh semua pemanggilnya.

### Kalau labelnya belum ada: pilih antara menahan, atau mengatakannya

Dua opsi yang jujur, dan yang ketiga (diam-diam menunda) yang tidak:

- **Tahan `clickable`-nya** sampai komponen gambarnya punya parameter label.
  Nol regresi, tapi interaksinya tidak ada sama sekali.
- **Kirim `clickable` sekarang** dan nyatakan batasnya eksplisit di laporan:
  "sampul sekarang jadi elemen fokus yang TalkBack baca tanpa nama; perbaikannya
  commit terpisah setelah rilis". Ini bisa diterima kalau visual tampilannya
  jelas lebih penting sekarang, dan labelnya masuk sebagai pekerjaan terjadwal.

Yang **tidak boleh** terjadi: mengirim `clickable` tanpa label, lalu membuang
string label yang tidak terpakai supaya tidak kelihatan menggantung. String
yang dibuang menyembunyikan gap yang sama persis, dan gap itu tetap ada di
produk yang tayang. Kalau memilih opsi kedua, string label **jangan** dihapus —
simpan supaya pekerjaan berikutnya tinggal memasangnya.

Tidak ada snackbar di seluruh app, jadi hasil yang gagal tidak punya tempat
tampil. Itu alasan yang sah untuk tidak menambah snackbar; bukan alasan untuk
tidak menyebutkan gangguannya.

Cek string yang ditambahkan benar-benar dipakai, kalau tidak hapus:

```bash
for k in kunci1 kunci2 kunci3; do
  printf '%s %s\n' "$k" "$(grep -rc "R.string.$k" --include=*.kt app/src/main | grep -v ':0' | wc -l)"
done
```

Resource yang ditambahkan lalu tidak terpakai adalah bukti fitur belum tuntas,
bukan sisa yang boleh dibiarkan.

Tabel backlog di vault atau catatan proyek ditulis dari **rencana**, bukan
dari isi repo. Kalau tabel bilang "belum" sementara kodenya sudah lengkap
dan sudah ter-commit, tabel itu yang salah — bukan pekerjaannya.

```bash
# sebelum mengerjakan item backlog:
git log --oneline -5 -- <path-fitur>
ls app/src/main/kotlin/<pkg>/<fitur>/
```

Sekaligus periksa apakah fiturnya sudah punya entri changelog — artinya
sudah pernah direncanakan, cuma belum pernah menyentuh CI.

## Sinkronkan dokumen dengan kode: bukti per item, bukan baca headers

Dokumen proyek (blueprint, roadmap, scope list) bisa tertinggal puluhan versi
di belakang — itu kondisi normal, bukan kegagalan. Yang gagal adalah klaim
di dokumen itu **tanpa bukti**. Sebelum mencentang `[x]`, cari bukti di kode,
dan bentuk klaimnya harus sesuai dengan apa yang kode itu benar-benar lakukan:

| Tampilan di dokumen | Bukti yang dicari | Kesalahan yang sering |
|---|---|---|
| "Library: Songs / Albums / Artists / **Folders**" | tab di `LibraryScreen` | butuh tab-nya benar-benar ada, bukan cuma string filter |
| "Queue: lihat, **reorder**, hapus" | fungsi mutasi antrean | reorder pakai tombol naik/turun bukan drag — itu fitur, jangan tulis "drag" |
| "Metadata: baca tag **ID3**" | pustaka yang dipakai | kode pakai kolom MediaStore, bukan parser ID3 |
| "Cache stream" | penulisan ke cache saat play | yang ada hanya unduh manual — itu BEDA |
| "filter pills (**mood**)" | nilai enum filter | enum-nya jenis hasil (Semua/Lagu/Artis/Album), bukan mood |

Aturan: **kalau kode mengerjakan sesuatu yang lebih sederhana dari yang
dokumen janjikan, tulis apa adanya di dokumen.** Baris "Cache stream otomatis
— yang ada hanya unduh manual" lebih berguna daripada centang yang menyesatkan.
Kotak kosong yang jujur lebih baik daripada kotak centang yang menekan.

**Periksa juga subtree yang tidak biasa.** Fitur besar bisa hidup di modul
terpisah (`settings.gradle.kts` → `include(...)`) dan tidak muncul di
`app/src/`, sehingga grep di satu modul mengira fitur itu belum ada.
Termasuk fitur yang **tidak tercatat sama sekali** di dokumen — tanda bahwa
dokumen yang perlu disinkronkan, bukan kode yang perlu ditulis.

```bash
grep -n 'include(' settings.gradle.kts        # modul nyata
ls <modul>/src/main/kotlin/.../             # fitur yang hidup di sana
grep -rli '<fitur>' app/src/main/kotlin      # atau tidak ada sama sekali
```

**Dokumen yang sudah jadi acuan otoritatif harus tetap benar.** Kalau README
menyatakan "kalau ada perbedaan antara kode dan spec, spec yang menang", dokumen
yang basi akan menyesatkan setiap sesi berikutnya. Perbarui sekalian kalimat
di sekitarnya yang merujuk ke keadaan lama, supaya dokumennya tidak
mendeklarasikan dirinya sendiri salah.

## Eksplorasi sebelum implementasi: petakan jalur baca dulu

Sebelum menulis dialog atau layar baru, cari dulu jalur yang **sudah ada** —
itu menghemat satu putaran penuh.

- **`grep -rln 'Komponen('`** → berapa tempat yang benar-benar merender objek
  itu. Kalau widget atau kartu berbagi punya loader sendiri, kolom override
  baru tidak otomatis muncul di sana.
- **Bukti call site, bukan import.** `rememberLauncherForActivityResult` yang
  sudah ada di Settings tidak berarti Photo Picker sudah dipakai.
- **Cek snackbar/toast tersedia.** Kalau nol, umpan balik gagal berarti satu
  lapisan baru plus state-nya. Tandai `ponytail:` di KDoc dan andalkan user
  mencoba lagi sendiri — jangan menambah infrastruktur untuk satu kasus.

Jejak kompas untuk fitur yang lebih besar dari satu layar: jangan langsung
nulis UI. Petakan dulu siapa membaca apa, lalu tanya user dua hal yang tidak
bisa ditebak dari kode (cakupan per lagu/per album, dan apakah hasilnya disimpan
di app atau ditulis balik ke tag berkas).

Tiga "gas" beruntun adalah izin berkala untuk mengerjakan bagian yang jelas,
lalu berhenti di titik yang butuh keputusan. Kalau satu giliran menyelesaikan
semua termasuk bagian yang belum terbukti, kamu menjalankan perbaikan yang
belum diuji.

Yang tidak boleh terjadi: mengerjakan bagian yang tidak terverifikasi lalu
menyebutnya selesai. "Hotfix sudah push" dan "hotfix sudah bisa diunduh user"
adalah dua klaim berbeda, dan yang kedua tidak boleh ikut berdasarkan yang
pertama.

## Satu run pada satu waktu: jangan numpuk, jangan larat

Push = satu run = satu antre runner. Dua aturan yang saling melengkapi:

**Jangan menumpuk run.** Kalau sambil menunggu ketemu tiga masalah, jangan
tiga push. Kumpulkan jadi satu commit, satu push, satu run. Satu putaran CI
≈ 5 menit; lima putaran beruntun ≈ 25 menit terbuang, dan tiap putaran
menambah satu run lagi yang harus dibaca.

**Jangan melompat ke depan.** Selesai satu push: tunggu, baca hasilnya, lalu
edit lagi. Run bisa saja membaca kode yang sudah diperbaiki — makanya error
yang muncul kadang bukan error yang ada di HEAD.

Permintaan eksplisit seperti "tunggu hijau biar ga numpuk CI" adalah aturan
operasional, bukan sekadar saran. Selama run belum hijau, tidak ada edit —
termasuk perbaikan kecil yang kelihatan aman seperti membuang string mati.

**Jangan memicu run kedua di ref yang sama.** Workflow dengan `concurrency`
ber-`cancel-in-progress: true` menaruh push dan `workflow_dispatch` di ref yang
sama (`refs/heads/main`) ke **satu grup**. Run kedua yang masuk antre
membatalkan run yang sedang berjalan, jadi run push yang tadinya bakal jadi
bukti berubah jadi `cancelled` — dan kalau run dispatch-nya ikut dibatalkan,
tidak ada satu pun hasil yang tersisa. Kalau "kok belum muncul" saat memeriksa:
tunggu, run push bisa butuh belasan detik untuk terdaftar. Membatalkan run orang
lain butuh hak admin di repo itu, jadi `gh run cancel` yang login sebagai akun
berbeda akan menolak — pakai token pemiliknya lewat
`POST /repos/<owner>/<repo>/actions/runs/<id>/cancel`.

### Error identik di beberapa run berturut-turut = stagger, bukan bug baru

Kalau dua run gagal dengan pesan **dan nomor baris yang sama persis**, itu
ciri run yang berjalan di commit berbeda. Periksanya satu perintah:

```bash
gh run list --limit 4 --json databaseId,headSha --jq '.[] | "\\(.databaseId) \\(.headSha[0:7])"'
git log --oneline -4
# lalu: di commit yang DIMAKSUDKAN fix-nya, blok itu ada di baris berapa?
git show <sha>:<path> | grep -n 'namaBlokYangDiperbaiki'
```

Kalau nomor baris di HEAD berbeda dari yang disebut log, run itu membaca kode
yang sudah tidak ada lagi. **Tidak ada bug baru** — jangan mulai fix baru.

Kronologi lengkap per run lebih mudah dibaca sebagai satu baris
`databaseId → sha → status`, jadi stagger terbaca sekilas.

## Run yang sudah berjalan jadi sia-sia: tidak ada yang gagal

Kalau menunggu CI lalu **baru memutuskan menaikkan versi**, run itu sedang
membangun APK versi lama. Deploy-nya berhasil, `versionCode` di APK cocok
dengan `build.gradle.kts` saat itu, dan user tidak pernah melihat hotfix.
Tidak ada job yang merah, tidak ada error — kegagalannya total.

Begitu kepikiran bump belum masuk sementara run masih berjalan:

1. **Jangan** pakai APK dari run itu.
2. Push commit versi, konfirmasi run **baru** muncul, kunci ke SHA baru.
3. Matikan watcher yang masih menempel ke run lama supaya tidak melapor
   sebagai sukses padahal sudah ditinggalkan.

Dua run bersamaan memboroskan runner, tapi lebih murah daripada menerbitkan
APK yang isinya bukan hotfix yang dimaksud. Lihat juga
`android-ota-inapp-update` bagian "Urutan yang tidak boleh dibalik".

## Batas bukti: "hijau" bukan "berfungsi"

Compile + lint + test hanya membuktikan bentuk statis. Sebagian permukaan
gagal **diam-diam** — tidak ada exception, tidak ada error di log:

- **Widget / `RemoteViews`** — ID layout atau drawable yang salah membuat
  widget tidak muncul sama sekali. Nol error, nol log. Tidak ada test JVM
  yang bisa menangkapnya karena tidak ada yang merender.
- **Integrasi API** — signature yang salah ditolak dengan kode generik.

Sebutkan batas ini apa adanya di closeout. Untuk permukaan yang gagal diam,
yang masih perlu dilakukan adalah verifikasi di user surface, dan itu tidak
bisa dibuktikan oleh CI.

## Ganti angka satu per baris, bukan global

`str.replace("0.29.0", "0.30.0")` di file catatan yang menyimpan histori per
versi akan **menimpa masa lalu**: baris "fitur X terbit di 0.29.0" diam-diam
berubah jadi "terbit di 0.30.0". Ganti per baris atau pakai anchor unik,
lalu baca hasilnya.

## Pindai tulisan sendiri untuk CJK dan kata rusak

Tulisan yang dihasilkan sering memuat karakter CJK/Cyrillic yang tidak
dimaksud di dalam komentar, identifier, dan pesan error — dan kata Inggris
yang rusak di tengah kalimat Indonesia. Keduanya lolos proofreading karena
terlihat seperti huruf asing yang sah.

Jalankan pindai **di turn yang sama dengan penulisannya**, sebelum patch
berikutnya. Setiap patch menyembunyikan artefak baru, dan artefak yang lolos
lebih sering berupa kalimat yang **tidak valid sama sekali**, bukan cuma salah
eja.

```bash
grep -nP '[^\x00-\x7F]' <file-file-yang-diubah>
```

Sertakan scan **kata Inggris nyasar** (bukan cuma CJK): pola camelCase yang
muncul di dalam kalimat prose, dan pengantar yang menggantung setelah CJK
dihapus. Kalau yang perlu dihapus adalah pengantar bertanda backtick,
pertahankan pungutannya supaya baris tetap grammatik — menghapus CJK saja
akan meninggalkan kata menggantung. Perbaiki ke bahasa Indonesia yang
benar, lalu jalankan ulang sampai bersih.

Scan yang sama wajib jalan untuk **file markdown, changelog, dan file SKILL.md**,
bukan hanya komentar Kotlin. Skill lama yang sudah punya CJK dan
kalimat setengah Inggris yang bertahan melewati beberapa sesi — tidak ada yang
menyebutnya karena isinya masih terbaca. Jalankan scan di file yang kamu patch
langsung, bukan hanya di file yang sedang dikerjakan.

Dan karena `patch` mengganti beberapa baris sekaligus, **kata bisa tergandakan
di sambungan baris**: baris lama berakhir dengan sebuah kata dan baris baru
dimulai dengan kata yang sama, keduanya utuh, hasilnya `perangkat perangkat`.
Setelah patch multi-baris pada prose, baca ulang blok yang diganti dan cek
**baris pertama dan terakhir**-nya. Diff membuat baris yang sama terlihat utuh
di dua tempat, jadi duplikasi sambungan tidak pernah terlihat di diff — hanya di
teks yang dibaca berurutan.

### Terapkan ke SKILL.md sendiri: scan setelah SETIAP patch skill

Bagian di atas berlaku untuk skill ini juga, dan patch skill adalah tempat
korupsi paling sering menumpuk — karena tiap patch menambah prose panjang tanpa
ada yang membacanya ulang. Urutan yang benar:

1. patch satu blok;
2. `skill_view` file itu;
3. scan blok itu untuk non-Latin **dan** kata Inggris nyasar;
4. hanya lalu patch berikutnya.

Kalau beberapa patch dibatchkan tanpa scan di antaranya, blok pertama yang
salah menutupi blok berikutnya — dan tidak ada yang menyebutnya karena isinya
masih terbaca. Kalau satu blok gagal di tengah batch, perbaiki blok itu sendiri;
jangan tulis ulang seluruh file.

Tanda cepat bahwa blokmu perlu ditulis ulang, bukan ditambal: kata yang
terpotong dan tidak punya subjek, atau huruf non-Latin yang menempel di tengah
kata (`menUNJUK` yang jadi `menUNTUK`, akhiran asing di kata Indonesia).
Semuanya hilang bersama artinya kalau dipotong — yang tersisa bukan kalimat
Indonesia.
