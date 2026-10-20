# Mendelegasikan lapisan tipis di atas inti yang sudah ditulis sendiri

## Pola

Fitur biasanya punya dua lapisan dengan sifat berbeda:

- **Inti** — model data, repository, service, lifecycle. Keputusan desain dan
  konsistensi antar-file hidup di sini. Sulit diverifikasi, mahal diperbaiki.
- **Lapisan tipis** — ViewModel, komposabel UI, string resource, wiring
  navigasi. Mekanis, berdiri sendiri di atas inti, dan cakupannya jelas.

Tulis intinya sendiri. Delegasikan lapisan tipisnya kalau memang perlu
kecepatan.

## Mengapa delegasi relatif aman

Delegasi jadi murah **bukan** karena tugasnya mudah, tapi karena kegagalannya
tidak merusak apa pun: kalau anak tugas kehabisan waktu, `git status`
menunjukkan tidak ada file baru. Tidak ada merge yang harus diperiksa, tidak
ada state setengah jadi. Kalau berhasil, hasilnya memakai persis API inti yang
sudah ada. Kalau gagal, perbaikannya cuma menulis ulang beberapa file — tidak
ada investigasi.

## Urutan yang benar

1. Tulis dan commit inti sendiri lebih dulu
2. Pastikan `git status` bersih dan compiler sudah pernah melewati inti itu
3. Baru delegasikan lapisan tipis

Jangan mendelegasikan sesuatu yang belum pernah dikompilasi. Anak tugas akan
mengeksekusi tebakan tentang API yang belum pernah dibuktikan, lalu
melaporkannya sebagai fakta — dan ringkasan yang terdengar yakin sangat
menyesatkan kalau tidak diverifikasi.

## Batas yang nyata: anak tugas bisa kehabisan waktu tanpa menghasilkan apa pun

Anak tugas punya batas waktu. Kalau habis, hasilnya nol file.

Aturan praktis:

- Setelah dispatch, **verifikasi hasilnya dengan `git status`, bukan dari
  ringkasan anak tugas.** Ringkasan bisa terlihat berhasil tanpa file apa pun.
- Bila delegasi gagal, selesaikan sendiri. Lapisan tipis biasanya hanya
  beberapa file dan tidak jauh lebih sulit daripada yang lain.
- `output_schema` tidak menjamin apa pun: anak tugas bisa kehabisan waktu
  sebelum mengisinya. Perlakukan hasil tanpa bukti file sebagai tidak ada.

## Apa yang layak didelegasikan

Lapisan yang memenuhi ketiganya:

- berdiri sendiri di atas inti yang sudah dikompilasi
- tidak butuh keputusan desain
- punya batas yang jelas: daftar file yang harus dibuat

Yang tidak layak: apa pun yang perlu tahu mengapa sebuah API berbentuk begitu,
atau apa pun yang harus konsisten dengan file lain.

## Yang tidak boleh ditulis ulang di test

Test tidak boleh memuat salinan nilai yang benar-benar hidup di file produksi.

- **Nama berkas** diambil dari sumber runtime dengan regex, bukan diketik ulang
  sebagai literal. Kalau nama berubah, test ikut menangkap; kalau literal,
  test hanya menguji kebetulan.
- **Konstanta batas** dibaca dari tempat aslinya. Dua angka yang sama di dua
  file bisa berbeda makna tanpa siapa pun sadar.

Hindari juga objek helper yang hanya dipakai test — kalau tidak ada kode
produksi yang memakainya, ia hanya menguji dirinya sendiri.