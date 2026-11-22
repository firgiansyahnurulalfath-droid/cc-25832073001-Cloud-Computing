"""Perintah bantu: init-db | seed | hash-password."""
import getpass
import sys

from werkzeug.security import generate_password_hash

import app as modul

PRODUK_CONTOH = [  # data sintetis
    ("Dodol Garut Original 250 g", 25000, 40, "Dodol klasik manis legit."),
    ("Dodol Garut Rasa Durian 250 g", 32000, 25, "Dodol dengan aroma durian."),
    ("Wajit Cililin 10 pcs", 20000, 30, "Wajit ketan dibungkus daun jagung."),
    ("Paket Oleh-oleh Hemat", 70000, 15, "Isi: dodol, wajit, dan keripik."),
]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "hash-password":
        p1 = getpass.getpass("Password admin: ")
        if len(p1) < 10:
            sys.exit("Password minimal 10 karakter.")
        if p1 != getpass.getpass("Ulangi password: "):
            sys.exit("Password tidak sama.")
        print(generate_password_hash(p1, method="pbkdf2:sha256"))
        return
    flask_app = modul.app or modul.create_app()
    path = flask_app.config["DB_PATH"]
    if cmd == "init-db":
        print("Skema siap di", path)
    elif cmd == "seed":
        d = modul.buka_db(path)
        if d.execute("SELECT COUNT(*) FROM produk").fetchone()[0]:
            sys.exit("Tabel produk sudah berisi; seed dibatalkan.")
        for nama, harga, stok, desk in PRODUK_CONTOH:
            d.execute("INSERT INTO produk (nama, harga, stok, deskripsi) VALUES (?,?,?,?)", (nama, harga, stok, desk))
        print("Produk contoh dimasukkan:", len(PRODUK_CONTOH))
    else:
        sys.exit("Pakai: python manage.py [init-db|seed|hash-password]")


if __name__ == "__main__":
    main()
