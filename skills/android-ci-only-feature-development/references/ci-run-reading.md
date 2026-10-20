# Membaca hasil run CI

Resep command untuk mengambil bukti dari GitHub Actions, dan jebakan yang
muncul di setiap perintah.

## Filter error jadi satu baris per masalah

Log Gradle mengulang error yang sama untuk setiap variant dan setiap job.
Tanpa filter, satu bug muncul sebagai 12 baris dan menutupi bug kedua.

```bash
gh run view <RUN_ID> --log-failed 2>&1 \
  | grep -E 'e: file|error:|FAILURE' \
  | sed 's|.*<REPO-NAME>/||' \
  | sort -u
```

`sort -u` adalah bagian yang penting: log mengulang pesan identik untuk
`compileDebugKotlin` dan `compileReleaseKotlin`, lalu mengulanginya lagi di job
`Lint` dan job `Unit test`.

Kalau hasilnya kosong padahal run `failure`, kegagalan-nya bukan compile error.
Cari kata lain:

```bash
gh run view <RUN_ID> --log-failed 2>&1 \
  | grep -viE 'deprecat|migrate|node.js|ubuntu-latest|annotations' \
  | tail -25
```

Pola yang muncul: `There were failing tests` berarti problem-nya logika, bukan
syntax — dan artifact laporan test **tidak** ter-upload karena job-nya gagal.
Artifact baru ada di run yang hijau.

## Hitung test yang benar-benar dieksekusi

```bash
rm -rf /tmp/rep
gh run download <RUN_ID> -n <ARTIFACT_NAME> -D /tmp/rep
find /tmp/rep -name index.html
```

Report Gradle HTML punya `div class="counter"` di urutan: tests, failures,
ignored, duration.

```python
import re, glob
for f in glob.glob('/tmp/rep/**/index.html', recursive=True):
    t = open(f, encoding='utf-8', errors='replace').read()
    print(f.split('/')[-4:], re.findall(r'<div class="counter">([^<]+)</div>', t)[:4])
```

Untuk memeriksa test fitur tertentu benar-benar jalan:

```python
import re, glob
for c in glob.glob('/tmp/rep/**/classes/*.html', recursive=True):
    if 'namafitur' in c.lower():
        n = len(re.findall(r'<td class="success">',
                           open(c, encoding='utf-8', errors='replace').read()))
        print(c.split('.')[-2], '->', n, 'lulus')
```

Hitung total `<td class="failures">` + `<td class="skipped">` di semua kelas
untuk memastikan tidak ada yang diam-diam di-skip.

### Jebakan flag `-A`

`gh run download` tidak punya flag `-A`. Ada di halaman help bersama `-n`,
`-p`, dan `-D`, tapi tidak dipakai — memanggilnya membuat gh mencetak help dan
keluar tanpa menjalankan apa pun, yang terlihat seperti "download gagal".
Dengan run-id, `-n <NAME>` saja sudah cukup.

## Membandingkan run ke SHA, bukan ke urutan

`gh run list --limit 1` mengembalikan run **paling baru secara waktu**, yang
belum tentu milik commit HEAD. Setelah push kedua dalam waktu dekat, run lama
bisa masih `in_progress` dan yang baru belum terdaftar.

```bash
gh run list --branch <B> --limit 3 \
  --json databaseId,status,headSha \
  --jq '.[] | (.databaseId|tostring)+"  "+.status+"  "+(.headSha[0:7])'
```

Bandingkan `headSha[0:7]` dengan `git log --oneline -1 --format=%h`. Hanya
run yang SHA-nya cocok yang errornya milik kode kamu.

## Membaca kegagalan test dari nama, bukan traceback

Report HTML tidak terunduh saat job test gagal, jadi traceback lengkap tidak
tersedia. Yang cukup: nama test yang gagal dari log Gradle.

```bash
gh run view <RUN_ID> --log 2>&1 \
  | grep -iE 'FAILED|tests completed' | head
```

`ChangelogParserTest > ... FAILED` diikuti `N tests completed, 1 failed`
memberi dua informasi sekaligus: test mana, dan totalnya. Setelah itu baru
buka file test-nya di repo.

## Monitor yang tidak merusak kernel

`execute_code` punya batas keras ~300 detik. Loop sleep 30 di dalamnya
membunuhnya. Jalankan `gh run watch` sebagai proses background dengan
notifikasi:

```
terminal(background=True, notify=True,
         command="gh run watch <ID> --exit-status --interval 30")
```

Kalau tidak bisa — mis. pemanggilan sedang berlangsung dalam konteks lain —
poll **sekali** per pemeriksaan, jangan loop. Timeout `wait` juga dijepit ke
batas yang lebih kecil dari yang diminta, jadi memperpanjang tidak membantu.

## Membaca gate tanpa menebak

Satu perintah untuk keempat job:

```bash
gh run view <ID> --json jobs \
  --jq '.jobs[] | .name+" -> "+(.conclusion//"running")'
```

Status `skipped` di job build berarti job sebelumnya gagal — itu informasi,
bukan noise. Jangan melaporkannya sebagai "build belum jalan".

## Hitung ulang setiap angka sebelum menyebutnya

Jumlah test, jumlah file, jumlah error, jumlah commit. Angka yang dikira-kira
jadi salah berulang dan merusak credibility seluruh laporan — termasuk
laporan yang bagian selebihnya benar.

## Kuota artifact: kegagalan yang bukan kegagalan kode

Gejalanya di log:

```
Failed to CreateArtifact: Artifact storage quota has been hit.
Unable to upload any new artifacts. Usage is recalculated every 6-12 hours.
```

Ini bukan error compile dan bukan error test. Yang gagal hanya langkah
unggah; `./gradlew test` dan `assembleRelease` di job yang sama sudah
`BUILD SUCCESSFUL`. Tetap baca langkahnya satu per satu sebelum menyimpulkan
apa pun tentang kode.

Sebabnya akumulasi. Setiap push membuat artifact APK (~27 MB untuk debug),
dan `retention-days: 30` menahannya sebulan — ratusan artifact sudah cukup
melewati kuota gratis 500 MB, dan begitu kuota penuh, langkah unggah di
**semua** job gagal sekaligus.

Kuota itu **per akun pemilik repo**, bukan per repo. Repo yang artefaknya nol
bisa merah sementara penyebabnya repo lain. Audit seluruh akun dulu:

```bash
gh repo list <OWNER> --limit 50 --json name --jq '.[].name' | while read -r r; do
  n=$(gh api "repos/<OWNER>/$r/actions/artifacts?per_page=1" --jq '.total_count' 2>/dev/null)
  [ "${n:-0}" != "0" ] && echo "$r: $n artefak"
done
```

Pola yang muncul: satu repo menahan 2,99 GB (64 artefak × ~85 MB) dan repo lain
206 MB, sementara repo yang CI-nya merah menyimpan **nol**. Tidak ada kode yang
salah di repo itu, dan mengubah kodenya hanya membuang satu putaran.

**Jangan memakai hasil hitunganmu untuk membantah pesan kuota.** Kalau total yang
kamu jumlahkan jauh di bawah kuota gratis (mis. ratusan MB) sementara pesannya
tetap keluar, itu bukan bukti pesannya keliru — hitungan GitHub berjalan di
jendela 6–12 jam dan bisa menahan unggahan lebih lama daripada angka yang bisa
kamu lihat. Karena itu yang berubah bukan kodenya: bersihkan sekali dengan ID
eksplisit, lalu tunggu jendela hitung ulang. Menghapus berulang, atau mengubah
workflow karena angkanya tidak cocok, hanya menambah satu run merah lagi.

Hapus dengan **menyisakan build terbaru per nama artifact** — bukan
mengosongkan repo, karena satu build terakhir per tipe masih dipakai untuk
membandingkan:

```bash
gh api "repos/<OWNER>/<REPO>/actions/artifacts?per_page=100" --paginate \
  --jq '.artifacts[]|"\(.id)\t\(.name)\t\(.size_in_bytes)\t\(.created_at)"'
# kelompokkan per name, sisakan created_at terbesar, hapus sisanya satu per satu:
# gh api -X DELETE repos/<OWNER>/<REPO>/actions/artifacts/<id>
```

### Cache: pemakan kuota yang sebenarnya

Menghitung artefak seluruh akun sering berakhir dengan total yang jauh di bawah
kuota (mis. ~118 MB) sementara pesan kuota tetap keluar. Yang belum dihitung
adalah **cache**: `actions/cache` ikut masuk ke penyimpanan Actions, dan cache
Gradle untuk app Android gampang mencapai beberapa GB per repo — satu akun bisa
menahan 11 GB hanya di dua repo. Angka itu yang melewati batas kuota gratis,
bukan APK-nya. Ironinya: repo yang CI-nya merah bisa jadi yang artefaknya nol,
sementara pemakan kuotanya adalah repo yang pipeline-nya sehat.

Angka per repo, satu panggilan per repo, tanpa menarik daftar entrinya:

```bash
gh repo list <OWNER> --limit 100 --json name --jq '.[].name' | while read -r r; do
  gh api "repos/<OWNER>/$r/actions/cache/usage" \
    --jq "\"$r \(.active_caches_count) entri \(.active_caches_size_in_bytes/1048576|floor) MB\"" 2>/dev/null
done
```

**Key cache unik per commit, jadi "sisakan yang terbaru per key" tidak
menghapus apa pun.** Key Gradle memuat hash dependensi, jadi 87 entri bisa
berarti 87 key yang berbeda — skrip penghemat yang mengelompokkan per key akan
melaporkan "hapus 0 entri" pada repo yang justru paling penuh. Yang bekerja
adalah **batas umur**: hapus yang lebih tua dari 2–3 hari.

```bash
cutoff=$(date -u -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)
gh api "repos/<OWNER>/<REPO>/actions/caches?per_page=100" --paginate \
  --jq ".actions_caches[] | select(.created_at < \"$cutoff\") | .id" \
| while read -r id; do
  gh api -X DELETE "repos/<OWNER>/<REPO>/actions/caches/$id" >/dev/null
done
```

Jangan heran kalau `cache/usage` sesudahnya masih melaporkan angka lama — tujuh
puluh entri yang dihapus bisa terlihat sebagai pengurangan dua belas. Itu
jendela hitung ulang yang sama (6–12 jam) seperti pada artefak, jadi verifikasi
yang sah adalah **log run pembersih yang mencetak sisa**, bukan endpoint itu.

Cara yang tidak perlu diulang tiap bulan: `templates/prune-caches.yml`,
workflow terjadwal yang melakukan tepat ini. Dua hal yang membuatnya benar:

- **Berkasnya harus ada di cabang default.** Workflow `schedule` hanya
  dijalankan dari default branch; commit yang mendarat di cabang fitur berarti
  nol run dan nol error yang memberitahu. Kalau commit-nya terlanjur mendarat
  di cabang lain, pindahkan lewat worktree sementara (`git worktree add <dir>
  origin/main --detach`) supaya working tree user tidak tersentuh.
- **Dispatch ke repo milik akun lain butuh token akun itu.** `gh workflow run`
  dengan akun yang bukan pemilik menjawab `HTTP 403: Must have admin rights to
  Repository`. Mengubah workflow di repo akun lain juga berarti push-nya harus
  memakai kredensial akun itu — kalau helper `store` di mesin ini mengembalikan
  token akun lain lebih dulu, push ditolak dengan pesan yang menyebut izin,
  bukan URL.

### Saat kuota penuh, unggahan artifact bukan satu-satunya jalur

**Aset GitHub Release tidak dihitung sebagai penyimpanan artifact.** Workflow
yang dipicu tag bisa membangun APK lalu menempelkannya ke release
(`softprops/action-gh-release` dengan `files:`), dan APK itu diunduh dari
runner mana pun dengan:

```bash
gh release download <tag> -p '*.apk' -D /tmp/dir-baru
```

Itu membuat rilis tetap bisa diterbitkan tanpa menunggu jendela hitung ulang
kuota — dan tanpa memasang `continue-on-error` pada unggahan APK, yang tetap
salah karena artifact memang produk di jalur `gh run download`.

Hitung dan bersihkan:

```bash
# berapa banyak, berapa besar, dan namanya
gh api 'repos/<OWNER>/<REPO>/actions/artifacts?per_page=100&page=1' \
  --jq '.artifacts[] | "\(.id)\t\(.size_in_bytes)\t\(.name)"'
gh api 'repos/<OWNER>/<REPO>/actions/artifacts' --jq '.total_count'

# hapus per halaman: per_page maksimum 100, jadi ulangi sampai total_count 0
for id in $(gh api 'repos/<OWNER>/<REPO>/actions/artifacts?per_page=100&page=1' \
              --jq '.artifacts[].id'); do
  gh api -X DELETE "repos/<OWNER>/<REPO>/actions/artifacts/$id" >/dev/null
done
```

**Menghapus tidak langsung membuka kuota.** Pesan errornya sendiri bilang
*usage is recalculated every 6-12 hours*, jadi rerun yang dijalankan langsung
setelah pembersihan masih merah dengan pesan identik. Jangan mengulang
penghapusan atau mengubah kode karena itu — tunggu jendela hitung ulang, lalu
rerun.

### Cegah di workflow, jangan bersihkan terus

```yaml
      # APK dibuat di SETIAP push dan besar; retensi panjang = kuota habis.
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: <app>-debug-apk
          retention-days: 3          # bukan 30

      # Langkah bantu tidak boleh memerahkan job yang isinya lulus.
      - name: Upload test report
        if: always()
        continue-on-error: true
        uses: actions/upload-artifact@v4
```

`continue-on-error: true` penting bukan cuma supaya rapi: job test yang merah
membuat job build `skipped` lewat `needs:`, jadi satu kegagalan unggah
menutupi **dua** hal sekaligus — hasil test yang lulus, dan build yang
sebenarnya jalan.

**Jangan pasang `continue-on-error` di unggahan APK.** Di sana artifact-nya
adalah produknya: `scripts/release.sh` mengambil APK lewat `gh run download`,
jadi unggah yang gagal memang harus merah. `continue-on-error` hanya untuk
langkah **diagnostik** — laporan test, skema generator — yang isinya bisa
diambil ulang tanpa membatalkan build.
