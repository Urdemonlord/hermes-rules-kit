---
name: android-home-screen-widget
description: Use when adding or fixing an Android AppWidget player.
category: android
---

# Widget pemutar di layar utama (AppWidgetProvider)

## Kapan skill ini dipakai

Menambah widget `RemoteViews` — atau memperbaiki widget yang sudah ada tapi
tidak pernah ikut berubah, atau widget yang muncul kosong. Untuk alur compile-nya
lihat `android-ci-only-feature-development`.

## AppWidgetProvider bukan objek yang hidup

Ini yang paling sering tidak disadari, dan hampir jadi sebagian besar bug widget.

**Android membuat instance `AppWidgetProvider` BARU untuk setiap broadcast.**
`onUpdate`, `onReceive`, `onAppWidgetOptionsChanged` — semuanya instance
tersendiri. Konsekuensi:

- Field di provider (`private var controller`, `scope`, listener) **tidak pernah
  bertahan** antar-broadcast. Menyimpan controller berarti menyambung ulang ke
  service setiap kali widget digambar.
- Listener yang didaftarkan di dalam provider **menumpuk**, karena tidak pernah
  ada yang melepasnya.
- Pola benar: sambung → kerjakan → lepas.

```kotlin
private fun denganController(lakukan: (MediaController) -> Unit) {
    scope.launch {
        val c = try {
            MediaController.Builder(appContext, token).buildAsync()
                .get(5, TimeUnit.SECONDS)
        } catch (e: Exception) {
            Log.w(TAG, "Widget gagal menyambung ke PlaybackService", e)
            return@launch
        }
        // Lepas di finally: controller yang tertinggal akan menahan
        // PlaybackService tetap hidup tanpa ada yang memutar.
        try {
            lakukan(c)
        } finally {
            c.release()
        }
    }
}
```

Konsekuensi lanjutan: kalau pola "sambung sekali, simpan" yang lama sudah
terpasang, `onDisabled` biasanya jadi kembar dari `onUpdate` — ia ada hanya
untuk melepas field yang tidak akan bertahan. Hapus, jangan rapikan.

## Widget tidak pernah digambar ulang sendiri

`android:updatePeriodMillis="0"` berarti Android tidak akan memanggil `onUpdate`
lagi. Widget yang menggambar sekali saat diletakkan akan **selalu** menampilkan
keadaan saat itu — bukan keadaan sekarang.

Jadi kalau widget butuh mencerminkan player, **pemicu pembaruan harus datang dari
luar**. Pilih yang sudah ada sebelum menambah apa pun:

1. **Broadcast dari listener player** — kalau app sudah punya
   `PlaybackConnection`/`Player.Listener`, itu pemicu paling murah. Nol
   scheduler, nol service baru.
2. `WorkManager` periodik — kalau tidak ada listener, dan widget boleh
   toleransi delay.
3. `AlarmManager` — hanya kalau update harus presisi; biasanya berlebihan.

```kotlin
// Di listener player, bukan di provider:
private fun segarkanWidget() {
    val manager = AppWidgetManager.getInstance(context) ?: return
    val ids = manager.getAppWidgetIds(ComponentName(context, WidgetPemutarProvider::class.java))
    if (ids.isEmpty()) return          // tanpa widget, jangan broadcast

    context.sendBroadcast(
        Intent(context, WidgetPemutarProvider::class.java).apply {
            action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
            putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
        },
    )
}
```

**`notifyAppWidgetViewDataChanged` bukan untuk ini.** Itu hanya berlaku pada
widget koleksi (`RemoteViewsService` + `ListenableFuture`). Widget yang
menggambar `RemoteViews` biasa harus diberi tahu lewat broadcast
`ACTION_APPWIDGET_UPDATE`, supaya `onUpdate` benar-benar dijalankan.

## Urutan gambar vs sambung

Gambar **di dalam** scope controller. Kalau `onUpdate` menggambar dulu lalu
menyambung, `currentMediaItem` masih null dan hasilnya selalu string cadangan —
widget terlihat "tidak ada lagu" walau ada lagu yang sedang diputar.

```kotlin
override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
    appContext = context.applicationContext
    denganController { c -> ids.forEach { gambarTentang(context, manager, it, c) } }
}
```

## `RemoteViews` gagal diam-diam

Dua kelas kegagalan, dan keduanya **tidak melempar exception**:

- **ID layout atau drawable salah** → widget tidak muncul sama sekali, tanpa
  error di log. Tidak ada test JVM yang menangkap ini karena tidak ada yang
  merender.
- **Widget tidak pernah dibangun ulang** → muncul dengan isi usang selamanya.

Artinya: `RemoteViews` yang sudah lolos compile dan test tetap bisa gagal total di
perangkat. Verifikasi di user surface adalah satu-satunya bukti. Kalau widget
tidak muncul, jangan lapor sebagai bug logika — itu lebih mungkin ID resource,
dan perlu `adb logcat`.

## Keputusan yang layak diekstrak dan diuji

`RemoteViews` hanya bisa dibangun di dalam proses app, jadi tidak bisa diuji dari
JVM. Yang **bisa** diekstrak: keputusan murni di dalamnya.

Contoh yang layak diekstrak, karena kalau salah **tidak melempar exception**:

- ikon tombol utama ikut atau tidak ikut `isPlaying` → tertukar = user melihat
  "pause" padahal sedang main
- pemetaan aksi ke perintah (play/pause, next, prev) → tertukar = tombol next
  jadi previous, tetap "berfungsi"

Bentuknya: objek kecil dengan fungsi murni, I/O tetap di provider. Ini satu-satunya
cara menguji `RemoteViews` tanpa mocking library dan tanpa menambah dependency.

## Pitfalls

- **Jangan simpan `MediaController` di field provider.** Lihat bagian atas.
- **Jangan andalkan `updatePeriodMillis`.** Nilai default pun terlalu jarang untuk
  mencerminkan player.
- **`RemoteViews` tidak punya `setText` pada elemen yang sudah ada.** Mengubah
  isi = membangun ulang seluruh `RemoteViews` lalu `updateAppWidget` lagi.
- **Coil/Glide tidak bisa dipakai.** `RemoteViews` menerima `Bitmap` yang sudah
  jadi, bukan URL. Decode manual di provider.
- **Teks diambil lewat `getString`, bukan `stringResource`.** Widget tidak punya
  `Context` Compose.
- **`Intent.action` nullable** dan smart cast tidak berlaku ke property — hoist ke
  `val` lokal lebih dulu.
- **Nama action wajib berawalan package** (`com.meowlabs.player.widget.MAIN`),
  kalau tidak intent-nya bisa dibalas app lain yang kebetulan memakai nama sama.