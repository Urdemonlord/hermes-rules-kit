---
name: youtube-music-metadata
description: "Use when reading artist/album metadata from YouTube."
---

# Metadata YouTube Music di pemutar musik

## Kapan dipakai

- Artist di library tampil sebagai `"Aimer - Topic"` / `"AimerVEVO"`.
- Judul lagu menyimpan `"(Official Video)"`, `"[MV]"`, `"(Lyrics)"`.
- "Pas nyari album, lagu yang keluar aneh" / urutan album acak.
- Menyambungkan hasil pencarian YouTube ke tabel lagu (search, album, artis, impor playlist).
- Membangun fitur apa pun yang mengubah metadata YouTube jadi entitas lagu.

## Fakta inti yang mengubah semua keputusan

**YouTube Music bukan katalog musik — ia katalog VIDEO.** Yang tersedia di sana adalah
*halaman video*, dan dua konsekuensinya menjalar ke mana-mana:

- `uploaderName` adalah nama **kanal**, bukan nama artis. YouTube Music membuat kanal otomatis
  `"<Artist> - Topic"` untuk tiap artis, dan kanal label memakai akhiran `VEVO`.
- Judulnya adalah judul **video**, bukan judul lagu.
- Hasil filter "album" **tidak selalu album** (lihat bagian album).

Jadi nilai mentah dari YouTube tidak pernah layak disimpan apa adanya ke database.

## Aturan utama: bersihkan di titik INGEST, lewat SATU modul bersama

Ini pelajaran yang paling mahal di kelas ini, dan bentuknya bukan "tambahkan pembersih"
melainkan "**letakkan pembersihnya di tempat yang benar**":

- **Bersihkan saat metadata diubah jadi entitas lagu — di satu fungsi konversi bersama**, bukan
  di masing-masing pemanggil. Satu fungsi yang membersihkan judul+artist saat item YouTube
  dipetakan ke hasil akan otomatis menutup SEMUA jalur sekaligus: pencarian, daftar album, daftar
  artis, dan metadata saat lagu disimpan.
- **Kalau pembersihannya hanya dipanggil di satu jalur, jalur lain menyimpan nama mentah.**
  Gejalanya: fitur yang memakai jalur itu tampak benar, sementara library menampilkan
  `"Aimer - Topic"` — karena aturannya ada, tapi tidak pernah dijalankan di jalur simpan.
- **Satu implementasi, bukan dua.** Kalau aturan pembersihan sudah ada di satu modul (mis.
  pembersih kueri lirik), modul lain **mendelegasikan** ke sana — jangan menyalin aturannya.
  Salinan akan menyimpang, dan tidak ada yang memberi tahu. Modul pembersih harus murni string
  tanpa dependensi Android supaya bisa diuji lewat JVM biasa.

### Penanda kanal (nama artist)

Buang: akhiran ` - Topic` (kanal otomatis), akhiran `VEVO` (kanal label), akhiran ` Official`.
Hanya **akhiran** yang dibuang — `"VEVO Music"` harus tetap utuh.

Pemisahnya bisa berspasi atau tidak: `"Aimer - Topic"` maupun `"Aimer-Topic"` sama-sama muncul.
`removeSuffix("- Topic")` **tidak** menangkap bentuk tanpa spasi; pakai regex
`\s*-\s*Topic$` dengan `IGNORE_CASE`.

Nama yang seluruhnya penanda kanal (`" - Topic"`) jadi **null**, bukan string kosong — supaya
tidak tersimpan sebagai artist hampa.

### Penanda judul (judul lagu)

**Buang penanda BENTUK VIDEO** (lagunya identik dengan versi asli): `Official Video`,
`Official Music Video`, `Official Audio`, `Lyrics`, `Lyric Video`, `Visualizer`, `MV`, `M/V`,
`PV`, `4K`, `HD`, `Color Coded`, `Eng Sub`. Tangani juga kurung Asia `【】`. Buang berulang
sampai tidak ada lagi — judul bisa punya lebih dari satu: `"X (Official Video) [4K]"`.

**PERTAHANKAN penanda VERSI MUSIK**: `Live`, `Acoustic`, `Remix`, `Instrumental`, `feat.`,
tahun. Itu menandai lagu yang **berbeda**, bukan sekadar bentuk videonya. Membuangnya membuat
lagu live terlihat sama dengan versi studio. Lebih baik tidak ketemu daripada ketemu tapi salah.

## Album: filter "album" tidak menjamin album

Filter album YouTube Music mengembalikan **playlist dan campuran otomatis (mix)** juga, bukan
hanya album rilisan. Mix berisi lagu dari banyak artis tanpa urutan album — menyebutnya "Album"
membuat user membukanya dan merasa "albumnya salah".

- **Bedakan lewat tipe playlist, bukan tebakan dari jumlah lagu.** `PlaylistInfoItem` punya
  `getPlaylistType()`; nilai selain `NORMAL` (`MIX_MUSIC`, `MIX_STREAM`, `MIX_GENRE`) berarti
  campuran otomatis. `StreamInfoItem` **tidak** punya field ini, jadi pemeriksaan hanya mungkin
  di hasil pencarian, bukan di dalam daftar lagunya.
- **Beri keterangan, jangan sembunyikan.** Menyaringnya diam-diam menghilangkan hasil yang sah;
  yang salah adalah labelnya. Tampilkan dengan keterangan seperti "Campuran, bukan album".
- Konsekuensinya: jangan pernah mengklaim sesuatu sebagai album hanya karena ia keluar dari
  filter album.

## Urutan lagu di dalam album

Urutan yang dikirim YouTube **tidak dijamin** sama dengan urutan album.

- **Tidak ada nomor trek di item hasil.** `StreamInfoItem` hanya punya durasi, jenis stream,
  nama, uploader, tanggal, dan jumlah tayangan. Satu-satunya petunjuk nomor urut adalah judulnya
  (`"1. Judul"`, `"01 - Judul"`).
- **Urutkan hanya kalau MAYORITAS lagu bernomor.** Kalau hanya segelintir yang bernomor,
  mengurutkan justru mengacak: lagu bernomor melompat ke depan, sisanya tetap di tempat.
  Menampilkan urutan yang mungkin salah lebih baik daripada menampilkan urutan yang pasti salah.
- **Pemisah wajib ada setelah angka.** Angka tanpa pemisah bukan nomor trek — `"1979"` dan
  `"2 Become 1"` tidak boleh dibaca sebagai trek 1979 / trek 2. Regex:
  `^\s*(\d{1,3})\s*[.\-–—)]\s+`.
- Pengurutan harus **stabil** untuk lagu yang tidak bernomor, supaya hasilnya tidak berubah-ubah
  antar-pemuatan.

## Aturan yang mengikat

- **Jangan percaya metadata YouTube sebagai fakta musik.** Ia fakta tentang halaman video.
  Bersihkan sebelum disimpan; jangan bersihkan hanya saat menampilkan (data mentahnya sudah
  terlanjur masuk database dan ikut tersalin ke playlist/impor).
- **Pembersihan tidak boleh mengubah arti.** Membuang penanda video aman; membuang penanda versi
  tidak. Kalau ragu, pertahankan — lagu dengan nama lebih panjang masih bisa dicari, lagu yang
  salah versi tidak bisa diperbaiki otomatis.
- **Uji pembersihnya sebagai fungsi murni di JVM.** Ini kelas yang paling mudah salah dan paling
  murah diuji tanpa jaringan; aturan pembersihan yang tidak punya tes adalah aturan yang akan
  memburuk diam-diam.

Fakta API NewPipe Extractor (field yang tersedia, enum tipe playlist, content filter) ada di
`references/newpipe-extractor-facts.md`.
