# ALAIR Ethnic admin field glossary (plain-language labels + tooltips)

Canonical mapping from developer field name to the label and tooltip the
non-technical operator sees. Reuse these exact words so the panel stays
consistent across pages. Rename the visible label; never touch input `name=`.

| Field (code) | Visible label | Tooltip gist |
|---|---|---|
| `slug` | Alamat URL | "Nama pendek untuk alamat halaman di internet, mis. /products/dress-tenun-kuning. Huruf kecil + tanda hubung, tanpa spasi. Dikosongkan = dibuat otomatis dari nama." |
| `price` | Harga (Jual) | "Harga yang dibayar pelanggan. Untuk produk bervarian, ini harga dasar — harga tiap varian diatur di tabel varian." |
| `compareAtPrice` | Harga Coret | "Harga asli sebelum dipotong. Harus lebih besar dari Harga Jual. Kalau diisi, katalog menampilkan harga coret + label diskon." |
| `stock` | Stok | "Jumlah unit yang bisa dibeli. Untuk produk BERVARIAN, ini hanya ringkasan — stok yang dihitung saat checkout adalah stok per varian." |
| `size` | Ukuran | "Ukuran tersedia untuk produk ini. Muncul sebagai pilihan di halaman produk, dan dicek saat pembeli menambah ke keranjang." |
| `tags` | Tag Produk | "Kata kunci untuk mengelompokkan produk di katalog. Pisahkan dengan koma. Contoh: tenun, dress, wanita, basic." |
| `searchKeywords` | Kata Kunci Pencarian | "Kata lain yang mungkin diketik pembeli saat mencari. Contoh: 'Dress Tenun' -> tulis juga 'baju tenun', 'gaun etnik'." |
| `fulfillmentType` | Cara Jual | "Ready Stock = barang sudah ada, langsung dikirim. Pre-Order = dibuat dulu setelah dipesan. Ini juga menentukan apakah stok berkurang saat checkout." |
| `preorderLeadDays` | Lama Pengerjaan (hari, untuk Pre-Order) | "Berapa hari kerja membuat pesanan pre-order. Dipakai menghitung perkiraan tanggal kirim yang tampil ke pembeli." |
| `isActive` | Tampilkan di Toko | "Kalau dimatikan, produk disembunyikan dari katalog dan tidak bisa dibeli, tapi datanya tetap tersimpan." |
| `isFeatured` | Produk Unggulan | "Menandai produk sebagai unggulan — tampil di bagian 'Unggulan' pada halaman utama." |
| `isNewArrival` | Produk Baru | "Menandai produk sebagai pendatang baru — tampil di bagian 'Baru' pada halaman utama." |
| `discountType` (voucher) | Jenis Diskon | "Potongan Harga = memotong total belanja sekian persen. Gratis Ongkir = biaya kirim jadi Rp0." |
| `minPurchase` (voucher) | Min. Belanja | "Total belanja paling sedikit supaya voucher bisa dipakai. Kosongkan kalau tanpa syarat." |
| `maxUses` (voucher) | Max Pakai | "Berapa kali voucher boleh dipakai. Setelah habis, otomatis tidak bisa dipakai lagi." |
| `sortOrder` (category) | Urutan | "Menentukan urutan tampil di katalog. Angka KECIL tampil lebih dulu (0 paling depan)." |
| `tier` (category) | Tingkat | "Umum untuk koleksi biasa, Eksklusif untuk koleksi premium. 'Tanpa Tingkat' = tidak ikut filter tier." |
| `role` (user) | Peran | "Admin = bisa masuk panel ini dan ubah semua data. Pembeli = hanya bisa belanja. Hati-hati menaikkan jadi Admin." |
| `order.status` | Status Pesanan | "Urutan normal: Menunggu -> Dikonfirmasi -> Diproses -> Dikirim -> Selesai. Pilih 'Dibatalkan' kalau batal." |
| `paymentStatus` | Pembayaran | paid -> Lunas, pending -> Menunggu, failed -> Gagal |
| `trackingCourier` | Kurir | "Nama ekspedisi pengiriman. Dipakai halaman lacak pesanan untuk melacak resi otomatis." |
| `trackingNumber` | No. Resi | "Nomor resi dari ekspedisi. Setelah diisi, pembeli bisa melacak di halaman /tracking." |
| `midtransMode` | Pembayaran (Midtrans) | "Uji Coba = latihan tanpa uang sungguhan. Asli = terima pembayaran betulan. Jangan pindah ke Asli sebelum semua dicoba." |
| `biteshipMode` | Pengiriman (Biteship) | "Uji Coba = latihan tanpa biaya nyata. Asli = ongkir sungguhan." |

## Status value translations (display only, never change stored value)

| Stored | Display |
|---|---|
| pending / confirmed / processing / shipped / delivered / cancelled | Menunggu / Dikonfirmasi / Diproses / Dikirim / Selesai / Dibatalkan |
| paid / pending / failed | Lunas / Menunggu / Gagal |
| active / inactive (product) | Tampil / Disembunyikan |
| basic / exclusive (tier) | Umum / Eksklusif |
| admin / customer (role) | Admin / Pembeli |
