# Server proxy untuk app yang dikirim ke end user

Pakai ini ketika sebuah app yang **dikirim ke user** (APK, binary, extension)
perlu memanggil gateway dengan kredensial yang tidak boleh bocor.

## Kapan, dan bukan kapan

| Situasi | Pilihan |
|---|---|
| Tool dev, app internal, kunci sudah milik tiap orang | Minta user isi kunci sendiri. Sederhana, nol biaya ke kamu |
| APK / binary untuk download publik | **Proxy.** Kunci tidak pernah masuk artifact |
| Modul browser, ekstensi | Proxy, atau minta kunci — tapi cek dulu apakah model bisa jalan tanpa kunci |

Yang menentukan bukan tekniknya, tapi **apakah artifact-nya bisa dibongkar orang
lain**. APK itu zip; `unzip` + `strings` cukup untuk mengambil kunci yang ditanam.

## Bentuk responsnya: indeks, bukan urutan

Proxy tidak harus mengubah bentuk payload. Kalau client sudah mencocokkan hasil
lewat indeks (lihat bagian "Batch structured output" di SKILL.md), proxy
cukup meneruskan:

```
POST /api/translate   {"lines":[{"i":0,"text":"..."}, ...]}
->                     {"lines":[{"i":0,"romaji":"...","translation":"..."}, ...]}
```

Menjaga bentuk ini berarti logika client yang sudah ada dan sudah dites tidak
perlu disentuh sama sekali. Mengubah bentuk respons saat menambah proxy adalah
sumber regresi yang tidak perlu — cukup teruskan.

## Dua rem, karena server yang menanggung biaya

Tanpa rem, proxy jadi biaya terbuka yang dipakai orang lain.

1. **Cache.** Kunci = `sha256` dari payload lirik yang sudah dibersihkan. Lagu
   yang sama cukup dibayar sekali, berapa kali pun diklik. Cache hit **tidak
   memakai kuota**, karena tidak ada biaya. Kalau kunci cache ikut memuat isi
   payload, perubahan lirik otomatis jadi kunci baru — tidak perlu EXPIRY.
2. **Kuota.** N permintaan per hari per IP, WIB. Hit yang melebihi batas tetap
   dilayani dari cache; yang ditolak hanya yang butuh panggilan baru.

Perhatikan apa yang harus dibuktikan test, bukan yang terlihat benar di kode:

- kuota benar-benar habis setelah N, lalu **tetap** habis pada panggilan berikutnya
- kuota terpisah per IP
- hitungan reset saat tanggal berganti
- **cache hit tidak menaikkan kuota** — inilah yang membuat cache/rem biaya bekerja
- input rusak (indeks bukan integer, teks kosong, teks kepanjangan) ditolak
  **sebelum** sampai ke penyedia

## Kuota habis adalah hasil KETIGA, bukan kegagalan

Client yang memakai `List<T>?` tidak bisa membedakan 429 dari galat. Efeknya
user melihat tombol yang menyala tapi **tidak muncul apa-apa** — gejalanya
persis seperti "fiturnya rusak", padahal tidak ada yang rusak.

Bentuk hasil jadi tipe terpisah, bukan `null`:

```kotlin
sealed interface TranslationResult {
    data class Ok(val lines: List<LyricLine>) : TranslationResult
    data object Failed : TranslationResult          // ada yang salah
    data object QuotaHit : TranslationResult         // habis, pulih besok
}
```

Alasannya berbeda dari "gagal": kuota habis akan hilang **dengan sendirinya** di
reset berikutnya. Menampilkannya sebagai "tidak tersedia" membuatnya terlihat
rusak permanen dan membuat orang mengira tombolnya perlu diperbaiki.

Dua aturan yang menyertainya:

- **Jangan cache hasil `QuotaHit`.** Kalau masuk cache, besok permintaan yang
  sama dilayani hasil kosong yang sama dan tidak pernah dicoba lagi.
- **Hapus semua status gagal di `withTranslations`/sukses.** Subtitle yang
  sudah tampil tidak boleh ikut hilang karena status gagal dari percobaan
  sebelumnya masih menempel.

Perhatikan juga: penambahan field ke state berarti **semua** status text perlu
mendapat cabang baru — panel yang merender "loading atau gagal" jadi diam
ketika KuotaHit aktif, karena syaratnya tidak pernah terpenuhi.

## Jangan habiskan kuota produksi saat menguji batas

Menguji batas kuota dengan request sungguhan adalah cara termurah untuk
membuat fitur ini mati tepat saat user pertama mencobanya: request dia kena 429,
tombol menyala, tidak ada subtitle, dan laporanZpengguna jadi "fiturnya tidak
jalan".

Setelah menguji batas, **reset penghitungnya** dan konfirmasi dengan satu
request nyata yang sukses sebelum-you melapor selesai. Kalau tidak,artefak
"hijau" di CI dan"semuanya berfungsi" di laporan sama-sama tidak menjawab
apa yang dilihat user.

## Diagnosis: tombol menyala tapi tidak ada subtitle

Jangan debug app. Baca access log proxy lebih dulu — satu baris menjawab
pertanyaannya:

```bash
journalctl --user -u <proxy-service> --since '-30 min' | grep -i 'POST /api/translate'
```

Deretan `429` berturut-turut berarti app benar dan kuota habis. Request yang
tidak muncul sama sekali berarti titik kegagalan ada di sisi app (URL salah,
cleartext, permission). Request `200` tapi baris kosong berarti bentuk
respons berubah — cek nama field di sisi proxy dan parser secara bersamaan.

Payload datang dari internet. Validasi di satu tempat, sebelum cache dan sebelum
penyedia: daftar harus berupa list, `i` harus integer, `text` harus string
non-kosong setelah trim, panjang dibatasi. Body keseluruhan dibatasi juga
(`client_max_body_size` + pemeriksaan `Content-Length`) supaya satu POST
raksasa jadi amplifier ke gateway.

Batas per-baris dan batas jumlah-baris dua-duanya perlu: satu lagu normalnya
puluhan baris, jadi batas longgar tetap menutup payload buatan.

## Tiga jebakan nginx yang lolos diam-diam

Semuanya lolos tanpa job merah, jadi harus dicek eksplisit.

### 1. Kuota per-IP jadi per-proxy

Service yang menerima request dari nginx selalu melihat
`client_address = 127.0.0.1`. "N per hari per IP" berubah jadi N per hari untuk
**semua** user. Gejalanya tidak terlihat di log lokal — yang terlihat hanya
request dari satu IP.

```nginx
real_ip_header CF-Connecting-IP;
set_real_ip_from 0.0.0.0/0;
```

Verifikasi: paksa hitungan ke batas, lalu request lewat domain publik dan
konfirmasi 429 datang.

### 2. `^~` kalau ada regex location yang lebih umum

nginx mengecek **regex sebelum prefix location**. Kalau vhost punya
`location ~* \.apk$`, maka `location /api/translate` kalah dan request dilayani
sebagai berkas statis — 404, tanpa pernah sampai ke service. `^~` memberi tahu
nginx berhenti di prefix itu:

```nginx
location ^~ /api/translate {
    proxy_pass http://127.0.0.1:<port>/api/translate;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 60s;      # satu lyric penuh butuh puluhan detik
    proxy_buffering off;
    add_header Cache-Control "no-store" always;
    client_max_body_size 128k;
}
```

`proxy_read_timeout` harus lebih besar dari kasus terburuk yang nyata, bukan
default yang kebetulan lebih kecil. Timeout nginx dan timeout klien harus
disamakan, kalau tidak yang satu memotong lebih dulu dan gejalanya "kadang
gagal".

### 3. Backup di `sites-enabled`

nginx memuat `sites-enabled/*` dengan glob. `cp vhost vhost.bak.<timestamp>`
di dalam direktori itu menambah server block kedua untuk `server_name` yang
sama. `nginx -t` tetap **sukses** sambil mencetak `conflicting server name`,
dan setelah reload domain itu dilayani konfigurasi yang salah. Simpan di
`/etc/nginx/backups/`, dan baca **stderr** `nginx -t` — bukan exit code-nya.

## Arahkan ke gateway lokal kalau ada

Kalau di mesin yang sama sudah ada router yang memegang kredensial ke penyedia
(the gateway di `127.0.0.1`), arahkan proxy ke sana, bukan ke domain publik.
Kredensial lalu tidak pernah lewat jaringan publik, dan routing tetap milik
satu proses.

Konsekuensi yang harus diterima secara sadar: router memilih modelnya sendiri,
jadi respons bisa **tidak identik antar permintaan** untuk payload yang sama.
Artinya jangan pernah menjadikan kesamaan byte respons sebagai bukti cache
bekerja — buktinya `cached: true` di respons dan kuota yang **tidak naik**.

## Urutan yang mencegah app setengah jadi

Server proxy bisa selesai dan terverifikasi sementara app yang sudah tayang
**masih** meminta kunci — daftar ini jadi tidak ada yang berubah untuk user
lama. Kalau itu terjadi, yang harus disebut di laporan: sisi server hijau
adalah klaim terpisah dari "user tidak perlu lagi isi apa-apa".

Saat app diarahkan ke proxy, seluruh jejak kunci harus ikut hilang dalam satu
pass: field Settings, flow + setter di repository, state di ViewModel, header
`Authorization`, dan string resources yang jadi mati. `grep` nama field
tersebut setelah patch — bukan sebelum.