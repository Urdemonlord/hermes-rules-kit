---
name: android-audio-effects
description: "Use when adding equalizer or audio effects to a player."
---

# Audio effects di Android player

## Kapan skill ini dipakai

Menambahkan atau memperbaiki fitur yang menyentuh `android.media.audiofx`:
equalizer, bass boost, normalisasi loudness, reverb, virtualizer, limiter.

Bukan untuk: pemutaran itu sendiri (silent playback, antrean, URI) — itu
skill Media3 terpisah.

## Jebakan utama: efek melekat pada `audioSessionId`, bukan pada player

`Equalizer`, `BassBoost`, `LoudnessEnhancer` dibangun dengan
`(priority, audioSessionId)`. Mereka menempel pada **sesi audio**, bukan pada
objek `ExoPlayer`. ExoPlayer membuat sesi baru setiap kali service dibangun
ulang — dan service dibangun ulang tiap app di-kill, atau tiap kali OS
melepaskan abusive foreground service.

**Gejala kalau lupa:** efek berfungsi di sesi pertama app dijalankan, lalu
diam-diam mati setelah app di-kill dan dibuka lagi. Tidak ada error.

Pasang dari listener, bukan sekali di `onCreate`:

```kotlin
exo.addListener(object : Player.Listener {
    override fun onAudioSessionIdChanged(audioSessionId: Int) {
        audioEffects.attach(audioSessionId)   // lepas efek lama, pasang yang baru
    }
})
// di onDestroy — lepas efek SEBELUM player.release()
audioEffects.detach()
```

## Suntikkan ke service, bukan ke UI

Pemutaran berjalan di service saat app tidak terlihat. Kontroler efek harus
`@Singleton` yang disuntik ke **service**; UI hanya menulis ke DataStore, dan
flow yang sama dibaca controller untuk menerapkan efeknya.

Kalau kontroler hidup di scope UI, efek mati begitu layar ditutup — persis
saat user paling butuh mendengarnya, dan tanpa pesan apa pun.

## Satu kelas untuk semua efek

Semua efek butuh session id yang sama dan semuanya harus dilepas bareng.
Satu efek yang lupa di-`release()` menahan native resource yang tidak akan
kembali.

## Jangan buat objek efek di komposabel

`Equalizer` adalah resource native yang harus di-`release()`. Membacanya di
`onComposition` atau langsung di dalam komposabel = leak per frame.

Baca kemampuan perangkat **sekali**, simpan di ViewModel sebagai state:
jumlah band, frekuensi tiap band, rentang level.

## "Belum diketahui" ≠ "tidak didukung"

Sebelum ada `audioSessionId`, `Equalizer(0, sessionId)` belum bisa dibuat, jadi
hasil baca kemampuan kosong. Kosong berarti **belum diketahui**.

Kalau keduanya disamakan, user yang belum pernah memutar lagu membuka
pengaturan dan melihat "tidak didukung di perangkat ini" padahal HP-nya jelas
punya equalizer. User menyimpulkan fiturnya rusak.

Pisahkan di state:

```kotlin
data class EqUiState(
    val isAvailable: Boolean,   // efek benar-benar gagal dibuat
    val isProbed: Boolean,      // capability sudah pernah dibaca
)
```

Dan baca ulang capability saat layar dibuka (`LaunchedEffect(Unit) { probe() }`),
bukan hanya di constructor ViewModel.

**Dua tempat yang diam-diam mengembalikan bug ini keadaannya semula:**

1. **Bail-out probe harus mengecek `isProbed`, bukan band kosong.**

   ```kotlin
   // SALAH: perangkat yang benar-benar tanpa EQ juga membalas bands kosong,
   // jadi perangkat itu akan selalu menampilkan "belum bisa dicek" dan
   // tidak pernah sampai ke "tidak didukung".
   if (fresh.frequenciesHz.isEmpty()) return
   // BENAR: yang belum dicek != yang sudah dicek dan tidak mendukung
   if (!fresh.isProbed) return
   ```

2. **Dua string harus berbeda.** Kalau teks "belum bisa dicek" dan "tidak
   didukung" masih satu string yang sama, pemisahan di model tidak terlihat
   ke user dan seluruh perbaikannya sia-sia. Pesan untuk kondisi "belum
   dicek" menyebut penyebab dan apa yang harus dilakukan user ("putar lagu
   sebentar, lalu buka kembali"), bukan menyatakan perangkatnya incapable.

Tiga kondisi di `when` (bukan dua): `isAvailable && bands.isNotEmpty()` →
konten; `!isProbed` → butuh playback; sisanya → tidak didukung. Ambil kondisi
konten lebih dulu, kalau tidak `isAvailable = false` menutupi `isProbed` dan
cabang kedua tidak pernah tercapai.

Tes yang mengunci: dua keadaan itu harus **tidak sama** satu sama lain.
```kotlin
assertFalse(sebelumAdaSesi == tidakMendukung)  // isProbed satu-satunya pembeda
```

## Screenshot pengguna: cari cabang mana yang merender string itu

Saat user mengirim screenshot berisi satu pesan ("Equalizer tidak tersedia di
perangkat ini"), pesan itu adalah bukti primer — jangan mulai dari dokumen
fitur atau dari daftar yang "seharusnya ada". Mulailah dari **string itu
persis**:

```bash
grep -rn '<potongan teks yang persis di screenshot>' app/src/main/
```

Kalau hasilnya **lebih dari satu cabang** yang merender string sama, itu
adalah tandanya, bukan kebetulan. Dua kondisi berbeda yang jatuh ke teks
identik selalu berarti state yang memikulnya ikut berubah jadi satu nilai —
dan perbaikannya di state, bukan di teks.

Dengan begitu "fitur ini belum ada isinya" (yang salah, dan menggoda) tidak
pernah jadi diagnosa yang bekerja.

## KDoc yang sudah benar + tipe yang tidak punya tempat = field yang hilang

Variasi dari bug yang sama, dan lebih halus: ViewModel-nya **sudah
mendokumentasikan aturannya dengan benar**, kalimat demi kalimat — "isAvailable
berarti efeknya benar-benar gagal dibuat, bukan belum ada sesi audio".

Kalau komentar seperti itu ada tapi kode tetap salah, komentarnya bukan
petunjuk untuk diperbaiki: itu **spesifikasi field yang belum ada**. Model
tidak punya tempat untuk menyimpan pembeda itu, jadi nilai akhirnya jatuh ke
satu nilai untuk dua situasi. Tambahkan field di **layer yang membaca**
(controller, tempat peristiwa diketahui terjadi), lalu bawa naik lewat state.
Flag yang ditambahkan di ViewModel tidak memb-edakan apa pun: kedua sumber
sudah terlanjur berubah jadi satu nilai, jadi menandai ulang di sana sia-sia.

Cek cepat saat KDoc dan kode bertentangan: cari kata "bukan" di KDoc state —
penentunya hampir selalu state yang salah, bukan komentarnya.

## Pull yang menyangkut file yang sama: cek dulu, jangan langsung fast-forward

Feature yang sedang dikerjakan bisa saja ditulis ulang orang lain di remote —
rewrite yang **melandari di atas commit kamu**, bukan branch yang berdiri sendiri.
Gejalanya saat pull: commit remote menyentuh file yang barusan kamu edit, dan
`git diff --stat` menunjukkan ratusan baris berubah di file yang menurutmu baru
saja kamu selesaikan.

Tiga pemeriksaan, dalam urutan ini:

```bash
git status -sb                 # "behind N" = ada commit remote
git log --oneline HEAD..origin/main
git diff --stat HEAD origin/main
```

Lalu dua grep untuk membuktikan apakah itu rewrite di atas commit kamu atau
karya yang benar-benar terpisah:

```bash
# 1. Apakah commit remote memakai field yang KAMU tambahkan?
git show <remote-sha>:<file> | grep -n '<field-yang-kamu-tambahkan>'
# 2. Apakah test milikmu masih ada di sana?
git show <remote-sha>:<test-file> | grep -c '<symbol-di-testmu>'
```

Kalau remote punya field itu dan test-nya masih hidup, commit itu melandari di
atas commit kamu — rewrite, bukan branch paralel. Aman di-fast-forward, tapi
langkah berikutnya adalah **baca ulang**, bukan pull lagi: perubahan sebesar itu
di file yang sama wajib ditinjau sebelum kamu membangun di atasnya.

Kalau remote tidak punya field kamu dan test-nya hilang, itu branch yang benar
benar paralel — dan `git pull` tanpa rebase akan menghasilkan conflict yang
jauh lebih mahal daripada inspeksi manual.

Satu jebakan tambahan: `git pull` yang sukses **tidak** berarti kamu menyetujui
rewrite-nya. Ia hanya berarti tree-nya bisa disatukan. Dan rewrite yang berhasil
dibaca bukan berarti sudah benar — periksa apa yang berubah secara semantik,
bukan cuma apakah file-nya masih punya simbol yang kamu cari.

## Simpan milibel, bukan indeks slider

`Equalizer.getBandLevelRange()` melaporkan rentang **berbeda per OEM** —
sering `-1500..1500` milibel di satu perangkat, `-1200..1200` di lain.
Menyimpan indeks posisi slider, atau dB yang dihitung dari asumsi rentang
tetap, membuat angka yang sama berarti gain berbeda di perangkat berbeda.

Simpan milibel — satuannya sama di mana pun. Slider hanya memetakan milibel ke
`0f..1f` untuk tampilan.

`min`/`max` rentang ikut dibawa di state UI, bukan di-hardcode di komposabel:
nilai di luar rentang yang dilaporkan perangkat ditolak `setBandLevel` dengan
`IllegalArgumentException`.

## Panjang daftar yang disimpan tidak sama dengan jumlah band perangkat

Efek di perangkat selalu punya N band. Daftar gain yang disimpan boleh lebih
pendek dari N — dan sering begitu. Yang salah adalah mengirim **hanya**
band yang ada di daftar:

```kotlin
// SALAH: band yang tidak ada di daftar tidak pernah disentuh, jadi level lama
// di perangkat UTUH. Tombol "Setel ulang" (yang mengosongkan daftar) berarti
// "tidak ada band yang dikirim" — yaitu tidak terjadi apa-apa.
s.bandGains.forEachIndexed { band, level -> eq.setBandLevel(band.toShort(), level) }

// BENAR: satu nilai untuk SETIAP band perangkat, netral kalau tidak tersimpan.
s.levelsForDevice(bandCount, minMillibels, maxMillibels).forEachIndexed { ... }
```

Gejalanya tidak mencolok: EQ tetap jalan, slider tetap bergerak, tapi tombol
reset melakukan nothing, dan band yang pernah disentuh masih berbunyi seperti
dulu padahal UI bilang sudah datar. Reset yang tidak mengembalikan suara ke
datar lebih buruk dari tidak ada tombol reset — user mempercayai tampilan.

Turunkan ke fungsi pure yang **panjang hasilnya = jumlah band perangkat**,
bukan jumlah entri yang tersimpan. Sekalian betulkan rentang yang terbalik di
sisi fungsi: `min`/`max` datang dari perangkat dan tidak dijamin rapi, jadi
pakai `minOf`/`maxOf` sebelum `coerceIn`.

Tesnya: fungsi murni, jadi easy — assert panjang hasil == `bandCount`, assert
band tanpa nilai tersimpan keluar netral, assert input terbalik tetap
menghasilkan length yang benar dan tidak melempar.

## Frekuensi band juga dari perangkat

Xiaomi dan Samsung membagi spektrum jadi band berbeda. Label hardcode
("60 Hz / 1 kHz / 14 kHz") salah di perangkat yang tidak mengindahinya.

## Persistensi: string, bukan stringSet

Band gain adalah **list berurutan**. `stringSetPreferencesKey` tidak
menyimpan urutan, dan urutan band itu makna — "50 Hz = -300, 200 Hz = +600"
harus tetap berarti hal yang sama setelah app ditutup.

Simpan satu string angka dipisah koma (`"-300,600,0"`), parse dengan
`mapNotNull { it.trim().toIntOrNull() }`.

Jumlah band bisa berbeda antar perangkat, jadi daftar gain **boleh lebih
pendek atau lebih panjang** dari jumlah band perangkat. Band yang tidak ada
diabaikan; band yang belum punya nilai memakai netral.

## Ikon Material di Compose: extension property, satu per satu

`Icons.Filled.GraphicEq` gagal resolve **meskipun** ikonnya ada di
`material-icons-extended` dan artefaknya sudah jadi dependency. Compose
Material Icons tidak punya wildcard: `import ...icons.Icons` tidak membawa
ikon apa pun, dan setiap ikon butuh import sendiri
(`androidx.compose.material.icons.filled.<Name>`, atau `.automirrored.filled.<Name>`
untuk yang ikut mirror).

Sebelum mengejar dependency, buktikan simbolnya memang ada:

```bash
unzip -l material-icons-extended-*.jar | grep -i graphiceq
javap -p androidx/compose/material/icons/filled/GraphicEqKt.class
```

`GraphicEqKt.class` ada + properti `getGraphicEq` artinya satu-satunya
defeknya import. Ini adalah kegagalan CI pertama yang paling sering muncul
di file baru — dan mustahil terlihat di diff.

## Bungkus setiap panggilan efek; satu error tidak boleh fatally seluruhnya

`setBandLevel`, `setStrength`, dan `setTargetGain` bisa melempar di ROM yang
menolak level tertentu **di tengah rentang yang mereka laporkan sendiri**.
Penjepitan ke `bandLevelRange` tidak menjamin aman.

```kotlin
runCatching { eq.setBandLevel(idx.toShort(), clamped) }
    .onFailure { Log.w(TAG, "Band $idx ditolak: ${it.message}") }
```

Tiga hal yang perlu dijaga sekaligus: capture `Throwable` (bukan hanya
`Exception`) di setiap jalur yang bisa melempar; jangan gagalkan seluruh
operasi hanya karena satu band ditolak; dan jangan
menganggap nilai yang diterima perangkat selalu sama dengan yang diminta —
`LoudnessEnhancer` memakai nilai yang lebih rendah **tanpa melempar** kalau
argumennya melewati batas, jadi batasnya dijepit di sisi sendiri, bukan
dibaca dari perangkat.

## Jangan tulis helper yang tidak ada yang memakainya

`defaultBandGains()`, `decibelsToMillibels()`, `ASSUMED_BAND_COUNT`, dan
`isEqAvailable` semuanya lahir bersama fitur ini dan **tidak pernah
dipanggil siapa pun**. Keduanya tidak menambah dokumentasi, hanya membuat
pembaca mencari ke mana helper itu dipakai.

Aturan yang lebih luas: nama konstanta yang menjelaskan conditionsnya
(`FALLBACK_MIN_GAIN_MILLIBELS`, bukan `MIN_BAND_GAIN_MILLIBELS`).Save the
nilai fallback sebagai konstanta yang dibaca dari file yang sama, jangan
ditulis ulang sebagai literal di test — dua angka yang sama di dua file
bisa berbeda makna tanpa siapa pun sadar.

## Scan karakter asing sebelum commit

Komentar dan string dalam repo ini ditulis dalam Bahasa Indonesia. Menulis
banyak teks panjang berulang kali menghasilkan fragmen karakter CJK/Cyrillic
yang tersisip di tengah kalimat — kompilasi lolos, test lolos, review
situsasi. Sekali terlihat di test yang gagal CI, sekali lagi di komentar
yang menghasilkan teks asing, dan sekali lagi di badan PR.

Jalankan scan **setiap kali menulis file panjang**, bukan sekali di akhir
sesi: koreksinya selalu jauh lebih murah di detik yang sama. Dan jalankan
terpisah untuk pesan commit — itu bukan file, jadi scan file tidak pernah
menangkapnya.

**Pakai rentang karakter literal, bukan `\x{...}`.** Bentuk `[\x{AC00}-\x{D7AF}]`
ditolak grep sebagai "Invalid range end" (dan `search_files` gagal sama),
padahal konvensi yang sudah dipakai skill ini bekerja. Karakter literalnya
memang terlihat aneh di sumber, tapi itulah biayanya — ia jalan.

```bash
python3 -c "
import re,sys
pat=re.compile(r'[　-鿿가-힯Ѐ-ӿ]')
for f in sys.argv[1:]:
    t=open(f,encoding='utf-8').read()
    h=[(i,l.strip()[:60]) for i,l in enumerate(t.split(chr(10)),1) if pat.search(l)]
    if h: print(f); [print(' ',x) for x in h]
" <changed files>
```

Kosong = aman. Untuk commit message, sisipkan teksnya sebagai argumen
ketiga ke pola yang sama, atau tempel ke file lalu scan — jangan
mempercayai mata.

## Setelan pemutaran yang diterima ExoPlayer langsung: collector tunggal, tanpa runBlocking

Fitur yang bukan `AudioEffect` tapi punya bentuk sama — hanya flag di
`ExoPlayer` (contoh: `skipSilenceEnabled`). Untuk ini **jangan** pakai
`Builder.setSkipSilenceEnabled` + `runBlocking` untuk membaca preferensi
sebelum build. API runtime-nya ada (`ExoPlayer.skipSilenceEnabled` bisa
diubah kapan saja), dan DataStore memancarkan nilai terkini sebagai emisi
pertama.

Jadi satu collector menutup nilai awal **dan** perubahan:

```kotlin
private val settingsScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

settingsScope.launch {
    settings.skipSilenceFlow().collectLatest { enabled ->
        runCatching { exo.skipSilenceEnabled = enabled }
            .onFailure { Log.e(TAG, "Gagal: ${it.message}", it) }
    }
}
```

Dua jalur (tunggu blocking untuk nilai awal + collector untuk perubahan)
justru lebih buruk: lebih panjang, dan membuka celah di mana setelan
dilewati.

**Batalkan scope DULUAN di `onDestroy`, sebelum `player.release()`.** Kalau
tidak, DataStore bisa memancarkan perubahan tepat setelah player dilepas
dan menulis ke ExoPlayer yang sudah dibebaskan:

```kotlin
override fun onDestroy() {
    settingsScope.cancel()      // sebelum release
    audioEffects.detach()
    player?.release()
}
```

Capture referensi player **non-null** yang sudah ada (`exo`), bukan
`player?` — kalau `player` masih null saat collector mulai, setelan
pertama hilang tanpa jejak.

Default untuk fitur yang mengubah apa yang user dengar adalah `false`:
menyalakan diam-diam mengubah output audio, jadi harus dipilih, bukan
muncul sendiri.

**Jangan_gate switch ini berdasarkan versi OS tanpa bukti.** Dugaan "fitur
ini butuh Android 7.0+" terdengar masuk akal dan terbukti salah: tidak ada
`@RequiresApi`, dan tidak ada `Build.VERSION` di seluruh rantai — ini DSP
murni. Gate berdasarkan API level yang tidak ada hanya mematikan fitur yang
memang jalan, dan penghilangan itu menyusul sebagai "peningkatan".

Verifikasi dengan dua grep sebelum menulis gate:

```bash
javap -v -p <Class>.class | grep -A6 '<methodName>' | grep -iE 'RequiresApi|SdkInt'
javap -c -p <Class>.class | grep -iE 'SdkInt|Build|VERSION'
```

Kosong keduanya = tidak ada gate = switch boleh nyala di semua perangkat.
Test yang menjaga ketiadaan gate ini berguna: kalau Media3 suatu saat
menambahkannya, ada yang ikut tahu.

**Test untuk setelan seperti ini: pakai JAR yang dipakai build, bukan
dokumentasi.** Dumping API publik lengkap dulu, lalu assertion hanya boleh
mengutip dari daftar itu — `javap` tidak menampilkan method yang diwarisi,
jadi nama yang "tidak ada di output" belum berarti tidak ada (dan
miripnya, nama yang mirip belum berarti ada). Ancestor-nya juga bisa berada
di artifact lain (`media3-common` vs `media3-exoplayer`), jadi cek kedua
jar sebelum menyimpulkan method tidak ada. Jalur relatif ke sumber untuk
test yang membaca berkas mengikuti konvensi project yang sudah hijau —
`grep -rn 'File("' app/src/test/` lebih cepat daripada menebak di mana
Gradle menaruh working directory.

## Rilis: jangan poll run lama, dan jangan buka PR di akhir

Dua jebakan operasional yang muncul berulang saatPompa lalu rilis. Keduanya
bukan soal kode — keduanya membuat CI yang benar dilaporkan sebagai yang salah.

**Push ke branch fitur tidak selalu memicu CI.** Kalau trigger workflow hanya
`push: [main]` + `pull_request: [main]`, tidak ada run sama sekali setelah
push ke branch. `gh run list` mengembalikan nol baris, lalu loop polling
berputar sampai batas waktu tanpa pernah ada yang gagal. Cek trigger dulu:

```bash
grep -n -A6 '^on:' .github/workflows/*.yml
```

Kalau hanya `main`, PR bukan formalitas — itu satu-satunya pemicu.

**Kunci polling ke SHA commit.** `--limit 1` mengembalikan run pertama yang
cocok; pada branch yang sudah pernah dipakai itu run **lama**. Hasilnya nyata:
poll melaporkan `failure` untuk run yang selesai 30 menit lalu, padahal run
baru masih `in_progress`. Enam menit terbuang tanpa satu pun perubahan kode.

```bash
SHA=$(git rev-parse --short HEAD)
RUN=$(gh run list --branch <branch> --limit 3 \
  --json databaseId,headSha,status \
  -q ".[] | select(.headSha | startswith(\"$SHA\")) | .databaseId")
[ -n "$RUN" ] || sleep 10   # belum ada run = belum trigger, bukan gagal
```

Bentuknya sama dengan aturan "jangan percaya nama, kuncikan pada identitas
yang unik" di bagianatas skill ini.

## Bukti batas: yang tidak bisa dibuktikan tanpa perangkat

`compile` + `lint` + `test` hanya membuktikan kode benar secara statis.
Tidak ada satu pun yang membuktikan:
- `setBandLevel` benar-benar mengubah suara
- gain di luar rentang perangkat tidak melempar
- efek tetap nyala setelah app di-background lalu di-kill sistem

Sebutkan batas ini di closeout, dan berikan langkah test manual yang
konkret. Untuk equalizer, minimal: putar lagu dulu → baru buka pengaturan
(capability hanya ada setelah ada sesi audio) → geser band → dengar
perubahan → kill app → buka lagi → pastikan pengaturan masih tersimpan
dan efek masih aktif.