"""Katalog & Pemesanan Oleh-oleh Garut (PTI 2802).

Flask + SQLite. Tanpa dependensi baru di luar requirements.txt M03.
Rancangan mengikuti FR-01..FR-07 pada dokumen studi kelayakan.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

BASE_DIR = Path(__file__).resolve().parent

# Transisi status pesanan (FR-06/FR-07): lompatan lain ditolak server.
ALUR_STATUS = {
    "baru": ["dikonfirmasi", "dibatalkan"],
    "dikonfirmasi": ["dikemas", "dibatalkan"],
    "dikemas": ["dikirim"],
    "dikirim": ["selesai"],
    "selesai": [],
    "dibatalkan": [],
}
KODE_HURUF = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
KONTAK_RE = re.compile(r"^([0-9+\-\s()]{8,20}|[^@\s]{1,60}@[^@\s]{1,60}\.[^@\s]{2,20})$")
IDEM_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS produk (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nama TEXT NOT NULL,
  harga INTEGER NOT NULL CHECK (harga > 0),
  stok INTEGER NOT NULL CHECK (stok >= 0),
  deskripsi TEXT NOT NULL DEFAULT '',
  foto_url TEXT NOT NULL DEFAULT '',
  aktif INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS pesanan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kode TEXT NOT NULL UNIQUE,
  idem_key TEXT UNIQUE,
  nama TEXT NOT NULL,
  kontak TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'baru',
  total INTEGER NOT NULL,
  dibuat TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_pesanan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pesanan_id INTEGER NOT NULL REFERENCES pesanan(id),
  produk_id INTEGER NOT NULL REFERENCES produk(id),
  nama_produk TEXT NOT NULL,
  harga INTEGER NOT NULL,
  qty INTEGER NOT NULL CHECK (qty > 0)
);
CREATE INDEX IF NOT EXISTS ix_item_pesanan ON item_pesanan(pesanan_id);
"""


class ApiError(Exception):
    def __init__(self, status, message, field=None):
        super().__init__(message)
        self.status, self.message, self.field = status, message, field


class RateLimiter:
    """Batas laju sederhana per kunci (satu proses; cukup untuk 1 worker)."""

    def __init__(self, maks, detik):
        self.maks, self.detik = maks, detik
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def boleh(self, kunci):
        sekarang = time.monotonic()
        with self._lock:
            if len(self._hits) > 5000:
                self._hits.clear()
            q = self._hits[kunci]
            while q and sekarang - q[0] > self.detik:
                q.popleft()
            if len(q) >= self.maks:
                return False
            q.append(sekarang)
            return True


def buka_db(path):
    c = sqlite3.connect(path, timeout=5, isolation_level=None, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=5000")
    return c


@contextmanager
def transaksi(d):
    """BEGIN IMMEDIATE: penulis lain menunggu, sehingga cek stok bersifat atomik."""
    d.execute("BEGIN IMMEDIATE")
    try:
        yield
        d.execute("COMMIT")
    except BaseException:
        if d.in_transaction:
            d.execute("ROLLBACK")
        raise


def _secret_dari_file(path):
    if path.exists():
        return path.read_text().strip()
    nilai = secrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(nilai)
    return nilai


def _sekarang():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "Isi permintaan harus berupa JSON yang valid.")
    return data


def _teks(data, nama, minimal, maksimal, label, wajib=True):
    v = data.get(nama)
    if v is None and not wajib:
        return None
    if not isinstance(v, str):
        raise ApiError(400, f"{label} wajib diisi.", nama)
    v = v.strip()
    if not (minimal <= len(v) <= maksimal):
        raise ApiError(400, f"{label} harus {minimal}-{maksimal} karakter.", nama)
    return v


def _int(v, label, field, minimal, maksimal):
    if isinstance(v, bool) or not isinstance(v, int):
        raise ApiError(400, f"{label} harus berupa bilangan bulat.", field)
    if not (minimal <= v <= maksimal):
        raise ApiError(400, f"{label} harus antara {minimal} dan {maksimal}.", field)
    return v


def _produk_dari(data, parsial):
    """Validasi input produk. parsial=True untuk PUT (hanya field yang dikirim)."""
    out = {}

    def ada(k):
        return k in data

    if ada("nama") or not parsial:
        out["nama"] = _teks(data, "nama", 2, 80, "Nama produk")
    if ada("harga") or not parsial:
        out["harga"] = _int(data.get("harga"), "Harga", "harga", 1000, 10_000_000)
    if ada("stok") or not parsial:
        out["stok"] = _int(data.get("stok"), "Stok", "stok", 0, 100_000)
    if ada("deskripsi"):
        out["deskripsi"] = _teks(data, "deskripsi", 0, 300, "Deskripsi")
    if ada("foto_url"):
        f = _teks(data, "foto_url", 0, 200, "Alamat foto")
        if f and not (f.startswith("/static/") or f.startswith("https://")):
            raise ApiError(400, "Alamat foto harus diawali /static/ atau https://.", "foto_url")
        out["foto_url"] = f
    if ada("aktif"):
        if not isinstance(data["aktif"], bool):
            raise ApiError(400, "Aktif harus true atau false.", "aktif")
        out["aktif"] = 1 if data["aktif"] else 0
    if parsial and not out:
        raise ApiError(400, "Tidak ada field yang diubah.")
    return out


def create_app(config=None):
    app = Flask(__name__)
    cfg = {
        "DB_PATH": os.getenv("DB_PATH", str(BASE_DIR / "data" / "katalog.db")),
        "APP_ENV": os.getenv("APP_ENV", "development"),
        "SECRET_KEY": os.getenv("SECRET_KEY", ""),
        "ADMIN_USER": os.getenv("ADMIN_USER", "admin"),
        "ADMIN_PASSWORD_HASH": os.getenv("ADMIN_PASSWORD_HASH", ""),
        "BATAS_PESANAN": 10,
        "BATAS_LOGIN": 5,
        "JENDELA_DETIK": 60,
    }
    cfg.update(config or {})
    app.config.update(cfg)
    db_path = Path(cfg["DB_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = _secret_dari_file(db_path.parent / ".secret_key")
    produksi = cfg["APP_ENV"] == "production"
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=produksi,
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if produksi:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    init = buka_db(db_path)
    init.executescript(SCHEMA)
    init.close()

    batas_pesanan = RateLimiter(cfg["BATAS_PESANAN"], cfg["JENDELA_DETIK"])
    batas_login = RateLimiter(cfg["BATAS_LOGIN"], cfg["JENDELA_DETIK"])

    def db():
        if "db" not in g:
            g.db = buka_db(db_path)
        return g.db

    @app.teardown_appcontext
    def tutup_db(_exc):
        d = g.pop("db", None)
        if d is not None:
            d.close()

    def token_untuk(kode):
        mac = hmac.new(app.config["SECRET_KEY"].encode(), kode.encode(), hashlib.sha256)
        return mac.hexdigest()[:32]

    def butuh_admin(fn):
        @wraps(fn)
        def dibungkus(*a, **kw):
            if not session.get("admin"):
                raise ApiError(401, "Silakan login sebagai admin.")
            return fn(*a, **kw)

        return dibungkus

    @app.before_request
    def cek_csrf():
        # Tulis ke /api/admin wajib memakai header kustom (tidak bisa dikirim form lintas situs).
        if request.path.startswith("/api/admin/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("X-Requested-With") != "katalog":
                raise ApiError(403, "Permintaan tidak valid.")

    @app.after_request
    def header_keamanan(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https: data:; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- penanganan error (FR-05: ramah, tanpa stack trace) ----------
    def _balas(status, pesan, field=None):
        if request.path.startswith("/api/"):
            body = {"error": pesan}
            if field:
                body["field"] = field
            return jsonify(body), status
        return render_template("error.html", status=status, pesan=pesan), status

    @app.errorhandler(ApiError)
    def tangani_api(e):
        return _balas(e.status, e.message, e.field)

    @app.errorhandler(HTTPException)
    def tangani_http(e):
        pesan = {404: "Halaman tidak ditemukan.", 405: "Metode tidak diizinkan.",
                 413: "Permintaan terlalu besar."}.get(e.code, "Permintaan tidak dapat diproses.")
        return _balas(e.code, pesan)

    @app.errorhandler(Exception)
    def tangani_umum(e):
        app.logger.exception("Kesalahan tak terduga")  # detail hanya di log server
        return _balas(500, "Terjadi kesalahan di server. Coba lagi nanti.")

    # ---------- halaman ----------
    @app.get("/")
    def index():
        produk = db().execute(
            "SELECT id, nama, harga, stok, deskripsi, foto_url FROM produk WHERE aktif=1 ORDER BY nama"
        ).fetchall()
        return render_template("index.html", produk=produk, app_env=cfg["APP_ENV"])

    @app.get("/admin")
    def halaman_admin():
        return render_template("admin.html")

    @app.get("/health")
    def health():
        try:
            db().execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return jsonify(status="error"), 503
        return jsonify(status="ok", environment=cfg["APP_ENV"], timestamp=_sekarang())

    # ---------- API publik ----------
    @app.get("/api/produk")
    def api_produk():
        rows = db().execute(
            "SELECT id, nama, harga, stok, deskripsi, foto_url FROM produk WHERE aktif=1 ORDER BY nama"
        ).fetchall()
        return jsonify(produk=[dict(r) for r in rows])

    def pesanan_json(d, row, dengan_kontak):
        items = d.execute(
            "SELECT nama_produk, harga, qty FROM item_pesanan WHERE pesanan_id=? ORDER BY id", (row["id"],)
        ).fetchall()
        out = {
            "kode": row["kode"], "status": row["status"], "total": row["total"], "dibuat": row["dibuat"],
            "item": [{"nama": i["nama_produk"], "harga": i["harga"], "qty": i["qty"]} for i in items],
        }
        if dengan_kontak:
            out["nama"], out["kontak"] = row["nama"], row["kontak"]
        return out

    def baca_item(data):
        mentah = data.get("item")
        if not isinstance(mentah, list) or not (1 <= len(mentah) <= 10):
            raise ApiError(400, "Pilih 1 sampai 10 produk untuk dipesan.", "item")
        gabung = {}
        for it in mentah:
            if not isinstance(it, dict):
                raise ApiError(400, "Format item pesanan tidak valid.", "item")
            pid = _int(it.get("produk_id"), "ID produk", "produk_id", 1, 10**9)
            qty = _int(it.get("qty"), "Jumlah", "qty", 1, 20)
            gabung[pid] = gabung.get(pid, 0) + qty
        for pid, qty in gabung.items():
            if qty > 20:
                raise ApiError(400, "Jumlah per produk maksimal 20.", "qty")
        return sorted(gabung.items())

    @app.post("/api/pesanan")
    def buat_pesanan():
        ip = request.remote_addr or "?"
        if not batas_pesanan.boleh(ip):
            raise ApiError(429, "Terlalu banyak permintaan. Coba lagi sebentar lagi.")
        data = _json()
        nama = _teks(data, "nama", 2, 60, "Nama penerima")
        kontak = _teks(data, "kontak", 8, 80, "Kontak")
        if not KONTAK_RE.match(kontak):
            raise ApiError(400, "Kontak harus berupa nomor telepon atau email yang valid.", "kontak")
        idem = data.get("idempotency_key")
        if idem is not None and (not isinstance(idem, str) or not IDEM_RE.match(idem)):
            raise ApiError(400, "Kunci idempotensi tidak valid (8-64 huruf, angka, - atau _).", "idempotency_key")
        item = baca_item(data)

        d = db()
        with transaksi(d):
            if idem:
                lama = d.execute("SELECT * FROM pesanan WHERE idem_key=?", (idem,)).fetchone()
                if lama:  # permintaan ulang: kembalikan pesanan yang sama, stok tidak berkurang lagi
                    out = pesanan_json(d, lama, True)
                    out["token"] = token_untuk(lama["kode"])
                    return jsonify(out), 200
            baris, total = [], 0
            for pid, qty in item:
                p = d.execute("SELECT id, nama, harga FROM produk WHERE id=? AND aktif=1", (pid,)).fetchone()
                if not p:
                    raise ApiError(400, f"Produk dengan ID {pid} tidak tersedia.", "item")
                kurang = d.execute(
                    "UPDATE produk SET stok = stok - ? WHERE id=? AND stok >= ?", (qty, pid, qty)
                )
                if kurang.rowcount == 0:
                    raise ApiError(409, f"Stok {p['nama']} tidak mencukupi.", "item")
                baris.append((p["id"], p["nama"], p["harga"], qty))  # harga dari server, bukan klien
                total += p["harga"] * qty
            while True:
                kode = "OG-" + "".join(secrets.choice(KODE_HURUF) for _ in range(8))
                if not d.execute("SELECT 1 FROM pesanan WHERE kode=?", (kode,)).fetchone():
                    break
            cur = d.execute(
                "INSERT INTO pesanan (kode, idem_key, nama, kontak, status, total, dibuat) "
                "VALUES (?,?,?,?, 'baru', ?, ?)", (kode, idem, nama, kontak, total, _sekarang()),
            )
            for pid, nama_p, harga, qty in baris:
                d.execute(
                    "INSERT INTO item_pesanan (pesanan_id, produk_id, nama_produk, harga, qty) VALUES (?,?,?,?,?)",
                    (cur.lastrowid, pid, nama_p, harga, qty),
                )
        app.logger.info("pesanan dibuat kode=%s total=%s", kode, total)  # tanpa data kontak
        row = d.execute("SELECT * FROM pesanan WHERE kode=?", (kode,)).fetchone()
        out = pesanan_json(d, row, True)
        out["token"] = token_untuk(kode)
        return jsonify(out), 201

    @app.get("/api/pesanan/<kode>")
    def lihat_pesanan(kode):
        d = db()
        row = d.execute("SELECT * FROM pesanan WHERE kode=?", (kode,)).fetchone()
        token = request.headers.get("X-Order-Token", "")
        sah = bool(row) and (session.get("admin") or hmac.compare_digest(token, token_untuk(kode)))
        if not sah:  # 404 seragam: tidak membocorkan apakah kode ada
            raise ApiError(404, "Pesanan tidak ditemukan. Periksa kode dan token.")
        return jsonify(pesanan_json(d, row, True))

    # ---------- API admin ----------
    @app.post("/api/admin/login")
    def admin_login():
        if not batas_login.boleh(request.remote_addr or "?"):
            raise ApiError(429, "Terlalu banyak percobaan login. Coba lagi nanti.")
        if not app.config["ADMIN_PASSWORD_HASH"]:
            raise ApiError(503, "Login admin belum dikonfigurasi.")
        data = _json()
        user, sandi = data.get("username"), data.get("password")
        if not isinstance(user, str) or not isinstance(sandi, str):
            raise ApiError(400, "Username dan password wajib diisi.")
        ok_user = hmac.compare_digest(user, app.config["ADMIN_USER"])
        ok_sandi = check_password_hash(app.config["ADMIN_PASSWORD_HASH"], sandi)
        if not (ok_user and ok_sandi):
            raise ApiError(401, "Username atau password salah.")
        session.clear()
        session["admin"] = True
        return jsonify(ok=True)

    @app.post("/api/admin/logout")
    def admin_logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/admin/produk")
    @butuh_admin
    def admin_daftar_produk():
        rows = db().execute("SELECT * FROM produk ORDER BY id").fetchall()
        return jsonify(produk=[dict(r) for r in rows])

    @app.post("/api/admin/produk")
    @butuh_admin
    def admin_tambah_produk():
        v = _produk_dari(_json(), parsial=False)
        v.setdefault("deskripsi", "")
        v.setdefault("foto_url", "")
        v.setdefault("aktif", 1)
        d = db()
        cur = d.execute(
            "INSERT INTO produk (nama, harga, stok, deskripsi, foto_url, aktif) VALUES (:nama,:harga,:stok,:deskripsi,:foto_url,:aktif)",
            v,
        )
        return jsonify(dict(d.execute("SELECT * FROM produk WHERE id=?", (cur.lastrowid,)).fetchone())), 201

    @app.put("/api/admin/produk/<int:pid>")
    @butuh_admin
    def admin_ubah_produk(pid):
        v = _produk_dari(_json(), parsial=True)
        d = db()
        if not d.execute("SELECT 1 FROM produk WHERE id=?", (pid,)).fetchone():
            raise ApiError(404, "Produk tidak ditemukan.")
        sets = ", ".join(f"{k}=?" for k in v)  # nama kolom dari whitelist validasi, bukan input mentah
        d.execute(f"UPDATE produk SET {sets} WHERE id=?", (*v.values(), pid))
        return jsonify(dict(d.execute("SELECT * FROM produk WHERE id=?", (pid,)).fetchone()))

    @app.delete("/api/admin/produk/<int:pid>")
    @butuh_admin
    def admin_hapus_produk(pid):
        d = db()
        if not d.execute("SELECT 1 FROM produk WHERE id=?", (pid,)).fetchone():
            raise ApiError(404, "Produk tidak ditemukan.")
        dipakai = d.execute("SELECT 1 FROM item_pesanan WHERE produk_id=? LIMIT 1", (pid,)).fetchone()
        if dipakai:  # riwayat pesanan harus utuh: nonaktifkan, jangan hapus
            d.execute("UPDATE produk SET aktif=0 WHERE id=?", (pid,))
            return jsonify(hasil="dinonaktifkan", alasan="Produk sudah ada di riwayat pesanan.")
        d.execute("DELETE FROM produk WHERE id=?", (pid,))
        return jsonify(hasil="dihapus")

    @app.get("/api/admin/pesanan")
    @butuh_admin
    def admin_daftar_pesanan():
        d = db()
        rows = d.execute("SELECT * FROM pesanan ORDER BY id DESC LIMIT 200").fetchall()
        return jsonify(pesanan=[pesanan_json(d, r, True) for r in rows])

    @app.post("/api/admin/pesanan/<kode>/status")
    @butuh_admin
    def admin_ubah_status(kode):
        baru = _json().get("status")
        if baru not in ALUR_STATUS:
            raise ApiError(400, "Status tidak dikenal.", "status")
        d = db()
        with transaksi(d):
            row = d.execute("SELECT * FROM pesanan WHERE kode=?", (kode,)).fetchone()
            if not row:
                raise ApiError(404, "Pesanan tidak ditemukan.")
            if baru not in ALUR_STATUS[row["status"]]:
                raise ApiError(409, f"Status tidak boleh berubah dari {row['status']} ke {baru}.", "status")
            if baru == "dibatalkan":  # kembalikan stok
                for it in d.execute("SELECT produk_id, qty FROM item_pesanan WHERE pesanan_id=?", (row["id"],)):
                    d.execute("UPDATE produk SET stok = stok + ? WHERE id=?", (it["qty"], it["produk_id"]))
            d.execute("UPDATE pesanan SET status=? WHERE id=?", (baru, row["id"]))
        row = d.execute("SELECT * FROM pesanan WHERE kode=?", (kode,)).fetchone()
        return jsonify(pesanan_json(d, row, True))

    return app


app = create_app() if os.getenv("APP_SKIP_DEFAULT") != "1" else None
