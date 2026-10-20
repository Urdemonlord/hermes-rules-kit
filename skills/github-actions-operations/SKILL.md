---
name: github-actions-operations
description: "Use when GitHub Actions quota, cache, or artifacts fail."
category: devops
version: 1.0.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [github, actions, ci, quota, cache, artifact]
    related_skills: [android-ci-only-feature-development, vps-autodeploy-pipelines, android-fork-rebrand]
---

# Operasi GitHub Actions

## Kapan dipakai

- Job merah di langkah unggah artefak, terutama `Artifact storage quota has been hit`.
- Build hijau tapi artefak tidak ada; atau sebaliknya, merah padahal build-nya jelas jalan.
- Run `cancelled` padahal tidak ada yang membatalkan.
- Workflow terjadwal tidak pernah muncul di daftar run.

## Aturan yang berlaku di setiap instance

- **Kuota storage akun = artefak + cache.** Pesan errornya menyebut "artifact", tapi cache
  Gradle ikut dihitung. Artefak 0 pun bisa kena.
- **Meter `/actions/cache/usage` bohong selama 6–12 jam.** Pesan errornya sendiri yang bilang
  hitung ulang segitu. Untuk memutuskan, baca daftar `/actions/caches`, bukan meter.
- **Batas umur bukan batas ukuran.** Cache Gradle Android ~90 MB per entri dan key-nya unik per
  commit, jadi jendela 3 hari bisa 3,6 GB. Yang dibatasi harus ukurannya.
- **Hapus pakai ID eksplisit**, sesudah daftar dibaca. Jangan hapus berdasarkan pola nama.
- **Bukti = log workflow, bukan meter.** Setelah membersihkan, dispatch pembersihnya sekali dan
  baca angka `sisa:` di log.

## 1. Diagnosis: ukur dulu, jangan tebak

```bash
# meter: angka lama, jangan dipakai memutuskan
gh api /repos/<owner>/<repo>/actions/cache/usage

# kebenaran: daftar entri
gh api "/repos/<owner>/<repo>/actions/caches?per_page=100" \
  -q '[.actions_caches[].size_in_bytes]|add/1048576|floor'
```

Kuotanya **per akun**, dipakai bersama semua repo — jadi sisir semuanya sebelum menyimpulkan:

```bash
gh repo list <owner> --limit 100 --json name -q '.[].name' | while read -r r; do
  printf '%-32s %s MB\n' "$r" \
    "$(gh api /repos/<owner>/$r/actions/cache/usage -q '.active_caches_size_in_bytes/1048576|floor')"
done
```

Bandingkan dengan kuota paket (gratis: 500 MB untuk artefak + cache sekaligus). Kalau satu repo
sendiri sudah berkali lipat, penyebabnya cache, bukan artefak.

## 2. Bersihkan: simpan yang terbaru sampai batas ukuran

Aturan yang terbukti: **simpan cache terbaru sampai total ≤ batas, hapus sisanya**. Batas dibagi
jumlah repo aktif di akun itu — 400 MB per repo di akun 500 MB dengan dua repo Android berarti
masih menabrak.

`templates/prune-caches.yml` adalah workflow harian siap salin: `workflow_dispatch` + `schedule`,
`permissions: actions: write`, menyortir entri per `created_at` lalu menghapus yang melewati batas,
dan mencetak `sisa:` di akhir. Salin ke `.github/workflows/prune-caches.yml`.

Untuk sekali jalan dari terminal, hapus per ID (jangan per pola nama):

```bash
gh api "/repos/<owner>/<repo>/actions/caches?per_page=100" \
  --jq '.actions_caches[] | "\(.id) \(.size_in_bytes) \(.created_at)"' \
| sort -k3 -r | awk -v cap=$((400*1024*1024)) '{ if (total+$2<=cap) { total+=$2 } else { print $1 } }' \
| while read -r id; do gh api -X DELETE "/repos/<owner>/<repo>/actions/caches/$id"; done
```

## 3. Hentikan treadmill-nya, bukan cuma bersihkan

Pembersih harian kalah cepat dari build yang menulis cache baru tiap push. Matikan penulisannya
di push biasa, sisakan untuk rilis:

```yaml
      - uses: gradle/actions/setup-gradle@v4
        with:
          cache-read-only: ${{ !startsWith(github.ref, 'refs/tags/') }}
```

Pasang di **setiap** langkah setup (lint, test, build debug, build release) dan di workflow rilis —
satu yang terlewat tetap menulis cache. Ekosistem lain: cari sakelar read-only milik setup
action-nya sebelum memutuskan mematikan cache sepenuhnya.

Konsekuensi yang harus disebut: setelah cache lama habis masa pakai, build tidak dapat cache sampai
ada run tag yang menulis lagi. Kalau itu terlalu lambat, izinkan penulisan berkala — jangan diamkan.

## 4. Unggah artefak non-fatal, tapi periksa dulu siapa yang memakainya

`continue-on-error: true` di level **langkah** unggah (di atas `with:`), bukan di level job — job
tetap merah kalau kompilasinya gagal, dan hijau kalau cuma kuota yang menolak.

Sebelum memasangnya, buktikan tidak ada yang mengonsumsi artefak itu:

```bash
grep -rn 'run download\|artifacts' scripts/ .github/workflows/ | head   # ada pemakai?
```

Kalau skrip rilis mengambil artefak (`gh run download -n <nama>`), artefak hilang = jalur rilis
rusak, dan langkah unggah harus tetap fatal. Kalau rilis dijalankan dari berkas hasil build atau dari
aset GitHub Releases, artefak cuma untuk diunduh manusia — aman dibuat non-fatal.

**Jangan percaya komentar di workflow.** Komentar "skrip rilis mengambil APK dari job ini" bisa
bertahan lama setelah skripnya berubah jadi menerima path argumen. Baca skripnya.

## 5. `cancelled` bukan `failure`

`concurrency` + `cancel-in-progress` membatalkan run yang sedang jalan begitu ada push lebih baru ke
ref yang sama. Run lama tidak pernah menyelesaikan build-nya — bukan berarti kodenya salah.

```bash
gh run list -R <owner>/<repo> -L 3 --json databaseId,headSha,status,conclusion \
  -q '.[] | "\(.status) \(.conclusion) \(.headSha[0:7]) \(.databaseId)"'
```

Kalau SHA run terbaru adalah turunan commit yang dibatalkan, build yang menentukan sudah tercakup —
baca hasil run terbaru, jangan menyalahkan kode di run yang cancelled.

## 6. Workflow baru hanya hidup di cabang default

`schedule` dan `workflow_dispatch` hanya ada untuk workflow di cabang default. Berkas yang
ter-commit di cabang fitur tidak muncul di `gh workflow run` (404 / tidak terdaftar). Kalau working
tree user ada di cabang lain, commit ke default tanpa menyentuhnya:

```bash
WT=~/scratch/<repo>-main
git worktree add "$WT" origin/main --detach
cp <berkas> "$WT/<path>"
cd "$WT" && git add "<path>" && git commit -m "..." && git push origin HEAD:main
cd - && git worktree remove --force "$WT"
```

Push ke cabang yang dilindungi bisa lolos lewat bypass admin; output git menulis
`Bypassed rule violations for refs/heads/main`. Sebutkan itu di laporan, jangan disembunyikan.

## 7. Kuir `gh api` yang bikin salah hitung

- `--paginate` mengeluarkan hasil **per halaman**, jadi `--jq` yang menyortir hanya menyortir satu
  halaman. Sortir di shell (`sort -k3 -r`) atas baris gabungan.
- `gh workflow run` butuh token **pemilik** repo: `GH_TOKEN=<token> gh workflow run ...`. Tanpa itu
  jawabannya `403 Must have admin rights`, bukan pesan tentang workflow-nya.
- Hapus selalu per ID hasil daftar; pola nama tidak pernah aman.

## Verifikasi sebelum melapor

1. Dispatch pembersihnya sekali, baca log: entri dihapus + baris `sisa:`.
2. Ukur ulang dari daftar `/actions/caches` (bukan meter) dan sebut angkanya.
3. Untuk run yang tadinya merah, sebut langkah mana yang merah dan mana yang hijau — "merah di
   langkah unggah, build + verifikasi APK hijau" adalah informasi yang berbeda dari "CI merah".

## Jebakan

- **Menyimpulkan dari meter.** Meter masih melaporkan 2 GB setelah cache tinggal 416 MB; memutuskan
  berdasarkan itu membuat pembersihan terlihat gagal padahal berhasil.
- **Batas umur saja.** "Hapus lebih tua dari 3 hari" tidak menurunkan apa pun kalau 3 hari terakhir
  saja sudah melebihi kuota.
- **`if-no-files-found: ignore` bukan penawar kuota.** Langkah unggah tetap gagal di pembuatan
  artefak, sebelum sempat memeriksa berkas.
- **Membuat unggahan non-fatal tanpa memeriksa pemakainya.** Artefak yang dikonsumsi skrip rilis
  berubah dari "gagal keras" jadi "hilang diam-diam".
- **Mengulang re-run berkali-kali.** Kalau pesan errornya bilang hitung ulang tiap 6–12 jam, re-run
  dalam menit yang sama hanya mengulang kegagalan yang sama.
- **Satu repo dibersihkan, akun tetap penuh.** Kuota dipakai bersama; repo lain dengan cache besar
  tetap menahan unggahan repo yang sudah bersih.
- **`gh run view` / `gh release view` memilih repo dari git remote.** Checkout dengan dua remote
  (`origin` + `upstream`, wajib di fork) bikin keduanya menunjuk repo yang salah — 404 menyebut repo
  yang bukan milik user. Pakai `--repo <owner>/<repo>`, atau langsung `gh api repos/<owner>/<repo>/…`
  yang tidak pernah menebak.
