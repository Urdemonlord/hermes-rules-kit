# Tidal lewat hifi-api — endpoint & penyiapan

Proxy Tidal yang paling banyak dipakai: `binimum/hifi-api` (fork dari `sachinsenal0x64/hifi`).
Banyak fork lain dengan API yang sama; endpoint di bawah berlaku untuk instance self-host mana pun.

## Endpoint

| Kebutuhan | Endpoint | Bentuk respons |
|---|---|---|
| Cari lagu | `GET /search/?s={judul artis}` | `data.items[]` — `id`, `title`, `artist`, `mediaMetadata.tags` |
| Info trek | `GET /info/?id={id}` | metadata + `isrc` + `audioQuality` |
| **Audio** | `GET /track/?id={id}&quality={q}` | **manifest DASH base64** — lihat di bawah |
| Manifest DASH | `GET /dash/{id}` | 302 ke manifest `.mpd` |
| Manifest mentah | `GET /trackManifests/{id}?formats=…` | JSON v2 lengkap (URI, hash, DRM) |

### `/track/` mengembalikan manifest DASH, BUKAN URL `.flac` langsung

Ini sudah diverifikasi langsung terhadap server, dan bertentangan dengan dugaan yang wajar.
Yang keluar adalah XML MPD ter-encode base64:

```json
{
  "version": "2.3",
  "data": {
    "assetPresentation": "FULL",
    "audioQuality": "HI_RES_LOSSLESS",
    "manifestMimeType": "application/dash+xml",
    "manifest": "<base64 dari XML MPD>"
  }
}
```

XML MPD itu berisi satu `Representation` per format, mis. `FLAC_HIRES,176400,24`
(`codecs="flac"`), dengan `SegmentTemplate` (initialization + `$Number$.mp4`).

**Kabar baiknya:** ExoPlayer/Media3 sudah mengerti DASH, jadi parser manifest sendiri
kemungkinan besar tidak diperlukan — serahkan URL-nya ke Media3. Tapi ini tetap berarti
satu URL yang sama **tidak** bisa langsung dipakai OkHttp untuk unduh; kalau mengunduh,
segmennya harus dirakit dari manifest.

### `assetPresentation` wajib diperiksa

`"FULL"` = lagu utuh. `"PREVIEW"` = **hanya 30 detik** — durasi MPD terbaca `PT29.976S`
dan host CDN-nya `sp-ad-fa.audio.tidal.com`, bukan `lgf.audio.tidal.com`. Nilai `PREVIEW`
muncu pada akun tanpa langganan, dan **responsnya tetap sukses** — jadi ini tidak terlihat
seperti kegagalan kecuali diperiksa khusus.

`mediaMetadata.tags` di hasil pencarian memberi tahu tingkat tertinggi yang didukung trek
(`LOSSLESS`, `HIRES_LOSSLESS`, `DOLBY_ATMOS`) — pakai ini untuk memilih, bukan menebak.

## Tingkat kualitas

| Kualitas | Format | Keterangan |
|---|---|---|
| `HIGH` | AAC 320 kbps | Cadangan |
| `LOSSLESS` | FLAC 16-bit / 44.1 kHz | Kualitas CD |
| `HI_RES_LOSSLESS` | FLAC 24-bit / 96–192 kHz | Hanya trek ber-tag `HIRES_LOSSLESS` dan akun yang berhak |
| `EAC3_JOC` | E-AC-3 (Dolby Atmos) | Hanya trek ber-tag `DOLBY_ATMOS` |

Kalau kualitas yang diminta tidak berhak, Tidal bisa membalas `403 CLIENT_NOT_ENTITLED` (ketika
hanya format itu yang diminta) atau **diam-diam menurunkan** ke yang tersedia (ketika beberapa
format diminta sekaligus). Karena itu periksa `mimeType`/`codecs` di respons.

**Tanpa langganan HiFi, kenyataannya bukan penurunan kualitas — melainkan potongan 30 detik.**
Lihat bagian `assetPresentation` di atas.

## Penyiapan self-host

```bash
git clone https://github.com/binimum/hifi-api && cd hifi-api
cp .env.example .env
# jalankan tidal_auth/tidal_auth.py mengikuti instruksi → menghasilkan token.json
docker compose up -d          # default port 8000
curl "http://127.0.0.1:8000/track/?id=<id>&quality=LOSSLESS"
```

- `token.json` dibaca dari direktori tempat server dijalankan, bukan tempat skrip berada.
- Menjalankan `tidal_auth.py` dengan `token.json` yang sudah ada **menambahkan** token baru ke
  berkas itu, tidak menimpanya — berguna untuk beberapa akun, tapi mudah membuat berkas membengkak.
- Akun bisa ditandai `"role": "catalog"` agar dipakai untuk metadata saja dan tidak ikut rotasi
  playback.
- Playback dibatasi satu permintaan in-flight per akun; permintaan berlebih dibalas `202 Accepted`
  + `statusUrl` untuk dipoll.

## Mitigasi ban

Tidal memblokir akun yang memakai jalur ini, termasuk instance homelab yang tidak diekspos ke
internet. Yang berlaku:

- Satu permintaan trek sekaligus, dari satu IP.
- Jangan berpindah IP di tengah pemakaian.
- Jangan ekspos instance ke internet; pakai jaringan lokal atau tunnel terautentikasi.
- Antrean unduhan diberi jeda, jangan paralel.

## Alternatif provider

| Sumber | Catatan |
|---|---|
| `BartolomeoRusso9/qobuz-rest-api` | REST lokal untuk Qobuz — `/download-url/{id}` mengembalikan URL bertanda tangan + `mime_type`/`bit_depth`/`sampling_rate` |
| `api.song.link` (Odesli) | Pemetaan lintas layanan: Spotify/ISRC → id Tidal/Qobuz/Deezer, plus ISRC |
| `spotbye/SpotiFLAC` (Go + Wails) | Referensi rantai lengkap: Spotify metadata → ISRC → Tidal/Qobuz. Desktop, tidak bisa di-embed |
| `spotiflacapp/SpotiFLAC-Mobile` (Flutter + Go) | Referensi format extension `.sflx` (ZIP: `manifest.json` + JS) dan registry JSON dengan digest SHA-256 |

Tidak ada SDK Android/Kotlin di ekosistem ini — yang bisa dipakai ulang adalah rantai endpoint-nya,
bukan kodenya.
