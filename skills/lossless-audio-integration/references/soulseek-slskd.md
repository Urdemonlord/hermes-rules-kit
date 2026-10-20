# Soulseek lewat `slskd` — jalur lossless gratis

`slskd/slskd` — server Soulseek headless dengan REST API, jalan di Docker. Ini satu-satunya jalur
yang memberi FLAC asli tanpa langganan. Dipakai kalau user menolak membayar provider.

## ⚠️ slskd TIDAK bisa mengirimkan isi berkas yang sudah diunduh

Ini membatalkan asumsi yang paling wajar, jadi periksa dulu sebelum merencanakan apa pun.
Endpoint `/api/v0/files/*` **hanya** bisa **mendaftar** (`GET`) dan **menghapus** (`DELETE`)
berkas. Semua respons `application/json`; tidak ada satu pun endpoint yang mengembalikan binary.

Jadi **tidak ada "endpoint unduh HTTP dari slskd"** untuk memindahkan FLAC dari server ke HP.
Verifikasi ulang ini di OpenAPI + `Files/API/FilesController.cs` sebelum menjanjikannya.

Cara memindahkan berkas yang benar-benar bisa (semua menyajikan `~/slskd/downloads/`):

| Cara | Catatan |
|---|---|
| Static file server terpisah | Paling dekat dengan maksud "unduh lewat HTTP". Caddy/nginx/`python -m http.server`, listen HANYA di interface Tailscale, dengan auth |
| SSH/SFTP | Butuh kredensial + library di HP |
| Syncthing | Server dan HP sama-sama jalan |

Pilih bersama user — ini keputusan yang tidak bisa ditebak dari kode.

## Endpoint

Auth: header `X-API-Key`. Base path `/api/v0`.

| Kebutuhan | Endpoint | Catatan |
|---|---|---|
| Mulai cari | `POST /searches` | Body: `searchText`, `searchTimeout`, `responseLimit`, `fileLimit`, `filterResponses`. Hanya **satu** pencarian sekaligus — yang kedua dibalas 429 |
| Status + hasil | `GET /searches/{id}?includeResponses=true` | Poll sampai `state` memuat `Completed` |
| Antre unduh | `POST /transfers/downloads/{username}` | Balas **201** `{Enqueued, Failed}`; body berupa **array** `[{filename, size}]` |
| Kemajuan | `GET /transfers/downloads` | Bersarang: user → directories → files |
| Status koneksi | `GET /application` | `server.isConnected` / `server.isLoggedIn` |
| Daftar berkas | `GET /files/downloads/directories` | Hanya metadata — lihat peringatan di atas |

## Bentuk respons yang mudah salah dibaca

- **`state` berupa STRING, bukan angka.** slskd memasang `JsonStringEnumConverter` global
  (`Program.cs`), jadi enum dikirim sebagai nama. Karena `SearchStates`/`TransferStates` adalah
  flags enum, nilainya bisa gabungan: `"Completed, Cancelled"`, `"Completed, Succeeded"`.
  **Periksa dengan `contains`, jangan `==`.** Memodelkannya sebagai `Int` tidak melempar error —
  ia diam-diam bernilai 0 dan pencarian tampak tak pernah selesai.
- **Status unduhan: periksa kegagalan LEBIH DULU.** Sebuah transfer bisa bertag
  `"Completed, Succeeded, Errored"`. Menganggap `Succeeded` sebagai sukses akan membuat berkas
  rusak terlihat utuh. Flag gagal: `Errored`, `TimedOut`, `Rejected`, `Cancelled`, `Aborted`.
- **Antre unduhan: 201 belum berarti berhasil.** Balasannya `{Enqueued, Failed}` dan `Enqueued`
  bisa kosong. Periksa isinya, jangan hanya kode status.
- **Metadata berkas bisa null.** Banyak peer tidak mengirim `bitDepth`/`sampleRate`. Terima berkas
  tanpa metadata selama ekstensinya benar; tolak hanya kalau metadatanya ADA dan jelas lossy.
- **409 saat belum login Soulseek** adalah kondisi yang pasti dialami setiap user baru. Pesan
  mentah slskd ("The server connection must be connected and logged in...") tidak menuntun —
  ganti dengan pesan yang menjelaskan apa yang harus diisi.

## Menyaring FLAC asli dari yang palsu

Nama berkas di Soulseek tidak bisa dipercaya; sangat umum menemukan `.flac` yang sebenarnya MP3
hasil encode ulang. Saring dengan metadata dari peer:

- Ekstensi lossless: `flac`, `wav`, `aiff`, `aif`, `ape`, `wv`, `alac`.
- Tolak `mp3`, `m4a`, `aac`, `ogg`, `opus`, `wma`, `mpc`. **`m4a` sengaja ditolak** meski bisa
  memuat ALAC: di Soulseek ia hampir selalu AAC, dan melewatkan sesekali ALAC asli lebih murah
  daripada mengunduh AAC ratusan megabita.
- Tolak kalau `sampleRate < 44100` atau `bitDepth < 16` — bukti kuat hasil transcode.
- Saat memilih di antara kandidat, **bit depth harus benar-benar lebih menentukan daripada sample
  rate**. Penjumlahan biasa gagal di sini: `bitDepth×10⁶ + sampleRate×100` membuat 16/192k
  mengalahkan 24/44.1k. Pakai bobot berlapis dengan batas atas eksplisit per tingkat.

**Batas jujurnya:** metadata juga bisa dipalsukan. Bukti sebenarnya hanya dari analisis spektrum
setelah berkas diunduh. Sebut hasilnya **"kandidat"**, bukan "lossless", dan jangan biarkan UI
menjanjikan lebih dari itu.

## Penyiapan

```yaml
# docker-compose.yml
ports:
  - "127.0.0.1:5030:5030"   # web + API — JANGAN diekspos ke internet
  - "50300:50300"            # P2P — HARUS publik, ini cara kerjanya
```

Tiga jebakan yang sudah terbukti memakan waktu:

- **`ip_address: 127.0.0.1` di dalam `slskd.yml` membuat port mustahil dijangkau** — curl balas
  `000`. Docker meneruskan trafik ke IP container, bukan loopback-nya. Isi `0.0.0.0`; keamanan
  dijamin oleh port binding `127.0.0.1:5030:5030` di compose, bukan oleh opsi ini.
- **`cidr: 127.0.0.1/32` pada API key menyebabkan 401**, karena permintaan datang dari IP bridge
  Docker. Batasi lewat port binding saja, jangan lewat CIDR.
- **Blok `permissions` sudah usang** di versi baru — dipindah ke
  `transfers.download.destination`. Container crash-loop sampai blok itu dihapus.

Ambil skema API yang asli dari instance yang berjalan, jangan menebak nama field:

```bash
curl -s http://127.0.0.1:5030/swagger/v0/swagger.json -o openapi.json
```

## Dua hal yang wajib dipenuhi user — tanpa ini sistemnya jalan tapi tidak menghasilkan apa-apa

1. **Folder share harus terisi.** Soulseek memutus klien yang hanya mengunduh (leecher). Kalau
   folder share kosong, server tetap "jalan" tapi pencarian selalu kosong dan tidak ada peer yang
   mau mengunggah. Ini bukan setelan opsional.
2. **Akun Soulseek (gratis).** Terpisah dari kredensial panel slskd.

## Ekspektasi yang harus dikatakan di depan

Ini **bukan** streaming instan seperti provider berbayar. Unduhan mengantre di sisi peer: menit
sampai jam, dan bisa gagal. Karena itu infrastruktur unduhan latar yang sudah ada (WorkManager +
progress) justru cocok — tapi jangan menjanjikan pemutaran seketika.
