---
name: media3-session-uri
description: "Use when Android/Media3 playback misbehaves. Covers silent playback, spurious errors that appear though playback works, a song playing twice, and YouTube stream 403."
---

# Media3: URI hilang antara controller dan session

## Gejala

- Lagu muncul di UI, mini player, dan metadata (judul/artis) benar.
- Menekan play tidak menghasilkan suara **dan tidak ada error apa pun**.
- Terjadi hanya saat playback dipicu lewat `MediaController` ke
  `MediaSessionService`/`MediaLibraryService` (arsitektur background playback),
  bukan saat ExoPlayer dipakai langsung.

## Akar masalah

`MediaItem` yang dikirim `MediaController` ke `MediaSession` melewati binder,
**tidak membawa `MediaItem.localConfiguration`** — Media3 sengaja membuangnya
karena objek itu tidak aman diserialisasi lintas proses. URI audio ada di
`localConfiguration`, jadi ExoPlayer di sisi service menerima item tanpa URI.

Dokumentasi resmi `MediaSession.Callback.onAddMediaItems`:

> the requested media items don't have a `MediaItem.LocalConfiguration` (for
> example, a URI) and need to be updated to make them playable by the underlying
> Player

`MediaItem.requestMetadata` **ikut** terkirim (terverifikasi lewat bytecode:
`MediaItem.toBundle()` menyertakan `FIELD_REQUEST_METADATA`; `localConfiguration`
tidak). Jadi `requestMetadata` adalah satu-satunya jalur yang bisa membawa URI.

## Perbaikan

Tulis URI di DUA tempat — ini bukan duplikasi, keduanya dipakai di sisi berbeda:

```kotlin
// 1) Saat membangun MediaItem (sisi controller)
builder.setUri(parsed)                       // localConfiguration — proses sama
builder.setRequestMetadata(
    MediaItem.RequestMetadata.Builder()
        .setMediaUri(parsed)                 // ikut terkirim lintas proses
        .build()
)
```

```kotlin
// 2) Di service, sebelum item diserahkan ke ExoPlayer
override fun onAddMediaItems(
    mediaSession: MediaSession,
    controller: MediaSession.ControllerInfo,
    mediaItems: List<MediaItem>,
): ListenableFuture<List<MediaItem>> =
    Futures.immediateFuture(mediaItems.map { it.withRestoredUri() })

fun MediaItem.withRestoredUri(): MediaItem {
    if (localConfiguration?.uri != null) return this
    val restored = requestMetadata.mediaUri ?: return this
    return buildUpon().setUri(restored).build()
}
```

## Aturan pendamping

- **Jangan telan kegagalan dengan `runCatching{}.getOrNull()`.** Koneksi
  `MediaController` yang gagal dan `Player.Listener.onPlayerError` yang tidak
  dipermukaan menghasilkan gejala identik dengan bug URI: senyap tanpa pesan.
  Teruskan keduanya ke state UI (`errorMessage`) supaya bisa dilaporkan user.
- **Pesan error di UI, bukan hanya logcat.** Kalau perangkat uji tidak bisa
  diambil logcat-nya, kegagalan yang hanya masuk logcat = kegagalan yang tidak
  pernah terlihat.
- **Keystore debug harus tetap dan ikut repo.** Tanpa itu, setiap build CI
  memakai kunci acak baru dan APK tidak bisa dipasang sebagai update di atas APK
  sebelumnya (user dipaksa uninstall). Verifikasi dengan
  `apksigner verify --print-certs` pada APK lama vs baru, dan bandingkan dengan
  `keytool -list -v -keystore debug.keystore`.
- **`mipmap-anydpi-v26` bukan kesalahan.** Rename ke `mipmap-anydpi` merusak
  resource linking pada minSdk 26; `-v26` adalah standar Android Studio.

## Jebakan ketiga: Room menolak migrasi `ADD COLUMN ... DEFAULT NULL`

Menulis `ALTER TABLE x ADD COLUMN y TEXT DEFAULT NULL` membuat `PRAGMA table_info`
melaporkan default berupa **string `'NULL'`**, sedangkan Room mengharapkan default
kosong untuk kolom nullable. Room menolak migrasi saat **runtime** dengan
"Migration didn't properly handle" — build tetap hijau, jadi bug baru muncul di
perangkat user. Tulis `ADD COLUMN y TEXT` tanpa `DEFAULT`.

Cara memvalidasi tanpa emulator: bangun DB versi lama dari `app/schemas/*.json`
dengan `sqlite3`, jalankan SQL migrasi, lalu bandingkan `PRAGMA table_info` dan
`PRAGMA index_list` dengan skema versi baru — normalisasi default `None`/`''`/`'NULL'`
seperti `TableInfo.normalizeDefaultValue`.

## Jebakan keempat: `OpenDocumentTree` bawaan tidak minta izin persisten

`ActivityResultContracts.OpenDocumentTree` hanya mengirim `ACTION_OPEN_DOCUMENT_TREE`
tanpa `FLAG_GRANT_PERSISTABLE_URI_PERMISSION`. Di sebagian perangkat,
`takePersistableUriPermission` lalu melempar `SecurityException: No persistable
permission grants found`. Gejalanya menyesatkan: folder bisa dipindai sekarang,
tapi lagunya mati setelah app ditutup. Pakai kontrak turunan yang menambahkan
`FLAG_GRANT_READ_URI_PERMISSION or FLAG_GRANT_PERSISTABLE_URI_PERMISSION`, dan
verifikasi hasilnya lewat `persistedUriPermissions` — jangan andalkan "tidak ada
exception".

## Jebakan kelima: pemindaian gagal ≠ folder kosong (risiko hapus data)

Saat prune membandingkan "yang ada di storage" dengan "yang ada di DB", pemindaian
yang gagal (kartu SD belum ter-mount, izin dicabut, provider error) mengembalikan
daflar kosong — dan prune akan menghapus SELURUH lagu folder itu, termasuk
keanggotaan playlist (FK CASCADE) dan statistik putar. Kembalikan flag
`isComplete` terpisah dari daftar hasil, dan hanya menghapus saat pemindaian lengkap.

## Jebakan keenam: `@OptIn` yang ter-resolve ke `kotlin.OptIn`

Menulis `@OptIn(UnstableApi::class)` tanpa import membuat Kotlin memakai
`kotlin.OptIn` bawaan — compile **tetap hijau**, tapi lint Android gagal:

```
UnsafeOptInUsageError: This declaration is opt-in and its usage should be marked
with @androidx.media3.common.util.UnstableApi or @OptIn(markerClass = ...)
```

Lint `UnsafeOptInUsageError` default-nya **fatal** (bukan warning), jadi build
berhenti di `lintDebug` walau `assembleDebug` sendiri sudah bisa menghasilkan APK.
Selalu tambahkan `import androidx.annotation.OptIn` di setiap file yang memakai
`@OptIn(UnstableApi::class)`. Cara cepat menemukan file yang belum: cari
`@OptIn(UnstableApi` lalu pastikan tiap file itu punya `import androidx.annotation.OptIn`.

## Jebakan ketujuh: URL audio stream tidak boleh disimpan di database

URL audio YouTube membawa parameter kedaluwarsa (biasanya ~6 jam). Menyimpannya di
kolom `uri` berarti lagu yang ditambahkan hari ini mati diputar besok, dan user
akan mengira app-nya rusak. Simpan URI penanda berskema sendiri
(mis. `blossomstream://audio/<id>`), lalu tukar jadi URL asli lewat
`ResolvingDataSource.Factory(base) { dataSpec -> ... }` tepat sebelum ExoPlayer
meminta data. Dua konsekuensi yang wajib ditangani:

- **Cache URL di memori dengan TTL pendek (mis. 5 menit).** ExoPlayer membuka
  ulang `DataSource` setiap kali user seek; tanpa cache, tiap geseran jadi satu
  permintaan jaringan penuh dan lagu tersendat. Jangan tulis cache ke disk.
- **Skema tak dikenal aman.** `DefaultMediaSourceFactory` memilih sumber
  berdasarkan skema SEBELUM `DataSource` jalan; skema tak dikenal jatuh ke
  `ProgressiveMediaSource`, yang memang yang diinginkan untuk URL audio langsung.

Terakhir, pastikan `onPlayerError` menampilkan `error.cause?.message` / `error.message`
lebih dulu, bukan `error.errorCodeName` saja. Kode seperti
`ERROR_CODE_IO_UNSPECIFIED` menyembunyikan pesan asli dari resolver (mis. "YouTube
meminta verifikasi bukan bot") — satu-satunya petunjuk yang berguna bagi user.

## Jebakan: `onConnect` yang menolak controller → "service connection failed"

**Gejala:** scan/library jalan, tapi setiap play gagal dengan pesan koneksi
(tidak ada suara sama sekali). Bukan senyap — ada error eksplisit dari kode
sendiri, mis. `SERVICE_CONNECTION_FAILED`.

**Jangan pernah** menulis `onConnect` yang mengembalikan
`ConnectionResult.reject()` berdasarkan `ControllerInfo.isTrusted`. Itu mematikan
controller dari app sendiri:

- `MediaSessionManagerImplBase.isTrustedForMediaControl` (Media3) hanya
  mengembalikan true bila controller punya izin sistem
  (`MEDIA_CONTENT_CONTROL`, `STATUS_BAR_SERVICE`), ber-uid 1000, atau
  notification listener. **App biasa tidak punya satu pun → `isTrusted=false`.**
- `MediaSessionStub.connect()` hanya melindungi controller trusted (komentarnya:
  *"Don't reject connection for trusted app"*). Untuk controller tidak trusted,
  `reject()` = koneksi dibuang total → `MediaController` gagal → play mustahil.

Pola yang benar (sama seperti Metrolist & ArchiveTune): **jangan override
`onConnect` sama sekali**; biarkan `super.onConnect()` menerima dengan perintah
default. Untuk membungkam lint `ExportedService`, pakai
`tools:ignore="ExportedService"` di `<service>` — bukan guard runtime.

**Intent-filter service wajib tiga action** (seperti dua app produksi di atas):

```xml
<action android:name="androidx.media3.session.MediaSessionService" />
<action android:name="androidx.media3.session.MediaLibraryService" />
<action android:name="android.media.browse.MediaBrowserService" />
```

Catatan: `MediaControllerImplBase` membangun intent bind secara *explicit*
(`new Intent(SERVICE_INTERFACE)` + `setClassName(...)`), jadi action manifest
bukan penyebab utama kegagalan — tapi tetap harus lengkap agar binding lewat
jalur lain (mis. MediaBrowser/Android Auto) ikut bekerja.

## Jebakan kedelapan: aksi yang butuh controller hilang tanpa jejak

`MediaController` dibangun secara asinkron. Selama sambungan belum jadi,
`controller` bernilai `null`, dan menulis `controller?.addMediaItems(...)` berarti
aksi itu **diam-diam tidak terjadi**: tidak ada exception, tidak ada error di UI,
lagu hanya tidak masuk antrean. Gejalanya mudah disalahkan ke hal lain karena
playback lain (yang lewat `playQueue`) tetap bekerja normal.

Kasus yang paling sering kena: user membuka app, lalu langsung menekan "Tambah ke
antrean" sebelum ada lagu yang diputar. Tidak ada satu pun lagu diputar, jadi
sambungan tidak pernah diminta, dan `controller` masih `null`.

Perbaikan: satu jalur untuk semua aksi yang butuh controller.

```kotlin
private val pendingActions = mutableListOf<() -> Unit>()

private fun runWhenReady(action: () -> Unit) {
    if (controller != null) action()
    else {
        pendingActions.add(action)
        connect()   // jangan hanya menunggu; coba sambung sekarang
    }
}
```

Jalankan daftarnya saat sambungan berhasil, dan **kosongkan daftar sebelum
mengiterasi** — aksi di dalamnya bisa memanggil `runWhenReady` lagi, dan itu akan
menambah ke daftar yang sedang diiterasi:

```kotlin
if (controller != null && pendingActions.isNotEmpty()) {
    val queued = pendingActions.toList()
    pendingActions.clear()
    queued.forEach { it() }
}
```

**Penampungnya harus daftar, bukan satu slot.** Dengan satu slot, dua aksi
berturut-turut sebelum sambungan jadi akan saling menimpa — user menambahkan dua
lagu ke antrean, hanya yang terakhir masuk. Karena urutan menentukan isi antrean,
menimpa bukan pilihan. Aturan ini berlaku juga untuk aksi lain yang
memodifikasi antrean (`playNext`, `addMediaItems`, `seekTo`).

Cara menemukan sisa kasus ini: cari semua `controller?.` di kelas koneksi. Setiap
pemakaian yang bukan sekadar membaca state adalah kandidat bug yang sama.

## Jebakan kesembilan: `catch (e: Exception)` menelan pembatalan coroutine

**Gejala:** pesan galat muncul di layar padahal operasinya sebenarnya berhasil —
paling sering saat user mengetik cepat di kolom pencarian, atau saat lagu dilewati
sebelum URL-nya selesai diambil.

**Akar masalah:** di Kotlin/JVM, `CancellationException` adalah subclass
`RuntimeException`, jadi **juga subclass `Exception`**. Buktikan dengan probe
sekali jalan kalau ragu:

```java
System.out.println(new java.util.concurrent.CancellationException("x")
    instanceof Exception);   // true
```

Setiap `try { ... } catch (e: Exception)` yang membungkus panggilan `suspend`
menangkap pembatalan juga, lalu memperlakukannya sebagai kegagalan sungguhan.
Pesan bawaannya ("Job was cancelled") lalu tampil ke user sebagai "kegagalan
dari server".

Ini muncul di beberapa lapisan sekaligus, dan **satu perbaikan saja tidak cukup**:

| Lapisan | Yang terjadi kalau tidak diperbaiki |
|---|---|
| ViewModel yang membatalkan job lama | pembatalan jadi pesan galat di UI |
| Fungsi pembungkus exception (`fun Exception.toXException()`) | pembatalan berubah jadi exception domain, sehingga cabang `catch (CancellationException)` di atasnya **tidak lagi mengenalinya** |
| `ResolvingDataSource`/resolver yang membungkus jadi `IOException` | melewati lagu memunculkan galat pemutaran |
| Pemeriksa pembaruan / panggilan jaringan lain | pembatalan tampil sebagai "tidak bisa menghubungi server" |

**Aturan:** setiap `catch (e: Exception)` yang membungkus operasi `suspend` wajib
punya cabang pembatalan **di atasnya**, dan melemparnya ulang apa adanya:

```kotlin
} catch (e: CancellationException) {
    throw e                 // pembatalan bukan kegagalan
} catch (e: Exception) {
    // penanganan kegagalan sungguhan
}
```

Untuk fungsi pembungkus exception, jangan kembalikan nilai — **lempar ulang**:

```kotlin
private fun Exception.toStreamException(): StreamException = when (this) {
    is CancellationException -> throw this
    is StreamException -> this
    else -> StreamException("Gagal mengambil data: $this", this)
}
```

Cara menemukan semua tempatnya: `grep -rn 'catch (e: Exception)'` di seluruh
modul, lalu periksa satu per satu apakah blok `try`-nya berisi operasi `suspend`.
Kalau ya, itu kandidat bug yang sama.

**Pola pikir yang lebih umum:** pembatalan dan kegagalan adalah dua hal berbeda.
Melempar ulang pembatalan bukan sekadar menghilangkan pesan galat — ia membuat
seluruh mekanisme pembatalan coroutine bekerja sebagaimana mestinya.

## Jebakan kesepuluh: satu lagu terputar dua kali karena antrean disusun setelah data berubah

**Gejala:** menekan satu lagu memutar lagu itu dua kali berturut-turut, bukan
sekali. Muncul terutama untuk lagu yang BELUM ada di library (mis. hasil YouTube).

**Akar masalah:** urutan operasi. Kalau alurnya "simpan lagu ke database, lalu
susun antrean dari lagu itu + daftar library", maka saat antrean disusun, lagu
yang baru disimpan **sudah ikut terpancar** ke daftar library (Room/Flow
memancarkan perubahan segera). Antreannya jadi `[lagu, lagu, ...]`.

```kotlin
// SALAH
saveSong(song) { saved ->
    player.play(saved, listOf(saved) + librarySongs)   // saved ada di DUA-duanya
}
```

**Perbaikan dua lapis**, dan keduanya perlu:

1. Di pemanggil, saring lagu yang sedang dipilih dari daftar:
   `listOf(saved) + librarySongs.filterNot { it.id == saved.id }`
2. Di lapisan playback, buang duplikat id dari antrean mana pun — ini menutup
   **seluruh kelas bug**, bukan hanya satu pemanggil:
   ```kotlin
   val unique = queue.distinctBy { it.id }   // pertahankan kemunculan pertama
   ```

**Jebakan terkait yang gejalanya sama:** `setMediaItems(...)` selalu memulai dari
detik nol. Menekan lagu yang SEDANG diputar dari antrean yang sama akan
me-restart lagunya, dan itu terasa seperti "keplay dua kali". Tambahkan penjaga
sebelum memasang antrean:

```kotlin
val sameQueue = mediaItemCount == items.size &&
    currentMediaItemIndex == index &&
    currentMediaItem?.mediaId == items[index].mediaId
if (sameQueue) { if (!isPlaying) play(); return@apply }
```

Penjaga ini hanya boleh berlaku kalau antreannya benar-benar identik. Kalau lagu
yang sama ditekan dari daftar lain (mis. hasil pencarian), antreannya memang beda
dan harus dipasang ulang.

**Untuk pencatatan riwayat putar**, dedupe terpisah juga perlu: Media3 bisa
memanggil `onMediaItemTransition` dua kali untuk lagu yang sama dalam hitungan
milidetik. Simpan `lastMarkedId` + `lastMarkedAtMs`, dan lewati pencatatan kalau
id-nya sama dalam jendela ~1,5 detik.

## Jebakan kesebelas: YouTube membalas 403 walau URL audio masih berlaku

**Gejala:** sebagian lagu YouTube gagal diputar dengan 403 dari `googlevideo.com`,
tapi tidak semua — lagu lain jalan, dan lagu yang sama bisa berhasil di lain
waktu. Muncul-hilang, jadi mudah disalahkan ke jaringan.

**Akar masalah:** YouTube mengikat URL `videoplayback` ke **klien yang memintanya**.
UA saat MENGEKSTRAK URL dan UA saat MEMUTAR audio harus sama. Kalau beda,
YouTube membalas 403 walaupun URL-nya belum kedaluwarsa.

Yang membuat ini sulit ditemukan: **NewPipe Extractor sengaja TIDAK menyetel
`User-Agent` sendiri.** NewPipe menambahkannya di lapisan `Downloader`
(`DownloaderImpl.USER_AGENT`). Jadi `Downloader` buatan sendiri yang lupa
menambahkannya membuat permintaan ekstraksi berjalan TANPA UA sama sekali,
sementara sisi pemutaran memakai UA lain. Dua UA berbeda = 403.

**Cara memverifikasi nilai UA yang benar (dan jebakan pencariannya):**

```bash
# SALAH — ini false negative, bikin Anda mengira UA-nya karangan:
unzip -p NewPipeExtractor-*.jar '.../YoutubeParsingHelper.class' | strings | grep Firefox
# Nihil, karena DownloaderImpl ada di APP NewPipe, bukan di library extractor.

# BENAR — ambil dari sumber NewPipe (app), bukan dari JAR extractor:
# https://github.com/TeamNewPipe/NewPipe → DownloaderImpl.java → USER_AGENT
```

**Perbaikan (empat bagian, semuanya perlu):**

1. **Satu konstanta UA dipakai kedua sisi** (ekstraksi + pemutaran). Dua literal
   terpisah akan melenceng cepat atau lambat. Di sisi pemutaran nilainya
   di-*inline* compiler, jadi di dex cari string UA-nya, bukan nama konstantanya.
2. **`Downloader` bridge wajib menambahkan UA**, dengan urutan seperti NewPipe:
   pasang default dulu, lalu `removeHeader` + `addHeader` untuk header yang
   disusun extractor supaya header ekstraktor bisa menimpanya.
3. **Pasang UA per-request di `DataSpec`, JANGAN di `DefaultHttpDataSource.Factory`.**
   `DefaultHttpDataSource.makeConnection` menulis UA dari factory **SETELAH**
   header dari `DataSpec`, jadi UA di factory menimpa UA per-request. Akibatnya
   UA khusus per-URL (mis. visionOS) tidak akan pernah terpakai. Ini terverifikasi
   dari bytecode Media3, bukan dugaan.
4. **Ulangi 403 sekali dengan URL baru.** URL audio bisa dicabut lebih cepat dari
   masa berlakunya; resolve ulang video yang sama biasanya langsung berhasil.
   Hanya ulang 403 — 404/410 berarti videonya memang hilang, dan mengulangnya
   cuma memperlambat pesan galat yang sama. Pasang pembungkus `DataSource` DI
   ANTARA resolver dan sumber aslinya, dan taruh videoId di `DataSpec.key` supaya
   pembungkus tahu video mana yang harus dicari ulang.

**Header lain yang NewPipe selalu kirim dan sering terlupa:** `TE: trailers`
(dikirim untuk SEMUA URL, di luar blok header web), plus `Origin`/`Referer`/
`Sec-Fetch-*` **hanya** untuk URL dari klien WEB. Mengirim header web untuk URL
klien Android/iOS tidak ada gunanya.

**Tidak bisa diuji tanpa perangkat** — bukti yang tersedia hanya dari kode sumber
NewPipe/Media3, bukan dari YouTube yang benar-benar membalas. Verifikasi yang bisa
dilakukan: pastikan string UA dan kelas pembungkus retry benar-benar ada di dex
APK, dan `getVisionOsUserAgent(null)` tidak NPE (null → `Localization.DEFAULT`).

## Verifikasi

Tidak bisa diuji tanpa emulator/perangkat. Verifikasi yang tersedia:

1. `./gradlew :app:lintDebug :app:assembleDebug` → 0 error.
2. `aapt2 dump xmltree --file AndroidManifest.xml app-debug.apk` → pastikan
   service punya tiga action di atas.
3. `apksigner verify --print-certs app-debug.apk` → bandingkan SHA-256 dengan
   APK sebelumnya; harus identik supaya update bisa menimpa tanpa uninstall.
4. `javap -cp <media3-common-*.jar> androidx.media3.common.MediaItem` untuk
   memastikan `buildUpon()`, `requestMetadata`, dan
   `MediaItem$RequestMetadata$Builder.setMediaUri` ada di versi yang dipakai.
5. Pastikan `onAddMediaItems` benar-benar ter-override di service (bukan default
   yang mengembalikan `UnsupportedOperationException`).
6. **Cek isi dex setelah perubahan besar** — cara termurah memastikan kode baru
   benar-benar terpaket, tanpa perangkat:

   ```bash
   unzip -q app-debug.apk 'classes*.dex' && \
     strings -a classes*.dex | grep -oE 'namaKelas|namaMetode' | sort -u
   ```

   **Jebakan saat memakai cara ini:** fungsi `@Composable` tingkat-atas dan
   fungsi top-level lain **tidak** menghasilkan kelas bernama fungsinya. Fungsi
   `fun UpdateDialog()` di `UpdateDialog.kt` menjadi kelas `UpdateDialogKt`, dan
   `PlaylistPickerDialog()` di dalam `SongMenu.kt` menjadi `SongMenuKt`. Mencari
   `Lcom/.../UpdateDialog;` tidak menemukan apa pun meski kodenya ada. Cari nama
   file dengan akhiran `Kt`, atau cari nama metode/fungsi di dalamnya. Salah
   membaca hasil ini bisa membuat Anda mengira kode hilang padahal tidak.
7. **Build lokal bersifat inkremental; artifact CI tidak.** Isi `build/` bergantung
   pada build sebelumnya, jadi APK hasil build lokal dan APK dari CI bisa berbeda
   isi walau ukurannya sama persis. Kalau yang di-deploy adalah APK, deploy
   artifact CI supaya isinya benar-benar berasal dari commit yang di-tag. Untuk
   memastikan perbedaannya, bandingkan `sha256sum` per `classes*.dex`, bukan
   ukuran APK.
