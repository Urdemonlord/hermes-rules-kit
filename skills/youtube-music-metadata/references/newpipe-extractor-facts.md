# Fakta NewPipe Extractor (v0.26.x)

Dipakai kalau metadata YouTube Music diambil lewat NewPipe Extractor. Ini daftar hal yang
**ada** dan **tidak ada** di API-nya — bedanya menentukan desain, jadi jangan menebak dari nama.

## `StreamInfoItem` — satu hasil lagu/video

Field yang tersedia (tidak lebih):

| Field | Isi |
|---|---|
| `name` | Judul VIDEO (bukan judul lagu) |
| `uploaderName` | Nama KANAL (bukan artis) |
| `duration` | Detik |
| `streamType` | `VIDEO_STREAM` / `AUDIO_STREAM` / `LIVE_STREAM` |
| `uploadDate` | Objek tanggal |
| `viewCount` | Tayangan |
| `url` | URL halaman |
| `uploaderUrl` | URL kanal |
| `shortFormContent` | Penanda Shorts |

**Tidak ada** `trackNumber`, `albumName`, `artistName`, `isrc`. Karena itu urutan album harus
diturunkan dari judul, dan artist harus dibersihkan dari nama kanal.

`streamType` adalah satu-satunya cara menyaring non-audio yang jelas; live stream tidak punya
durasi tetap sehingga tidak layak masuk album.

## `PlaylistInfoItem` — satu hasil album/playlist

- `getPlaylistType()` → `PlaylistType`:
  - `NORMAL` — playlist/album yang benar-benar didaftarkan.
  - `MIX_MUSIC`, `MIX_STREAM`, `MIX_GENRE` — **campuran otomatis**; bukan rilisan album.
- `getUploaderName()`, `getStreamCount()`, `getThumbnails()`.

Tipe selain `NORMAL` adalah satu-satunya sinyal andal untuk membedakan mix dari album.

## Content filter pencarian

`SearchQueryHandlerFactory`:

- `FILTER_MUSIC_SONGS = "music_songs"`
- `FILTER_MUSIC_VIDEOS = "music_videos"`
- `FILTER_MUSIC_ALBUMS = "music_albums"` — **mengembalikan `PlaylistInfoItem`, dan isinya
  termasuk playlist user + mix**, bukan hanya album.
- `FILTER_MUSIC_PLAYLISTS = "music_playlists"`
- `FILTER_MUSIC_ARTISTS = "music_artists"`

Pakai `FILTER_MUSIC_SONGS` untuk lagu. Jangan pakai `FILTER_MUSIC_ALBUMS` lalu menganggap
hasilnya album tanpa memeriksa `getPlaylistType()`.

## Mengambil lagu di dalam album

Album hasil pencarian diekspos sebagai `PlaylistInfoItem`, dan lagunya ada di `relatedItems`
(milik `InfoItem`, bukan `PlaylistInfoItem` sendiri). `relatedItems` berisi campuran tipe —
saring dengan `filterIsInstance<StreamInfoItem>()` dan periksa `streamType`, jangan asumsikan
semuanya lagu. Lalu buang duplikat dengan `videoId`, karena satu video bisa muncul dua kali.

## Catatan verifikasi

Tidak adanya field di tabel di atas sudah diverifikasi dari javadoc v0.26.5, bukan dari
kegagalan kompilasi. Kalau versi NewPipe naik, **cek ulang javadoc-nya sebelum mengandalkan
kolom "Tidak ada"** — NewPipe cukup sering menambah field, dan field yang baru ada akan
membatalkan alasan mengapa nomor trek dibaca dari judul.
