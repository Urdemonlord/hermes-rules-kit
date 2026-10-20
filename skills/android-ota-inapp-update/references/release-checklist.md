# Checklist rilis OTA Android

Urutannya penting: setiap langkah membuktikan langkah sebelumnya. Jangan
lompat ke `./scripts/release.sh` karena artifact "kelihatan ada".

## Urutan yang tidak boleh dibalik: bump versi SEBELUM menunggu CI

Artifact yang dipublish harus berasal dari run yang commit-nya **sudah
memuat** bump versi. Kalau bump dilakukan setelah menunggu CI, run yang
baru saja kamu tonton membangun APK versi **lama** — `versionCode` di APK
akan cocok dengan `build.gradle.kts` pada saat itu, bukan dengan versi
yang hendak kamu deploy. Deploy-nya succeeds dan user tidak pernah
melihat hotfix.

Urutannya: bump `versionCode`/`versionName` + entri changelog → commit →
push → **baru** kunci run ke SHA itu dan tunggu. Jangan pernah menunggu
CI atas commit yang belum dipush versinya, lalu memutuskan "ya sudah
cukup" dan melanjutkan ke commit versi terpisah.

Kalau terlanjur menunggu run yang salah: jangan pakai APK-nya. Push
commit versi, konfirmasi run baru muncul, tunggu yang itu. Dua run
berjalan bersamaan itu boros runner tapi lebih murah daripada
menerbitkan APK yang isinya bukan hotfix yang dimaksud.

**Gejalanya fisik: run hijau, APK terpasang, tidak ada error — tapi
hotfix-nya tidak ada di dalamnya.** Karena itu begitu run yang kamu
tonton selesai hijau, jangan buru-buru lanjut; cocokkan dulu
`versionCode` di APK dengan `versionName` yang hendak kamu deploy. Dua
nilai itu harus sama persis. Kalau APK-nya satu versi lebih lama,
artifact itu bukan milik rilis ini — dan tidak ada yang akan menangkapnya,
karena semua gate sudah hijau.

Urutan yang tidak pernah salah: bump versi + changelog → commit → push →
kunci run ke SHA itu → tunggu → download APK → cocokkan `versionCode`
dengan `build.gradle.kts` → `release.sh`.

## 1. Sumber perubahan terverifikasi

```bash
git rev-parse --show-toplevel        # pastikan di repo yang benar
git status --short
git checkout main && git pull
git log --oneline -1
```

Rilis memakai commit yang sudah **merged dan hijau di `main`**, bukan dari
branch fitur. Kalau PR masih terbuka, artifact-nya bukan yang akan dipakai
user.

## 2. VersionCode naik, versionName berubah

```bash
grep -n 'versionCode\|versionName' app/build.gradle.kts
```

Naikkan `versionCode` di setiap rilis — termasuk hotfix. `versionName` untuk
manusia dan akan tampil di changelog. **Langkah ini wajib selesai dan
dipush sebelum baris ini turun** — lihat "Urutan yang tidak boleh dibalik".

## 3. Changelog konsisten di semua tempat

Changelog biasanya ada di tiga file yang bisa tidak sinkron:

- `CHANGELOG.md` (markdown)
- `app/src/main/assets/changelog.json` (dipakai app untuk dialog)
- `README.md` (tabel versi terbaru)

`changelog.json` punya invarian yang tidak selalu dicek compile: entri
teratas harus sama dengan `BuildConfig.VERSION_NAME`, tidak ada
`versionName` kosong, tidak ada tanggal format lain dari `YYYY-MM-DD`, tidak
ada tanggal di masa depan, dan urutan tanggal tidak naik ke atas. Validasi
dengan parse JSON, bukan grep — grep tidak membedakan `"2026-13-45"` yang
telah salah bentuk.

**Invarian itu punya test di project yang sudah menerapkannya — jadi ia
menangkap diri sendiri.** Kalau test sudah hijau tapi entri teratas tertinggal
di versi sebelumnya, `VERSION_NAME` naik duluan dan `changelog.json` menyusul.
Naikkan keduanya **dalam batch yang sama**; kalau tidak, 반드시 ada satu run
CI merah di tengah.

Kalau harus menyusul dalam commit terpisah (karena versi baru groundwater-nya
entah kapan), commit susulan itu adalah **rilis kedua yang belum pernah
diverifikasi** — pastikan CI hijau lagi untuknya, jangan tidur pada hijau
commit sebelumnya.

```bash
python3 -c "
import json,datetime,re
d=json.load(open('app/src/main/assets/changelog.json'))
today=datetime.date.today()
dates=[e['publishedAt'] for e in d if e.get('publishedAt')]
checks={
 'blank name':[e['versionName'] for e in d if not e.get('versionName','').strip()],
 'bad date':[e['versionName'] for e in d if e.get('publishedAt') and not re.match(r'\d{4}-\d{2}-\d{2}',e['publishedAt'])],
 'future':[(e['versionName'],e['publishedAt']) for e in d if e.get('publishedAt') and datetime.date.fromisoformat(e['publishedAt'])>today],
 'not descending':[(a,b) for a,b in zip(dates,dates[1:]) if a<b],
}
[print(' ',k,v or 'OK') for k,v in checks.items()]
"
```

## 4. CI hijau penuh — dan test benar-benar jalan

```bash
gh run list --branch main --limit 1
gh run view <RUN_ID> --json conclusion,jobs -q '.jobs[] | "\(.name)\t\(.conclusion)"'
```

**Kunci run ke SHA, jangan percaya "run terakhir".** `--limit 1` mengembalikan
run pertama yang cocok; kalau branch-nya pernah dipakai, itu bisa run lama —
`gh run view` lalu melaporkan `failure` untuk run yang sudah selesai, sementara
run baru masih berjalan. Polling sampai run yang salah wastes waktu dan,
kalauCI hijau di run lama, bisa melepas APK dari commit yang salah.

```bash
SHA=$(git rev-parse --short HEAD)
RUN=$(gh run list --branch main --limit 3 \
  --json databaseId,headSha -q ".[] | select(.headSha | startswith(\"$SHA\")) | .databaseId")
```

SHA yang dicari adalah milik `main` **setelah merge** (hasil squash), bukan
SHA branch fitur sebelum squash. Kalau `RUN` kosong, belum ada run — tunggu,
jangan lanjut ke langkah 5 dan pakai APK dari rilis sebelumnya.

Yang wajib hijau: `Lint`, `Unit test`, `Build debug APK`, `Build release APK`.
Compile saja tidak cukup.

**Workflow bisa saja tidak jalan di push ke branch fitur.** Kalau trigger-nya
hanya `push: [main]` + `pull_request: [main]`, tidak ada run sama sekali
setelah push ke branch — dan PR adalah satu-satunya pemicunya:

```bash
grep -n -A6 '^on:' .github/workflows/*.yml
```

Tidak ada run setelah push ke branch fitur bukan CI lambat: itu PR belum
dibuka.

**Buktikan jumlah test.** Centang hijau tidak berarti ada test yang
dieksekusi — dan fitur baru bisa lolos dengan nol test khusus:

```bash
gh run download <RUN_ID> -n <nama-artifact-laporan-test> -D /tmp/report-fresh
# parse jumlah test + kegagalan per modul dari HTML laporan
```

Direktori tujuan **harus baru setiap kali**. Download kedua ke direktori
yang sama gagal dengan `error extracting zip archive: ... file exists` —
pesan yang tidak menyebut download sama sekali, jadi mudah dibaca sebagai
masalah ekstraksi zip, bukan sebagai "sudah pernah diunduh".

Artifact laporan test berupa **HTML, bukan XML**. `TEST-*.xml` tidak ikut,
jadi `glob('**/TEST-*.xml')` mengembalikan nol suite padahal ratusan test
berjalan — dan nol suite itu terbaca "tidak ada test". Ambil angkanya dari
`index.html` (`<div class="counter">`: tests, failures, ignored, duration)
atau dari daftar kelas di direktori `classes/`.

Bentuk perintahnya `gh run download <RUN_ID> -n <name> -D <dir>`. Saat run-id
diberikan, **repo tidak boleh ikut sebagai argumen** (`-R owner/repo` atau
`-A` membuat `gh` menolak seluruh perintah). `gh run download --help` adalah
sumber kebenaran kalau versinya menolak; jangan menebak nama flag-nya.

Untuk hitung dari laporan HTML, halaman per-kelas lebih akurat daripada
`index.html` — file per kelas menyimpan `<td class="success">` per test, jadi
bisa dipakai membuktikan test fitur benar-benar dieksekusi dan bukan cuma ada
di source:

```bash
python3 -c "
import re,glob
for f in glob.glob('/tmp/report/**/classes/*.html',recursive=True):
    t=open(f,encoding='utf-8',errors='replace').read()
    print(f.split('/')[-1], len(re.findall(r'<td class=\"success\">',t)))
"
```

Kalau jumlah test tidak bertambah dibanding rilis sebelumnya padahal ada
fitur baru, itu bukan kabar baik — itu fitur yang belum diuji.

## 4b. Kalau CI gagal, baca error-nya sebelum memperbaikinya

Satu run gagal = satu sumber kebenaran. Ambil log yang gagal, bukan menebak:

```bash
gh run view <RUN_ID> --log-failed | grep -E 'e: file|error:|Dagger\[' \
  | sed 's|.*<repo-dir>/||' | sort -u
```

Kelompokkan per file dan per jenis. Yang sering terlewat: **run bisa gagal
di tahap yang lebih akhir dari run sebelumnya**, jadi error dari run lama sudah
tidak berlaku. Compile error → DI error → test failure → semua hijau adalah
urutan normal, bukan empat siklus terpisah yang perlu diulang dari nol.

## 5. Unduh artifact dari CI yang benar

Nama artifact **tidak selalu sama dengan yang Anda kira**. Kalau
`gh run download` bilang tidak ada, ambil nama aslinya dari API daripada
menebak:

```bash
gh api repos/<owner>/<repo>/actions/runs/<RUN_ID>/artifacts \
  -q '.artifacts[].name'
```

Unduh, lalu verifikasi isi APK. Kalau `aapt2`/`apkanalyzer` tidak ada di
mesin build — dan di VPS ramping memang tidak perlu ada — APK itu zip, jadi
berkas yang kamu pedulikan bisa dibaca langsung:

```bash
aapt2 dump badging app-release.apk | head -1
# package: name='...' versionCode='42' versionName='0.28.1'
sha256sum app-release.apk

# tanpa Android SDK:
python3 - <<'PY'
import zipfile, json
z = zipfile.ZipFile('app-release.apk')
n = [x for x in z.namelist() if x.endswith('assets/changelog.json')][0]
print(json.loads(z.read(n).decode())[0]['versionName'])
PY
```

`versionCode` di APK **harus sama** dengan yang di `build.gradle.kts` dan
di `update.json`, dan `changelog.json` di dalam APK harus punya entri
teratas yang sama dengan `versionName`. Kalau berbeda, user tidak akan
pernah melihat update-nya.

`AndroidManifest.xml` di dalam APK adalah biner AXML yang tidak bisa dibaca
`ElementTree`. Untuk manifest, andalkan job `Verify APK` di CI atau
`apkanalyzer` — jangan menebak dari bytes.

## 6. Signature cocok dengan versi sebelumnya

```bash
apksigner verify --print-certs app-release.apk
```

Signer harus identik dengan APK yang sudah terpasang di perangkat user.
Bedanya berarti installer menolak dan user dipaksa uninstall.

## 7. Publish

```bash
./scripts/release.sh <path-apk> "catatan perubahan"
```

Skrip yang baik memverifikasi sendiri (checksum cocok, `update.json` bisa
dibaca, halaman hidup) dan keluar non-zero kalau gagal. Baca keluarannya —
jangan hanya melihat exit code.

**Varian: repo yang punya workflow rilis dipicu tag.** Di sana tag adalah pemicu build, jadi
"tag setelah verifikasi" tidak bisa berlaku harfiah. Konsekuensinya: tag wajib di-push sesudah
`versionName` dan entri changelog untuk versi itu ada (workflow menolak tag yang tidak cocok dengan
`versionName`), dan verifikasi pindah ke sesudah — unduh aset Release, cocokkan `versionCode`,
`versionName`, dan entri teratas `changelog.json`. Yang paling mudah terlewat: GitHub Release
**tidak** menyentuh `update.json`, jadi OTA belum aktif sampai langkah 7 dijalankan. Sebutkan
dua fakta itu terpisah di laporan: "rilis terbit" dan "OTA aktif".

**Tag dibuat setelah verifikasi, bukan sebelumnya.** Kalau proyek punya tag
rilis, periksa blok tag di `release.sh`:

```bash
grep -n 'tag -a\|git tag\|push origin' scripts/release.sh
```

Posisi blok tag harus setelah baris verifikasi checksum. Kalau belum ada,
tambahkan beserta tes penjaganya (lihat SKILL.md "Tes penjaga yang membaca
teks skrip").

**Verifikasi ulang dari luar setelah publish.** Script bisa salah tentang
diri sendiri (checksum dari berkas yang salah, cache, path yang tidak ditulis
sesuai ekspektasi). Satu `curl` ke `update.json` publik dan satu `HEAD` ke
URL APK membuktikan yang benar-benar dilihat user:

```bash
curl -s https://<domain>/update.json          # versionCode/versionName/sha256
curl -sI https://<domain>/<file>.apk | head -4 # HTTP 200 + content-length
```

Bandingkan `content-length` dengan ukuran berkas lokal. Kalau berbeda, yang
dipublish bukan yang diverifikasi checksum-nya.

## 9. Tag harus ada untuk setiap versi — dan kalau tertinggal, jangan ditebak

Jawaban "versi mana yang sudah tayang" harus terbaca dari repo, bukan dari
server. Kalau tag tertinggal banyak:

```bash
# commit yang mendeklarasikan tiap versi, urut naik
for sha in $(git log --reverse --format='%h' -- app/build.gradle.kts); do
  v=$(git show "$sha:app/build.gradle.kts" 2>/dev/null \
      | grep -oP 'versionName\s*=\s*"\K[^"]+' | head -1)
  echo "$v|$sha"
done | awk -F'|' 'NF==2 && $1!=p {print $1" "$2; p=$1}'
```

**Validasi metodenya dulu** dengan membandingkan hasil itu terhadap tag yang
sudah ada. Kalau tag lama cocok persis, metodenya benar; kalau tidak, jangan
lanjut bikin tag.

Setelah membuat tag, verifikasi SEMUA tag (bukan cuma yang baru):

```bash
for t in $(git tag); do
  v=${t#v}; sha=$(git rev-list -n1 $t)
  got=$(git show $sha:app/build.gradle.kts \
        | grep -oP 'versionName\s*=\s*"\K[^"]+' | head -1)
  [ "$got" = "$v" ] || echo "MISMATCH $t -> commitsays $got"
done
```

Nol baris = semua tag jujur. Tag yang menunjuk commit lain lebih buruk dari
tidak ada tag: ia terlihat benar dan diam-diam salah.

## 8. Bukti batas — apa yang SEBENARNYA terbukti

Setelah publish, yang terbukti baru: **manifest bisa dibaca dan mencantumkan
versi baru**. Dialog "Versi X tersedia" di perangkat user membuktikan
tahap discovery saja.

Belum terbukti tanpa perangkat nyata:
- tombol Unduh menyelesaikan unduhan
- dialog installer sistem benar-benar muncul
- signature diterima sehingga APK bisa menimpa
- fitur yang baru ditambahkan benar-benar bekerja

Sebutkan ini di closeout dengan langkah test manual yang konkret, jangan
dibiarkan jadi "silakan cek".