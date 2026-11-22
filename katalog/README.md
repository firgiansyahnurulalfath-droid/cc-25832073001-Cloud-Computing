# Katalog dan Pemesanan Oleh-oleh Garut (PTI 2802)

Aplikasi Flask + SQLite untuk katalog produk, pemesanan, dan admin. Mengikuti FR-01 sampai FR-07 pada dokumen studi kelayakan.

## Menjalankan lokal
    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt -r requirements-dev.txt
    python manage.py init-db && python manage.py seed
    python -m pytest -q
    flask --app app run

## Konfigurasi (environment, bukan di Git)
Lihat `.env.example`. `SECRET_KEY` dan `ADMIN_PASSWORD_HASH` wajib di produksi.
Hash password dibuat dengan `python manage.py hash-password`.

## Keamanan singkat
- Harga dan stok dihitung server dalam transaksi `BEGIN IMMEDIATE`; stok tidak bisa negatif (CHECK + UPDATE bersyarat).
- Idempotency key mencegah pesanan ganda saat permintaan diulang.
- Pelanggan melihat pesanan lewat kode + token (header `X-Order-Token`); selain itu 404 seragam.
- Endpoint tulis admin butuh sesi login dan header `X-Requested-With`.
- Log pesanan tidak memuat data kontak.
