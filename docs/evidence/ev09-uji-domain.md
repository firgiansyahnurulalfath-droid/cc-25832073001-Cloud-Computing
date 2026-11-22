# EV-09. Uji domain dan akses peran (stok atomik, IDOR)

Tanggal: 21-11-2026 | Lingkungan: VM Azure, https://oleholeh-garut.australiaeast.cloudapp.azure.com | Data: sintetis

## Pemasangan
- Aplikasi di /srv/katalog, service katalog.service (gunicorn 1 worker, 2 thread, 127.0.0.1:8001), Caddy meneruskan HTTPS ke port 8001.
- pytest di VM: 10 passed.
- Rahasia (SECRET_KEY, hash password admin) hanya di .env (izin 600), tidak di Git.

## Hasil uji di server asli
| Uji | Diharapkan | Hasil |
|---|---|---|
| Pesan 2 x Dodol Original (Rp 25.000) | total dihitung server, stok 40 jadi 38 | Rp 50.000; stok 38 |
| Admin: dikonfirmasi lalu dibatalkan | stok kembali | stok 40 |
| Dua pembeli bersamaan, stok produk uji = 1 | satu 201, satu 409, stok 0 | 201 dan 409; stok 0; satu pesanan |
| GET pesanan tanpa token | 404 | 404 |
| GET pesanan dengan token pesanan lain | 404 | 404 |
| GET pesanan dengan token benar | 200 | 200 |
| GET kode acak | 404 | 404 |
| GET daftar pesanan admin tanpa login | 401 | 401 |
| PUT produk tanpa login | 401, stok tidak berubah | 401; stok tetap 40 |
| DELETE produk tanpa login | 401 | 401 |

## Batasan
- Uji bersamaan hanya dua permintaan; kapasitas dan p95 belum diukur (EV-08).
- Idempotency key baru diuji lewat uji otomatis, belum di server asli.
- Data kontak pelanggan uji dihapus dari database setelah pengujian.
