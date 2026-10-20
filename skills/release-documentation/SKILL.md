---
name: release-documentation
description: Use when writing README, CHANGELOG, or release notes.
---

# Release documentation

Menjaga README, CHANGELOG, tag, dan GitHub Release tetap saling cocok dan
faktual. Dipakai saat menutup satu fase atau versi proyek.

## Urutan kerja

1. **Kumpulkan fakta dulu, jangan tulis dari ingatan.** Jalankan dan catat:

   ```bash
   git log --pretty='%h %ad %s' --date=short --reverse   # tanggal & urutan commit
   grep -rn "versionName" app/build.gradle.kts           # versi yang benar-benar di-build
   gh run list --limit 5                                 # id CI yang bisa dirujuk
   ```

   Lalu cek apa yang benar-benar ada di kode sebelum mengklaim fitur. Layar yang
   masih memakai placeholder, fungsi yang belum dipanggil, dan menu mati bukan
   fitur. Sebut yang belum ada secara eksplisit; daftar "belum ada" lebih
   dipercaya daripada daftar "sudah ada" yang melebih-lebihkan.

   **Untuk setiap KONTROL yang Anda klaim (pemilih, tombol, filter, tab), cari
   kontrol itu di kode — jangan hanya mencari namanya di dokumen.** Menulis
   "ada pemilih rentang 7 hari / 30 hari / sepanjang waktu" padahal layarnya
   memakai satu rentang tetap adalah klaim palsu yang paling mudah lolos: fiturnya
   memang ada, hanya kontrolnya yang tidak. Grep nama widget-nya
   (`FilterChip`, `SegmentedButton`, `TabRow`, `DropdownMenu`) atau nilai yang
   seharusnya bisa dipilih (`30 hari`, `sepanjang waktu`). Kalau nihil, kontrolnya
   tidak ada — hapus dari dokumentasi. Kalau kode justru punya komentar yang
   menjelaskan kenapa kontrol itu sengaja TIDAK ada, yang salah dokumentasinya,
   bukan kodenya.

   **Ini berlaku juga untuk kode yang Anda sendiri baru tulis di sesi yang sama.**
   Menulis dokumen dari ingatan tentang apa yang Anda *maksudkan* ("slider 5-60
   detik") padahal yang benar-benar ada di kode adalah kontrol lain (`FilterChip`
   dengan pilihan tetap 5/10/20/30/45/60) menghasilkan klaim palsu yang sama
   persisnya. Niat dan implementasi menyimpang dalam hitungan menit, apalagi
   setelah patch berlapis-lapis. Turunkan deskripsi kontrol dari KODE YANG ADA,
   bukan dari ingatan; nilai pilihannya pun di-grep dari konstanta di kode
   (`grep -n 'OPTIONS' <screen>.kt`), bukan diketik dari kepala. Menyatakan
   "slider" untuk `FilterChip` juga salah jenis kontrol, bukan cuma salah angka —
   pembaca mengira bisa menggeser bebas padahal pilihannya tetap.

2. **Tulis CHANGELOG sebagai sumber kebenaran**, lalu turunkan yang lain darinya.
   Format Keep a Changelog: `Added` / `Changed` / `Fixed` / `Removed`. Bagian
   `Fixed` menjelaskan **akar masalah**, bukan "perbaiki bug". Pembaca enam bulan
   lagi butuh tahu mekanismenya, bukan gejalanya.

3. **Samakan README dengan keadaan nyata.** Baris Status harus cocok dengan
   roadmap, dan struktur folder di README harus cocok dengan kode saat ini.

4. **Baru tag dan release**, diturunkan dari changelog (lihat Jebakan).

5. **Verifikasi** dengan `scripts/check-release-docs.py`.

## Aturan

- **Jangan mengarang riwayat versi.** Kalau `versionName` tidak pernah berubah
  antara dua fase, keduanya satu rilis. Menulis nomor versi yang tidak pernah
  ada di build sama dengan membuat riwayat palsu.
- **Klaim yang bisa dihitung harus benar.** Kalau menulis "tujuh perbaikan",
  daftarnya harus tujuh. Kalau maksudnya sebagian, tulis "enam dari tujuh".
- **Setiap klaim yang bisa diverifikasi, diverifikasi:** tanggal, id CI, jumlah
  item, nama file, checksum. Satu angka yang salah merusak kepercayaan pada
  seluruh dokumen.
- **Nomor versi hanya boleh ditulis di satu tempat.** Kalau `versionName`,
  `versionCode`, nama berkas APK, `update.json`, dan halaman unduh ditulis
  terpisah, salah satunya akan melenceng cepat atau lambat. Ambil semuanya dari
  satu sumber (mis. `versionCode`/`versionName` di file build) lewat skrip rilis,
  bukan diketik ulang per rilis. Tempat yang paling sering terlupa justru di
  dalam kode runtime: string versi di `User-Agent`, header, atau pesan log.
  Baca `BuildConfig.VERSION_NAME`, jangan tulis literalnya. Gejala yang paling
  mudah dikenali: nama berkas
  APK memakai penanda fase ("fase1", "fase2") alih-alih nomor versi, padahal
  `versionName` tidak pernah berubah antar fase. Itu tanda versi belum pernah
  dinaikkan, bukan tanda penamaannya kurang jelas.

  **Setelah menaikkan versi, cari nomor versi LAMA di seluruh repo, jangan hanya
    di berkas build.** README, blueprint, dan catatan rilis sering memuat nomor
    versi sebagai prosa, dan tidak ada yang menandai kalau itu tertinggal:
    `grep -rn "0\\.8\\.1" --include=*.md --include=*.kts . | grep -v /build`. Yang
    harus naik bersama: `versionCode` DAN `versionName` (jangan hanya salah satu —
    `versionCode` yang menentukan apakah update ditawarkan, `versionName` yang
    ditampilkan), baris versi di README, heading CHANGELOG, dan tautan tag di kaki
    CHANGELOG.

    **Tapi nomor versi lama yang muncul di catatan HISTORIS harus dibiarkan.**
    Berhimpit sama satu grep di atas: kalau setiap kemunculan angka lama ikut
    dinaikkan, catatan rilis yang lalu ikut berubah dan claims yang benar
    berubah jadi salah — tanpa satu pun error. Bedakan dua jenis kemunculan:

    | Jenis | Contoh | Aksi |
    |---|---|---|
    | Status saat ini | baris versi README, `update.json` | naikkan |
    | Sejarah / asal usul | tabel fitur, catatan rilis lama, changelog | biarkan |

    Jangan pernah menaikkan nomor versi dengan `replace` global pada berkas
      yang menyimpan riwayat (catatan proyek di vault, CHANGELOG). Contoh:

    ```python
    # SALAH — merusak histori tanpa error
    t = open(note).read().replace("0.29.0", "0.30.0")

    # BENAR — jangkarkan baris statusnya
    t = t.replace("| Versi | **0.29.0** (versionCode 43)",
                  "| Versi | **0.30.0** (versionCode 44)")
    ```

    Setelah menaikkan versi di berkas mana pun yang menyimpan riwayat, grep lagi
    dan baca **setiap** baris yang muncul: kalau baris tabel fitur ikut bergeser
    ke versi yang baru, replace-nya global dan harus diperbaiki per baris.

  **Kalau repo punya skrip rilis, baca dulu dan pakai skrip itu, jangan deploy
  manual.** Skrip semacam itu biasanya membaca `versionCode`/`versionName` dari
  berkas build lalu menurunkan nama berkas APK, `update.json`, dan halaman unduh
  dari satu angka itu — memakai skrip berarti keempatnya tidak bisa melenceng.
  Ia juga biasanya memverifikasi dari LUAR (unduh ulang APK dari server lalu
  bandingkan checksum), jadi hasilnya bukti, bukan klaim.

  **Baca ulang teks catatan SEBELUM menjalankan skrip rilis, bukan sesudah.**
  Catatan itu langsung terpanggang ke `update.json` dan halaman unduh, jadi satu
  salah ketik berarti seluruh siklus rilis harus diulang (skrip, salin, verifikasi
  ulang dari luar) hanya untuk memperbaiki teks. Jalankan pemeriksaan teks yang
  sama seperti pada README/CHANGELOG — em dash, kata slop, salah ketik — pada
  string catatan yang akan dioper, lalu baru panggil skripnya. Biaya proofread di
  depan jauh lebih murah daripada satu siklus deploy ulang.
- **Berkas changelog yang dibaca APLIKASI bukan CHANGELOG.md, dan skemanya
  berbeda.** App sering membaca `assets/changelog.json` yang ditulis untuk
  pengguna (tanpa istilah build), sementara `CHANGELOG.md` ditulis untuk
  pengembang. Keduanya punya skema sendiri, dan yang di JSON biasanya memakai
  nama kolom berbeda (`versionName`/`summary`/`sections`, bukan
  `version`/`changes`). Menulis entri baru dengan pola yang salah tidak
  menghasilkan error apa pun sampai app-nya dibuka — dan kalau kolom wajibnya
  tidak punya nilai bawaan, SATU entri yang salah membuat SELURUH riwayat versi
  gagal dibaca, bukan cuma satu baris hilang. Sebelum menambah entri, buka satu
  entri lama yang sudah ada dan tiru persis nama kolomnya; lalu jalankan tes yang
  membaca berkas itu. Kalau tesnya menulis fixture di dalam berkas tes, ia tidak
  akan pernah menangkap salah ketik di berkas yang benar-benar dikirim — cara
  menutupnya ada di `android-kotlin-cli-build` →
  .

  **Menulis entri lewat patch find-and-replace mudah OVER-ESCAPE kutip, dan
  backslash-nya sampai ke layar user.** Over-escape berarti menambahkan backslash
  lebih banyak daripada yang dibutuhkan JSON, sehingga sisa backslash ikut
  tersimpan sebagai bagian dari teks dan tampil di layar user. Parser JSON tetap
  menerimanya, jadi tidak ada error apa pun — hanya user yang melihat teks aneh.
  Setelah menulis entri apa pun yang memuat kutip, **parse berkasnya dan pastikan
  tidak ada backslash yang bocor ke teks yang menghadap user**, jangan hanya
  percaya bahwa lint JSON-nya hijau:

  ```bash
  python3 -c "import json,sys; d=json.load(open('app/src/main/assets/changelog.json'));
  bad=[(e['versionName'],i) for e in d for s in e.get('sections',[]) for i in s['items'] if chr(92) in i];
  print('bocor:',len(bad)); [print(' ',b) for b in bad]"
  ```

  Aturannya: dalam string JSON, kutip di dalam teks ditulis dengan SATU backslash
  di depannya, bukan dua. Setelah mengedit, baca ulang nilai yang sudah ter-parse
  dan bandingkan dengan apa yang Anda maksudkan, karena mata membaca satu dan dua
  backslash sebagai hal yang sama di dalam diff.
- **Tanggal rilis harus tanggal yang benar-benar terjadi, bukan tanggal yang enak
  dilihat.** Beberapa rilis di hari yang sama sering ditulis bertanggal berurutan
  (satu hari per versi) supaya rapi, dan hasilnya tanggal di MASA DEPAN. Karena
  berkas changelog app ikut dibundel ke APK sementara `update.json`/halaman unduh
  dibuat dari tanggal sistem, dua sumber itu lalu menampilkan tanggal BERBEDA
  untuk rilis yang sama, dan yang di dalam app salah. Kalau rilisnya belum
  terjadi, entrinya belum boleh ada. Cara menutupnya bukan disiplin manual: tes
  harus menolak entri bertanggal setelah hari ini.
- **Tanggal rilis harus punya SATU sumber, bukan dua jam yang berbeda.** Menetapkan
  zona waktu pada skrip rilis TIDAK memperbaiki tanggal yang melenceng: begitu
  Anda menyadarinya, jam sudah melewati tengah malam, jadi `today()` dengan zona
  waktu yang "benar" pun menghasilkan tanggal yang lebih baru daripada tanggal
  rilis. Akarnya dua perhitungan yang terpisah: satu
  ditulis tangan di berkas changelog app, satu dihitung dari jam sistem di skrip
  rilis. Perbaikannya: skrip rilis MEMBACA tanggal dari berkas changelog yang
  ikut dibundel ke APK, bukan menghitungnya sendiri, lalu gagal keras kalau versi
  yang sedang dirilis belum ada di berkas itu. Dengan begitu tanggal di
  `update.json` dan tanggal di dalam APK mustahil berbeda. Mekanismenya (termasuk
  cara mengunci lewat tes) ada di `android-kotlin-cli-build` →
   §10.
- **Tes yang memakai tanggal TETAP tidak menjaga apa pun.** Ia lulus selamanya.
  Untuk memeriksa "tidak ada tanggal di masa depan", tes harus memakai tanggal
  sistem sungguhan (`LocalDate.now()`), dan dijalankan terhadap berkas asli yang
  dikirim ke user, bukan fixture di dalam tes. Tes format (`YYYY-MM-DD`) TIDAK
  cukup: tanggal karangan lolos selama formatnya benar. Tambahkan juga pemeriksaan
  urutan menurun, karena layar riwayat versi biasanya menampilkan entri apa adanya
  tanpa mengurutkan. Pola lengkapnya (termasuk cara membuktikan tes bisa gagal
  dengan mengembalikan bug tanggal) ada di
  `android-kotlin-cli-build` §10.
- **Sebelum memutuskan apa yang dirilis, baca yang sudah LIVE, bukan yang sudah
  di-commit.** `git log` hanya menunjukkan commit lokal; user hanya punya yang
  benar-benar diterbitkan. Sumber kebenaran "apa yang user punya" adalah
  `update.json`/halaman unduh/`versionCode` APK yang disajikan, bukan repo.
  Periksa dulu, jangan berasumsi: `curl -fsS https://<host>/update.json`, lalu
  bandingkan `versionCode`-nya dengan `versionCode` di berkas build. Kalau yang
  live lebih tua, seluruh pekerjaan yang sudah hijau dan ter-commit itu **belum
  sampai ke user** — dan mengerjakan hal baru di atasnya hanya menambah yang tak
  terlihat. Rilis yang sudah terbukti lebih berharga daripada fitur yang belum
  terbukti. Gejala yang paling mudah dikenali: repo sudah di beberapa versi lebih
  maju sementara `update.json` masih menunjuk versi lama, dan tidak ada satu pun
  sesi yang menyadarinya karena semua orang membaca git, bukan server.
- **Kalau user menyerahkan keputusan ("terserah, enaknya gimana"), rilis yang
  sudah TERVERIFIKASI, bukan yang spekulatif.** Urutan prioritasnya: sudah lolos
  seluruh gate (lint + test + artifact terbangun) > benar-benar sampai ke user >
  risiko rendah. Simpan pekerjaan yang belum terbukti di branch sendiri
  (`git checkout -b feat/<nama>` → commit → `git checkout main`) supaya cabang
  rilis tetap bisa dirilis kapan saja; jangan biarkan WIP setengah jalan menahan
  rilis yang sudah matang. Kalau kamu tahu salah satu opsi yang kamu tawarkan
  belum pernah diuji, jangan tawarkan sebagai setara — labeli belum teruji, atau
  jangan sertakan.
- **Kalau yang dikirim adalah MITIGASI, bukan perbaikan yang terbukti, tulis
  begitu.** Rilis yang menutup lubang supaya kegagalan jadi pesan alih-alih
  proses mati TIDAK sama dengan "bug-nya sudah ketemu dan dibetulkan". Menulis
  "memperbaiki force close" padahal akarnya belum terbukti adalah klaim palsu
  yang paling mahal: user berhenti melapor, padahal masalahnya masih ada.
  Rumus yang dipakai: bagian `Fixed` menjelaskan mekanisme yang ditutup, lalu
  bagian `Catatan` menyatakan eksplisit apa yang **belum** dipastikan dan apa
  yang akan menunjukkan akarnya kalau terulang. Sebutkan juga perangkat/lingkungan
  yang tidak tersedia untuk membuktikannya, supaya pembaca tahu kenapa.
  Sama untuk fitur yang belum pernah diuji di perangkat sungguhan — nyatakan,
  jangan diamkan.

  **Mitigasi defensif tanpa logcat berarti `catch (Throwable)`, bukan
  `catch (Exception)`.** Kalau akar force close tidak diketahui karena tidak
  ada logcat, lapis pertahanan yang dipasang harus menangkap `Error`
  (`NoClassDefFoundError`, `NoSuchMethodError`), bukan hanya `Exception` —
  `Error` bukan subclass `Exception` dan lolos dari `catch (e: Exception)`.
  Tulis di catatan rilis bahwa perubahan bersifat menangkap semua yang bisa
  melempar, dan bahwa pesan error yang muncul (bukan force close) adalah yang
  akan menunjukkan akarnya. Jangan menulis "bug diperbaiki" — tulis
  "kegagalan sekarang menjadi pesan, bukan crash".
  Mekanisme lengkap `Throwable` vs `Exception` ada di skill
  `media3-session-uri` (jebakan kesembilan-setengah).
- **Perubahan infrastruktur yang memaksa user melakukan sesuatu WAJIB jadi
  bagian catatan rilis, bukan cuma commit message.** Kalau alamat unduhan pindah
  dan versi terpasang menyimpan alamat lama di dalam APK-nya, user harus memasang
  manual sekali — tulis langkah itu beserta URL lengkapnya, dan jelaskan kenapa
  (mekanisme pembaruan otomatisnya sendiri yang rusak, jadi tidak bisa dipakai
  untuk memperbaiki dirinya). Tanpa itu user melihat "gagal memeriksa pembaruan"
  pada versi yang sebenarnya sudah benar dan menyimpulkan tidak ada yang berubah.
- **Setiap perubahan setelah deploy wajib melewati deploy lagi.** Memperbaiki
  kode setelah APK naik ke server tanpa membangun dan mengunggah ulang berarti
  user mengunduh kode lama sementara dokumentasi menjanjikan yang baru.
**Jangan salin judul commit upstream ke changelog — baca diff-nya.** Judul commit
   adalah klaim orang yang menulis commit, sering ditulis sebelum atau neutro,
   dan tidak pernah menjelaskan apa yang benar-benar masuk. Salinannya jadi
   janji ke user yang tidak ada batasannya.

   Kasus nyata: commit upstreamuyo "add core audio player", sementara isi
   diff-nya folder scanner SAF, tema anime, dan `NowPlayingScreen` — pemutar
   intinya sendiri tidak berubah sama sekali. Changelog yang menyalin judul
   itu membuat user menunggu pemutar audio yang tidak pernah datang.

   ```bash
   git show --stat <sha>              # file apa yang benar-benar berubah
   git show <sha> -- README.md docs/  # sumber narasi yang trustworthy
   git diff <sha>^ <sha> --stat | tail -1   # skala sebenarnya perubahan
   ```

   Tulis entri dari **isi file yang berubah**, lalu baca README/blueprint
      yang ikut berubah sebagai bahan tambahan. Kalau ukuran diff jauh lebih
      besar dari yang judulnya menjanjikan, justru itu yang harus disebut —
      pembaca butuh tahu berapa banyak yang benar-benar masuk.

      **Scale check sebelum commit rilis.** Diff sebesar beberapa ribu baris
      yang lolos CI tanpa pernah dibaca manusia bukan rilis kecil yang aman;
      hijau hanya berarti tidak ada compile error dan test tidak gagal, bukan
      bahwa perilakunya benar. Sebut di laporan closeout berapa baris yang
      masuk tanpa review, dan surface apa yang **belum pernah nyala di
      perangkat** — terutama yang memanggil API eksternal, karena kegagalan
      seperti itu biasanya diam-diam (fitur tidak muncul, tidak ada error).

- **Jangan saat dua sumber punya tahap yang berbeda.** `release.sh` sering
  membuat daftar catatan dari argumen CLI, sementara `changelog.json` yang
  ikut dibundel ke APK punya `sections`. Dua sumber itu tidak saling menjaga:
  mengisi keduanya secara manual pada hari yang sama berarti menuliskannya
  dua kali, dan tidak ada yang gagal kalau hanya satu yang terisi. Sumber
  tunggalnya seharusnya entri teratas `changelog.json`, dengan skrip rilis
  membacanya — sama seperti aturan tanggal di bawah. Selama belum dipindah,
  isi keduanya manual dalam urutan yang sama, dan **cek keduanya setelah
  deploy** pada halaman publik dan di dalam APK.

- **Jangan bungkus semua bug jadi satu klaim dramatis.** Sebagian bug memang
  ditangkap lint atau build; pisahkan yang lolos build dari yang tidak, jangan
  menyatakan semuanya "tidak terdeteksi saat build".
- **Jangan deklarasikan token/kontrol di spec atau tema yang tidak dipakai siapa pun.**
  Saat merombak tampilan, mudah menulis satu set token baru "supaya lengkap" lalu
  hanya memakai sebagian. Token mati lebih buruk daripada tidak ada: ia terlihat
  seperti bagian dari sistem, jadi sesi berikutnya memakainya asal-asalan dengan
  kontras atau perilaku yang belum pernah dihitung untuk konteks itu. Sebelum
  menutup pekerjaan, cari setiap nama yang Anda tambahkan dan pastikan ada
  pemakaiannya di luar definisinya:

  ```bash
  # token warna: definisi vs pemakaian
  for t in $(grep -oP 'val \K\w+(?=\s*=\s*Color)' ui/theme/Color.kt); do
    n=$(grep -ro "BlossomColors\.$t\b" --include=*.kt . | wc -l)
    printf '%-22s dipakai %sx\n' "$t" "$n"
  done
  ```

  Yang `0x` dihapus dari KODE DAN dari spec DAN dari `res/values/colors.xml` —
  satu token biasanya tercatat di tiga tempat, dan menghapusnya di satu tempat
  saja meninggalkan referensi yang menggantung. Kalau tokennya benar-benar akan
  dipakai nanti, jangan tambahkan sekarang.

- **Mengubah satu komponen bersama bisa membuat `import` di berkas LAIN jadi mati.**
  Memindahkan latar ke modifier bersama, atau mengganti komponen dengan yang
  setara, meninggalkan import yang tidak lagi dipakai di berkas yang Anda sentuh
  — dan itu muncul sebagai warning, bukan error, jadi tidak ada yang menahannya.
  Untuk setiap berkas yang Anda ubah, bandingkan daftar import dengan pemakaian
  di badannya: `import androidx.compose.foundation.background` tetap ada padahal
  `.background(` sudah tidak dipanggil lagi.

  **Abaikan `getValue` dan `setValue`.** Keduanya dipakai secara implisit oleh
  delegasi properti `by`, jadi pemeriksaan "apakah nama ini muncul di badan"
  SELALU melaporkannya sebagai mati padahal tidak. Ini contoh hit palsu yang
  akan membuat Anda menghapus import yang dibutuhkan dan mematahkan build.

- **Kalau keputusan user menyimpang dari spec, perbarui spec di commit yang sama.**
  Dokumen desain/blueprint sering memuat rencana yang akhirnya tidak dipakai
  (mis. "tab X jangan tampil sebelum ada isinya"). Kalau user memilih arah lain,
  kodenya benar dan **dokumennya yang harus diselaraskan** — bukan sebaliknya.
  Ini wajib, bukan kerapian: README biasanya menyatakan "kalau ada perbedaan
  antara kode dan spec, dokumen yang menang", sehingga spec yang basi langsung
  menyesatkan sesi berikutnya. Perbarui juga kalimat di sekitar spec yang
  merujuk ke keputusan lama (mis. baris "Fase 1 hanya 4 tab") supaya dokumennya
  tidak kontradiktif dengan dirinya sendiri.

## Jebakan

- **Blok versi baru bisa nyasar ke TENGAH berkas, dan urutan yang salah tidak ada yang menandai.**
  CHANGELOG tumbuh dari atas, jadi blok `[Unreleased]`/versi berikutnya ditulis di paling atas —
  tapi penyuntingan berlapis mudah menyelipkannya di antara dua versi lama (blok `[Unreleased]`
  ditemukan terjepit antara `0.10.0` dan `0.9.1`), dan `git diff` menampilkannya sebagai penambahan
  yang wajar. Akibatnya versi terbaru tidak muncul di tempat pembaca mencarinya, dan versi yang
  dilewatinya seolah jadi yang terbaru. Sebelum menutup pekerjaan changelog, periksa URUTAN seluruh
  heading, bukan cuma blok yang Anda sentuh: `grep -n '^## \[' CHANGELOG.md` lalu pastikan nomornya
  turun monoton. Jangan "memperbaiki" dengan menambah blok baru di atas tanpa memeriksa blok lama —
  itu justru menggandakan entri.
- **Menghitung versi dari jumlah heading `## [` salah — `[Unreleased]` bukan rilis.** Ia tidak punya
  nomor versi dan tidak punya tanggal, jadi klaim "N versi" dari hitungan heading melebihkan satu.
  Hitung hanya heading bernomor + bertanggal. Kalau hasilnya berbeda dari yang Anda harapkan,
  laporkan selisihnya; jangan menambah entri palsu supaya angkanya cocok. Ini juga berlaku saat
  mendelegasikan penulisan riwayat ke subagent: periksa sendiri jumlah dan tanggalnya, karena
  laporan subagent adalah klaim, bukan fakta.
- **Catatan rilis yang dibuat CI hanya daftar commit — bukan catatan rilis.**
  `generate_release_notes: true` mengisi body release dengan daftar judul commit,
  yang bagi user non-teknis tidak berarti apa-apa ("chore: bump versi",
  "fix: typo"). Jangan serahkan halaman release seperti itu. Setelah CI menerbitkan
  release-nya, ganti body-nya dengan catatan sungguhan:

  ```bash
  gh release edit <tag> -R <owner>/<repo> \
    --title "<app> <tag> — <satu kalimat isi utama>" --notes-file /tmp/notes.md
  ```

  Tulis catatan itu untuk PEMAKAI app, bukan untuk kontributor: apa yang berubah
  dari sisi mereka, langkah yang harus dilakukan setelah update, dan apa yang
  belum teruji. Urutan yang benar adalah CI dulu (biar artifact-nya terbit dan
  bisa diverifikasi), baru catatannya — bukan menahan release demi teks.

  **Sebutkan perubahan cara pakai secara eksplisit, karena versi lama tetap
  beredar.** Kalau user harus melakukan sesuatu yang berbeda dari versi sebelumnya
  (mis. tidak perlu lagi menyetel environment variable), tulis sebagai langkah
  bernomor "cara pakai", bukan sisipan di daftar perubahan. Pembaca yang baru
  memasang tidak punya konteks versi lama, jadi langkahnya harus bisa diikuti
  tanpa membaca versi sebelumnya.

- **Body GitHub Release itu snapshot, bukan tampilan langsung CHANGELOG.** Edit
  changelog setelah release dibuat, halaman release tetap menampilkan teks lama.
  Hapus release, pindahkan tag ke commit dokumen terbaru, buat ulang dengan
  `--notes-file`. Ambil catatannya dari changelog, jangan tulis ulang manual.
- **Deploy dulu, amend commit kemudian = APK yang ter-deploy tidak lagi cocok
  dengan tag.** Urutan yang salah: build, deploy, lihat ada yang perlu
  diperbaiki, `git commit --amend`, pindahkan tag. Sekarang tag menunjuk kode
  yang belum pernah di-build, dan APK di server berasal dari commit lama. Kalau
  commit di-amend setelah deploy, **build ulang dan deploy ulang APK-nya**, lalu
  pindahkan tag, lalu perbarui checksum di release notes. Tanda bahayanya:
  checksum di release notes tidak sama dengan `sha256sum` berkas yang benar-benar
  diunduh.
- **Commit dokumentasi setelah deploy: buktikan APK tidak berubah, jangan asal
deploy ulang.** Memperbaiki README/CHANGELOG setelah APK naik ke server TIDAK
berarti APK-nya basi — kalau yang berubah hanya berkas dokumentasi, artifact CI
berikutnya menghasilkan APK yang identik. Cara membuktikannya, dan kenapa ini
penting: dengan bukti identik, checksum di release notes tetap sahih sehingga
tidak perlu deploy ulang dan tidak perlu memindahkan catatan release. Bandingkan
byte-for-byte, bukan ukuran:

  ```bash
  cmp -s apk-lama.apk apk-baru.apk && echo IDENTIK || echo BERBEDA
  # kalau perlu lebih meyakinkan: sha256sum per classes*.dex
  ```

  **Tapi perubahan build config BUKAN perubahan dokumentasi.** Menaikkan
  `versionCode`/`versionName`, menyentuh `libs.versions.toml`, atau menambah
  modul membuat APK-nya berbeda byte — `cmp` akan bilang BERBEDA, dan itu benar.
  Jangan menganggap "cuma angka versi" sebagai aman untuk tidak deploy ulang;
  yang menentukan isi APK, bukan besar-kecilnya diff.

  **Ada golongan ketiga: tooling yang tidak ikut ke dalam APK.** Memperbaiki
  `scripts/release.sh`, skrip verifikasi, atau workflow CI tidak mengubah satu
  byte pun dari artifact yang diunduh user. Untuk golongan ini jangan menaikkan
  versi dan jangan membangun ulang APK "supaya konsisten" — user akan mengunduh
  berkas yang isinya identik dengan nomor versi berbeda. Tetap jalankan `cmp`
  terhadap artifact lama sebagai buktinya, lalu commit sebagai perubahan
  infrastruktur. Kalau ragu sebuah berkas ikut dikirim atau tidak, tanyakan itu
  ke `cmp`, bukan ke perasaan: yang tidak ada di dalam APK tidak perlu dirilis
  ulang.

  Sebaliknya, perubahan kode sekecil apa pun setelah deploy WAJIB melewati build
dan deploy ulang. Yang menentukan adalah isi APK, bukan tanggal commit.
- **Tag anotasi menunjuk objek tag, bukan commit.** `git rev-parse --short v1.2.3`
  mengembalikan hash objek tag (berbeda dari commit yang di-tag), sehingga
  terlihat seolah tag menunjuk commit yang salah. Bandingkan dengan bentuk
  dereference `git rev-parse --short 'v1.2.3^{}'`, dan pastikan hasilnya sama
dengan `git rev-parse --short HEAD`.
- **Jangan deploy APK hasil build lokal kalau ada CI.** Build lokal bersifat
  inkremental, jadi isinya bergantung pada apa yang sudah ada di `build/` sejak
  build terakhir. Artifact CI dibangun dari repo murni. Dua-duanya jalan, tapi
  yang di-deploy harus artifact CI supaya isi APK benar-benar berasal dari commit
  yang di-tag. Kalau ukuran APK CI dan lokal kebetulan sama, **jangan** simpulkan
  isinya sama: bandingkan `sha256sum` per `classes*.dex`, dan kalau ada yang beda
  pastikan perbedaannya memang perubahan yang dimaksud.
- **`curl` ke repo private mengembalikan 404** untuk tag, release, dan raw file,
  yaitu status yang sama dengan "memang tidak ada". Itu artefak auth, bukan tag
  hilang. Verifikasi pakai `gh` yang sudah terautentikasi.
- **Selisih nomor versi antar kanal BUKAN bukti drift — cek apakah kanal itu
  masih dipakai sebelum menyebutnya tertinggal.** Dua kanal yang terlihat
  berbeda sering hanya karena satu sudah ditinggalkan secara sadar, dan
  "menyinkronkan" yang tidak diminta adalah pekerjaan based on asumsi. Urutan
  pemeriksaan, dari yang paling menentukan:

  ```bash
  gh release view <tag-lama> --json assets   # [] = kanal itu memang kosong
  gh repo view --json isPrivate             # true = tak terjangkau publik
  grep -nE 'gh release|git tag' scripts/release.sh   # adakah masih ditarget?
  ```

  Kalau `assets` kosong **dan** repo private **dan** skrip rilis tidak pernah
  memanggil `gh release`/`git tag`, maka kanal itu DITINGGALKAN dengan sengaja,
  bukan rusak. Tidak ada user yang bisa mendapat APK lama, jadi tidak ada yang
  perlu diperbaiki, dan menyatakan "butuh sync" adalah klaim yang sia-sia.
  Yang menentukan arah kanal yang hidup adalah skrip rilis yang sekarang
  berjalan, bukan tag yang tertinggal. Bandingkan yang live dengan yang live:
  `update.json` di server vs `versionCode` di berkas build.
- **Link rujukan changelog bisa mati** (`[1.0.0]: .../releases/tag/v1.0.0`) kalau
  tag belum ada. Buat tag-nya, atau buang link-nya.
- **Pemeriksa klaim jumlah memberi FALSE POSITIVE pada prosa, bukan cuma pada
  daftar.** `check-release-docs.py` mencocokkan pola `<angka> <kata benda daftar>`
  di mana saja, termasuk di tengah kalimat, lalu menghitung item daftar sesudahnya
  — dan `**tebal**` di awal paragraf ikut dihitung sebagai item daftar. Jadi
  prosa seperti "instrumental dan liriknya tidak ketemu adalah **dua hal**
  berbeda" memicu kegagalan palsu terhadap sub-judul tebal berikutnya, padahal
  tidak ada klaim daftar sama sekali. Kata yang paling mudah memicunya: `hal`,
  `masalah`, `perubahan` (semuanya ada di daftar kata benda). Sebelum
  "memperbaiki" apa pun, periksa apakah yang ditunjuk pemeriksa benar-benar klaim
  jumlah: hitung item daftarnya secara manual dan lihat baris yang dilaporkan.
  Kalau itu prosa, perbaikan termurah adalah mengganti kata bendanya ("dua hal
  berbeda" -> "dua keadaan berbeda") — bukan mengubah struktur dokumen atau
  memaksa daftarnya jadi dua item.

## Verifikasi

`scripts/check-release-docs.py` memeriksa: versi di file build vs heading
CHANGELOG teratas, klaim jumlah vs panjang daftar di bawahnya, link internal
README yang menunjuk file tidak ada, dan link tag changelog (dengan `--repo`,
lewat `gh`).

```bash
python3 scripts/check-release-docs.py \
  --readme README.md --changelog CHANGELOG.md \
  --version-file app/build.gradle.kts --repo OWNER/REPO
```

Untuk bahasa dan gaya penulisan, muat juga skill `anti-ai-slop-writing`.

## Bahasa Indonesia

Daftar kata terlarang di `anti-ai-slop-writing` berbahasa Inggris, jadi **tidak
akan menyala pada teks Indonesia** meski bentuk slop-nya persis sama. Yang paling
sering lolos dan sudah terbukti dikritik user:

- **Metafora identitas kosong** — mengklaim penting alih-alih menjelaskan
  perilaku: "warga kelas satu", "ujung tombak", "tulang punggung", "first-class
  citizen". Ganti dengan apa yang benar-benar dilakukan app.
- **Pola "bukan X, melainkan Y"** — "bukan tempelan belakangan", "bukan sekadar
  X", "tak hanya X tapi juga Y". Sebutkan Y langsung tanpa menegasikan X.
- **Kata pengisi:** "lebih dari sekadar", "pada akhirnya", "di era digital ini",
  "mari kita telusuri", "solusi menyeluruh", "tanpa hambatan", "mulus".

Em dash juga tetap berlaku di teks Indonesia: maksimal 1 per 500 kata. Pemisah
kolom di tabel spesifikasi bukan prosa, jadi tidak dihitung.

## Audit sebelum serah

Sebelum menyerahkan README/changelog panjang, jalankan pemeriksaan yang bisa
dihitung. Em dash yang tersebar di banyak baris mudah terlewat, dan klaim jumlah
("tujuh perbaikan") terasa benar saat ditulis.

**Scope audit em dash ke blok yang baru Anda tulis, bukan seluruh berkas.**
CHANGELOG lama memang berisi em dash dari rilis sebelumnya (histori, di luar
scope). `grep -c '—' CHANGELOG.md` karena itu SELALU mengembalikan angka bukan-nol
bahkan ketika pekerjaan Anda bersih, dan itu menggoda untuk "memperbaiki" teks
yang sudah dirilis. Ambil hanya blok versi teratas:

```bash
# em dash di blok versi teratas saja (harus 0)
awk '/^## \[/{n++} n==1' CHANGELOG.md | grep -c '—'
# atau, kalau tahu heading berikutnya:
awk '/^## \[0\.9\.0\]/,/^## \[0\.8\.0\]/' CHANGELOG.md | grep -c '—'
```

Untuk string yang menghadap user, scope-nya berkas resource saja, bukan seluruh
repo (kode komentar sengaja memakai em dash dan bukan temuan):

```bash
printf 'kata: %s  em dash: %s\n' "$(wc -w < README.md)" "$(grep -o '—' README.md | wc -l)"
grep -n '—' app/src/main/res/values/strings.xml    # harus nihil
grep -nEio '\b(delve|tapestry|seamless|robust|leverage|elevate|warga kelas satu|tak hanya|lebih dari sekadar|pada akhirnya)\b' README.md CHANGELOG.md
```

Hit palsu diabaikan (mis. `Elevated` sebagai nama variabel warna). Lalu hitung
ulang tiap klaim jumlah terhadap panjang daftarnya. Yang tidak bisa diaudit skrip:
isi yang hanya penulisnya tahu, dan kejujuran soal apa yang belum jalan.

**Teks panjang yang baru ditulis bisa memunculkan karakter asing dan kata
yang menempel — dan tidak ada pemeriksaan sintaks yang menangkapnya.** Dua
kegagalan berbeda bentuk dengan satu sebab yang sama: di sambungan saat
mengarang, sesekali keluar satu karakter dari aksara lain di dalam prosa yang
selainnya benar, atau dua kata menyatu tanpa spasi. Keduanya lolos JSON lint,
render Markdown, dan review diff, karena diff menampilkan baris yang
"terlihat benar" sementara mata sudah mengira bacaan itu benar juga. Yang rusak
hanya terlihat kalau karakternya disaring. Ini bukan soal disiplin membaca —
scan blok yang baru ditulis, sama seperti em dash di atas:

```bash
# karakter dari script lain + kata yang menempel (huruf kecil->Besar)
python3 - <<'PY'
import re, pathlib
sec = pathlib.Path('CHANGELOG.md').read_text()
sec = sec[sec.index('## ['):]                      # blok versi teratas saja
# Aksara non-Latin di dalam prosa yang seharusnya Indonesia/Inggris.
print('script lain :', re.findall(r'[\u3000-\u9fff\uff00-\uffef]', sec) or 'nihil')
# Dua kata menyatu tanpa spasi pada jahitan kalimat. Abaikan identifier
# camelCase yang sah (versionName, applicationId) — itu nama field API, bukan
# prosa, jadi skewer-nya hanya boleh menandai kata yang benar-benar rusak.
identifiers = {'versionName','applicationId','versionCode','fileName'}
joins = [m for m in re.findall(r'[a-z]{2,}[A-Z][a-z]{2,}', sec) if m not in identifiers]
print('kata nempel :', joins or 'nihil')
PY
```

Segera setelah `git add`, jalankan scan yang sama atas `git diff --cached`, bukan
atas berkas di disk — byte yang akan terkirim adalah byte yang ter-stage.

