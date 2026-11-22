"""10 uji otomatis (AT-01..AT-07b). Jalankan: python -m pytest -q"""
import sqlite3
import threading

import pytest
from werkzeug.security import generate_password_hash

from app import buka_db, create_app

SANDI = "sandi-uji-12345"
H = {"X-Requested-With": "katalog"}


def bikin_app(tmp_path, **extra):
    cfg = {
        "DB_PATH": str(tmp_path / "uji.db"), "SECRET_KEY": "kunci-uji", "APP_ENV": "testing",
        "ADMIN_USER": "admin", "ADMIN_PASSWORD_HASH": generate_password_hash(SANDI, method="pbkdf2:sha256"),
        "BATAS_PESANAN": 1000, "BATAS_LOGIN": 1000,
    }
    cfg.update(extra)
    app = create_app(cfg)
    d = buka_db(cfg["DB_PATH"])
    d.execute("INSERT INTO produk (nama, harga, stok) VALUES ('Dodol Uji', 25000, 5)")
    d.execute("INSERT INTO produk (nama, harga, stok) VALUES ('Wajit Uji', 20000, 1)")
    d.close()
    return app


@pytest.fixture
def app(tmp_path):
    return bikin_app(tmp_path)


@pytest.fixture
def klien(app):
    return app.test_client()


def admin_login(c):
    r = c.post("/api/admin/login", json={"username": "admin", "password": SANDI}, headers=H)
    assert r.status_code == 200
    return c


def pesan(c, item, **kw):
    body = {"nama": "Budi Santoso", "kontak": "081234567890", "item": item}
    body.update(kw)
    return c.post("/api/pesanan", json=body)


def stok(app, pid):
    d = buka_db(app.config["DB_PATH"])
    try:
        return d.execute("SELECT stok FROM produk WHERE id=?", (pid,)).fetchone()[0]
    finally:
        d.close()


# 1. FR-03 + FR-01: /health dan katalog tampil
def test_01_health_dan_katalog(klien):
    r = klien.get("/health")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"
    html = klien.get("/").get_data(as_text=True)
    assert "Dodol Uji" in html and "Rp 25.000" in html
    assert "kontak" not in str(klien.get("/api/produk").get_json()).lower()


# 2. AT-01: pesanan terkirim, kode+token, harga dihitung server
def test_02_pesanan_berhasil_harga_dari_server(klien, app):
    r = pesan(klien, [{"produk_id": 1, "qty": 2}], harga=1, total=1)  # harga dari klien diabaikan
    assert r.status_code == 201
    d = r.get_json()
    assert d["kode"].startswith("OG-") and len(d["token"]) == 32
    assert d["total"] == 50000
    assert stok(app, 1) == 3


# 3. AT-02: data tetap ada setelah "restart" (aplikasi dibuat ulang pada DB yang sama)
def test_03_data_bertahan_setelah_restart(app, tmp_path):
    d = pesan(app.test_client(), [{"produk_id": 1, "qty": 1}]).get_json()
    app2 = create_app({
        "DB_PATH": str(tmp_path / "uji.db"), "SECRET_KEY": "kunci-uji", "APP_ENV": "testing",
        "ADMIN_PASSWORD_HASH": "",
    })
    r = app2.test_client().get(f"/api/pesanan/{d['kode']}", headers={"X-Order-Token": d["token"]})
    assert r.status_code == 200 and r.get_json()["total"] == 25000


# 4. AT-04: endpoint tulis tanpa login ditolak
def test_04_tulis_tanpa_login_ditolak(klien):
    assert klien.post("/api/admin/produk", json={"nama": "X", "harga": 5000, "stok": 1}, headers=H).status_code == 401
    assert klien.put("/api/admin/produk/1", json={"stok": 99}, headers=H).status_code == 401
    assert klien.delete("/api/admin/produk/1", headers=H).status_code == 401
    assert klien.get("/api/admin/pesanan").status_code == 401
    assert klien.post("/api/admin/pesanan/OG-XXXXXXXX/status", json={"status": "dikemas"}, headers=H).status_code == 401
    salah = klien.post("/api/admin/login", json={"username": "admin", "password": "salah"}, headers=H)
    assert salah.status_code == 401
    # tanpa header kustom (mis. form lintas situs) ditolak walau sudah login
    admin_login(klien)
    assert klien.post("/api/admin/produk", json={"nama": "X", "harga": 5000, "stok": 1}).status_code == 403


# 5. FR-04: admin menambah, mengubah, menghapus produk
def test_05_admin_crud_produk(klien):
    admin_login(klien)
    r = klien.post("/api/admin/produk", json={"nama": "Keripik Uji", "harga": 15000, "stok": 7}, headers=H)
    assert r.status_code == 201
    pid = r.get_json()["id"]
    r = klien.put(f"/api/admin/produk/{pid}", json={"harga": 17000, "stok": 9}, headers=H)
    assert r.get_json()["harga"] == 17000 and r.get_json()["stok"] == 9
    assert klien.delete(f"/api/admin/produk/{pid}", headers=H).get_json()["hasil"] == "dihapus"
    assert klien.put(f"/api/admin/produk/{pid}", json={"stok": 1}, headers=H).status_code == 404


# 6. AT-05: input tidak valid -> pesan jelas, tanpa stack trace
def test_06_validasi_dan_error_ramah(klien):
    kasus = [
        ({"nama": "A", "kontak": "081234567890", "item": [{"produk_id": 1, "qty": 1}]}, "nama"),
        ({"nama": "Budi", "kontak": "abc", "item": [{"produk_id": 1, "qty": 1}]}, "kontak"),
        ({"nama": "Budi", "kontak": "081234567890", "item": []}, "item"),
        ({"nama": "Budi", "kontak": "081234567890", "item": [{"produk_id": 1, "qty": -3}]}, "qty"),
        ({"nama": "Budi", "kontak": "081234567890", "item": [{"produk_id": 1, "qty": "dua"}]}, "qty"),
        ({"nama": "Budi", "kontak": "081234567890", "item": [{"produk_id": 999, "qty": 1}]}, "item"),
    ]
    for body, field in kasus:
        r = klien.post("/api/pesanan", json=body)
        assert r.status_code == 400, body
        j = r.get_json()
        assert j["field"] == field and "Traceback" not in r.get_data(as_text=True)
    assert klien.post("/api/pesanan", data="bukan json", content_type="text/plain").status_code == 400
    assert klien.get("/tidak-ada").status_code == 404
    assert "Traceback" not in klien.get("/tidak-ada").get_data(as_text=True)


# 7. AT-06: dua pembeli bersamaan membeli unit terakhir -> satu berhasil, stok tidak negatif
def test_07_stok_terakhir_atomik(app):
    hasil, gerbang = [], threading.Barrier(2)

    def beli():
        c = app.test_client()
        gerbang.wait()
        hasil.append(pesan(c, [{"produk_id": 2, "qty": 1}]).status_code)

    t = [threading.Thread(target=beli) for _ in range(2)]
    [x.start() for x in t]
    [x.join() for x in t]
    assert sorted(hasil) == [201, 409]
    assert stok(app, 2) == 0
    # stok tidak boleh negatif walau ada yang mencoba memaksa
    d = buka_db(app.config["DB_PATH"])
    with pytest.raises(sqlite3.IntegrityError):
        d.execute("UPDATE produk SET stok = -1 WHERE id=2")
    d.close()


# 8. FR-06: idempotency key -> permintaan ulang tidak membuat pesanan/stok ganda
def test_08_idempotensi(klien, app):
    kunci = "kunci-unik-12345"
    r1 = pesan(klien, [{"produk_id": 1, "qty": 2}], idempotency_key=kunci)
    r2 = pesan(klien, [{"produk_id": 1, "qty": 2}], idempotency_key=kunci)
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r1.get_json()["kode"] == r2.get_json()["kode"] and r1.get_json()["token"] == r2.get_json()["token"]
    assert stok(app, 1) == 3  # berkurang sekali saja
    assert pesan(klien, [{"produk_id": 1, "qty": 1}], idempotency_key="pendek").status_code == 400


# 9. AT-07/07b: pelanggan hanya melihat pesanannya; pihak lain ditolak; admin melihat semua
def test_09_kontrol_akses_idor(klien, app):
    a = pesan(klien, [{"produk_id": 1, "qty": 1}], nama="Pelanggan A", kontak="081111111111").get_json()
    b = pesan(klien, [{"produk_id": 1, "qty": 1}], nama="Pelanggan B", kontak="082222222222").get_json()
    lihat = lambda c, kode, tok=None: c.get(f"/api/pesanan/{kode}", headers={"X-Order-Token": tok} if tok else {})
    orang = app.test_client()
    assert lihat(orang, a["kode"]).status_code == 404  # tanpa token
    assert lihat(orang, a["kode"], b["token"]).status_code == 404  # token pesanan lain
    assert lihat(orang, a["kode"], "x" * 32).status_code == 404
    ok = lihat(orang, a["kode"], a["token"])
    assert ok.status_code == 200 and "081111111111" in ok.get_data(as_text=True)
    assert "082222222222" not in ok.get_data(as_text=True)
    assert orang.get("/api/admin/pesanan").status_code == 401  # daftar semua pesanan hanya admin
    admin_login(orang)
    semua = orang.get("/api/admin/pesanan").get_json()["pesanan"]
    assert {p["kode"] for p in semua} == {a["kode"], b["kode"]}
    assert lihat(orang, b["kode"]).status_code == 200  # admin tanpa token


# 10. Transisi status: lompatan ditolak, pembatalan mengembalikan stok
def test_10_transisi_status_dan_batal(klien, app):
    admin_login(klien)
    kode = pesan(klien, [{"produk_id": 1, "qty": 2}]).get_json()["kode"]
    assert stok(app, 1) == 3
    ubah = lambda s: klien.post(f"/api/admin/pesanan/{kode}/status", json={"status": s}, headers=H)
    assert ubah("selesai").status_code == 409  # lompat status
    assert ubah("ngawur").status_code == 400
    assert ubah("dikonfirmasi").status_code == 200
    assert ubah("dibatalkan").status_code == 200
    assert stok(app, 1) == 5  # stok kembali
    assert ubah("dikemas").status_code == 409  # sudah dibatalkan
    assert ubah("dibatalkan").status_code == 409  # tidak bisa dibatalkan dua kali (stok tidak dobel)
    assert stok(app, 1) == 5
