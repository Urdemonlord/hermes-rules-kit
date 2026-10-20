# Pola callback bridge: server sebagai perantara auth

Untuk integrasi yang butuh web auth tapi client-nya tidak punya URL publik —
Android, CLI tanpa port masuk, aplikasi desktop yang tidak ingin menambah
protokol kustom.

## Bentuknya

```
app  ── GET /connect?nonce=N ──────▶ server
                                    server: ingat nonce N
app  ◀── {auth_url} ─────────────────
app  ── Custom Tab ke auth_url ─────▶ provider (user login + grant)
provider ── redirect ─▶ /callback?token=<redacted>
                                    server: auth.getSession -> session key
                                    server: simpan di RAM di bawah nonce N
                                    server: tampilkan "kembali ke aplikasi"
app  ── GET /session?nonce=N ──────▶ server
app  ◀── {session_key} ─────────────   (server BUANG nonce-nya)
```

Server adalah **penghubung, bukan pemilik**. Setelah langkah terakhir tidak ada
apa pun yang tersisa: session key tidak pernah menyentuh disk, dan mati begitu
proses berhenti.

## Nonce dibuat client, bukan server

Penting, dan mudah dibalik karena terdengar lebih sederhana. Kalau server yang
mengacak nonce lalu menampilkannya di halaman "sudah terhubung", nonce itu
masuk riwayat browser perangkat user — dan siapa pun yang punya device itu
bisa membacanya lalu mengambil session key-nya.

Jadi: app mengacak nonce sendiri, mengirimkannya di `/connect`, lalu polling
`/session` dengan nonce yang sama. Server tidak pernah menerbitkan nilai yang
perlu dirahasiakan; dia hanya menerima dan mengikat.

Konsekuensi yang harus ditulis jujur di catatan proyek: callback URL biasanya
**tetap** (dipakai satu kali saat pendaftaran akun API), jadi nonce tidak bisa
ikut di URL dan server tidak tahu nonce mana yang sedang berjalan. Pengikatan
terbaik adalah "nonce paling lama menunggu" — benar selama aplikasi menjaga
hanya satu login aktif pada satu waktu. Sebutkan syarat itu, jangan pretend
mereka identik.

## Kenapa session key tidak boleh disimpan di server

Session key biasanya berumur panjang — sering tanpa refresh sama sekali, jadi
nilainya juga nilai sebenarnya. Kalau server menyimpannya:

- server memegang kredensial user, padahal server punya banyak pembeda lain dari app,
- session key menentukan "scrobble mana" di riwayat, jadi ini data yang sensitif,
- menambah tempat yang harus direvoke kalau bocor.

Nonce sekali-pakai membalikkan itu: server memegang kredensial selama ~60 detik
lalu melepasnya, dan yang tersisa di app adalah milik user yang sedang login —
yang memang harus ada di perangkat.

## Token berumur pendek membuat opsi "salin manual" mustahil

Beberapa provider memberi authorization token yang **berumur singkat dan sekali
pakai**. Kalau begitu, user tidak mungkin menyalinnya lewat layar setup: app
menyimpan token saat menerimanya, dan tokennya sudah hangus. Jadi "token
manual" bukan opsi yang merepotkan — itu **tidak mungkin secara arsitektur**.
Cek masa hidup token sebelum menawarkannya sebagai pilihan.

Kalau provider memberi kredensial berumur panjang yang bisa diambil di luar
app, mode manual sah — dan kalau tidak butuh server sama sekali, itu selalu
lebih sempit.

## Motor auth punya beberapa jalur; daftar app yang menentukan jalannya

Banyak motor (Last.fm, Spotify, dan sebagian besar OAuth lawas) punya lebih dari
satu jalur auth, dan jalur mana yang aktif ditentukan **formulir pendaftaran akun
API** — bukan kode yang lo tulis.

Konsekuensi praktis: jangan langsung tulis server yang melakukan
`auth.getToken` lalu menyimpan request token. Baca dulu halaman pendaftaran.
Kalau ada field **Callback URL** dan itu diisi, motor otomatis memakai jalur web:
app membuka halaman auth, motor yang mengarahkan balik ke callback, dan session
key ditutup dengan satu panggilan. Request token tidak pernah ada.

Kalau callback URL tidak diisi, jalur desktop yang aktif — request token wajib,
dan barulah bentuk bridge lengkap tadi perlu.

Jadi periksa selalu: form apa yang sudah diisi di akun API, dan jalur mana
yang berlaku untuk form itu. Menebak jalur menghasilkan satu panggilan
provider yang tidak perlu, satu state yang harus dirawat, dan satu tempat
failure tambahan.

## API key tetap ada di server, sama sekali tidak di app

Selama callback di server, tukar kode juga di server, dan API key pun begitu.
Tidak ada alasan untuk membawanya ke binary — dan membawanya ke binary berarti
siapa pun yang membongkar APK punya credential itu.

## Validator bentuk harus berasal dari sampel nyata, bukan tebakan format

Endpoint yang dibuka browser sering memvalidasi bentuk parameter sebelum
meneruskannya ke provider — supaya tidak ada yang bisa mendorong input
sembarang dan membuat server memanggil API atas namanya. Bentuk itu perlu;
**asumsi tentang isinya tidak boleh dibuat-buat**.

Aturannya: regex bentuk diturunkan dari satu nilai yang benar-benar tertangkap
dari provider, bukan dari dugaan tentang format. Dugaan yang salah tidak
menghasilkan test gagal — ia menghasilkan penolakan diam-diam atas nilai yang
sah, dan gejalanya muncul sebagai "provider menolak login" padahal provider
**tidak pernah dipanggil**.

Yang aman hanya memblokir yang memang mustahil: panjang di luar rentang, dan
karakter yang tidak mungkin dibawa media transport URL. Jangan persempit ke
alfabet lebih kecil dari yang provider benar-benar pakai — token base64
mengandung huruf besar, huruf kecil, angka, `-`, dan `_`.

Kalau validator menolak nilai yang terlihat sah dari sesi nyata, itu **bukti
validator-nya salah**, bukan bukti nilainya nakal. Baca cabang mana yang
menolak — validasi lokal atau respons provider — sebelum menyimpulkan provider
menolak.

Test wajib punya minimal satu nilai dari tangkapan nyata, di samping nilai
sintetis. Kalau seluruh nilai test berasal dari dugaan yang sama dengan kodenya,
test hanya membuktikan tebakan itu konsisten dengan dirinya sendiri, dan test
hijau justru menutupi bug yang ada di validasinya.

Dua jebakan kecil saat menulis fixture validator:

- **Panjang hasil pengulangan string mudah salah hitung.** `"a_b-C" * 5 + "ab"`
  punya 27 karakter, bukan 32. Assert `len(s) == 32` di dalam test, atau pakai
  pola yang jelas panjangnya, supaya batas panjang benar-benar diuji.
- **Daftar "harus ditolak" jangan berisi karakter yang sebenarnya sah.** Kalau
  test menaruh huruf besar sebagai "harus ditolak", ia sedang mengunci bug yang
  belum terlihat. Setiap entri daftar itu harus bisa dijelaskan: karakter apa
  yang membuat provider mustahil menghasilkannya.

## Test yang paling berharga, dan kenapa

**Signature computation** adalah bagian yang paling mudah salah dan paling mau
diam-diam. API sering menolak signature yang salah dengan kode error generik
("invalid signature") tanpa menjelaskan apa yang berbeda, jadi tidak ada
trial-and-error yang_parse_. Verifikasi terhadap **contoh resmi di dokumentasi
provider**, lengkap dengan nilai yang diharapkan:

```python
def test_cocok_dengan_contoh_resmi(self):
    params = {"api_key": "xxxxxxxxxx", "method": "auth.getSession", "token": "yyyyyy"}
    expected = hashlib.md5(b"<string persis seperti di docs>ilovecher").hexdigest()
    self.assertEqual(api_sig(params), expected)
```

Aturan yang sering terlewat, semuanya layak test sendiri:

- parameter `format` **tidak ikut** ditandatangani,
- urutan parameter **tidak boleh** berpengaruh,
- secret yang berbeda menghasilkan signature berbeda.

## TTL jangan pernah jadi default argument

Python mengevaluasi default argumen **satu kali**, saat fungsi didefinisikan.
Jadi signature seperti ini tidak bisa diuji dan tidak bisa diubah saat berjalan:

```python
def take_session_key(self, nonce, ttl=NONCE_TTL_SEC):  # ttl terkunci selamanya
```

Simpan sebagai atribut instance, lalu baca `self._nonce_ttl`. Kalau tidak,
perubahan TTL diam-diam tidak berlaku dan test yang menyetelnya berbohong.

## Endpoint yang dipanggil app harus JSON, endpoint yang dibuka browser boleh HTML

Kalau satu service melayani dua jenis client, pisahkan cara menjawabnya. App
tidak bisa menampilkan pesan error yang badan balasanbodymya HTML; kalau
handler gagal di jalur yang biasanya dipanggil app, hasilnya response HTML dan
UI-nya menampilkan sesuatu yang tidak masuk akal.

Buat test untuk setiap endpoint yang dipanggil app: status code **dan**
`Content-Type`. Test yang hanya mengecek status akan lolos pada balasan HTML
yang tidak bisa di-parse app.

## Tutupi BrokenPipeError saat menulis response

`BaseHTTPRequestHandler` menjalankan thread per koneksi, dan `wfile.write` bisa
dilempar `BrokenPipeError` / `ConnectionResetError` ketika client menutup
koneksi lebih dulu. Pada halaman callback, **menutup tab atau swipe-back adalah
kejadian biasa** — tanpa penanganan itu satu gestur user mematikan seluruh
service.

```python
try:
    self.wfile.write(body)
except (BrokenPipeError, ConnectionResetError):
    LOG.info("client menutup koneksi sebelum balasan dikirim")
```

Test: subclass handler yang sengaja memutuskan koneksi, lalu assert server
**masih melayani** request berikutnya. Kalau handler-nya melempar keluar, test
ini gagal.

## Lock untuk state yang dipakai beberapa thread

`ThreadingHTTPServer` menjalankan tiap request di thread sendiri. Kalau state
berupa dict di memori, ambil dan hapus harus di bawah satu lock — kalau tidak,
dua callback bersamaan bisa membatalkan satu sama lain.

Test penutupnya: N thread berebut satu token → tepat satu `True`. Assertion
harus menghitung, bukan hanya mengecek tidak ada error.

## Jangan log query string mentah

Endpoint callback menerima token lewat query string, dan default log memakai
format `self.path` — yang berarti token ikut masuk syslog. Potong dulu:

```python
def log_message(self, fmt, *args):
    LOG.info("%s %s", self.command, self.path.split("?")[0])
```

## Pola deployment di VPS

Ikuti preseden yang sudah ada di mesin itu, jangan supervised baru. Di VPS Meow
Labs sudah ada layanan Python kecil di belakang nginx (port localhost, systemd
unit dengan `MemoryMax` + `NoNewPrivileges` + `ProtectSystem`, lokasi nginx
dengan `proxy_pass`). Salin bentuk itu; jangan buka port ke publik.

Untuk layanan baru, pakai port baru juga: port yang dipakai service lain tidak
boleh dipakai ulang begitu saja. Verifikasi dengan `ss -tln` sebelum memilih.

## Batas bukti

Sukses lokal = service jalan, endpoint membalas status yang benar, signature
cocok dengan contoh resmi, state sekali-pakai dan tidak ada sisa. Itu semua
**belum** membuktikan auth-nya berhasil: itu baru terlihat setelah user benar
login lewat provider dan session key sampai ke app. Jangan menyebut alur
sebagai "terbukti" sebelum itu terjadi.