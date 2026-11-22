"use strict";
const $ = (s) => document.querySelector(s);
const rp = (n) => "Rp " + Number(n).toLocaleString("id-ID");
const ALUR = { baru: ["dikonfirmasi", "dibatalkan"], dikonfirmasi: ["dikemas", "dibatalkan"], dikemas: ["dikirim"], dikirim: ["selesai"], selesai: [], dibatalkan: [] };

function el(tag, props, ...kids) {
  const e = Object.assign(document.createElement(tag), props || {});
  kids.forEach((k) => e.append(k));
  return e;
}
function info(teks, galat) {
  const m = $("#info");
  m.textContent = teks;
  m.className = galat ? "galat" : "ok";
}
async function panggil(metode, url, body) {
  const r = await fetch(url, {
    method: metode,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Requested-With": "katalog" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let d = {};
  try { d = await r.json(); } catch (e) { /* tubuh kosong */ }
  if (!r.ok) throw Object.assign(new Error(d.error || "Terjadi kesalahan."), { status: r.status });
  return d;
}
async function aksi(fn) {
  try { await fn(); } catch (e) {
    if (e.status === 401 && e.message.indexOf("login") !== -1) return tampil(false);
    info(e.message, true);
  }
}
function tampil(masuk) {
  $("#login").hidden = masuk;
  $("#panel").hidden = !masuk;
}

function barisProduk(p) {
  const nama = el("input", { value: p.nama }), harga = el("input", { type: "number", value: p.harga });
  const stok = el("input", { type: "number", value: p.stok }), aktif = el("input", { type: "checkbox", checked: !!p.aktif });
  const simpan = el("button", { type: "button", textContent: "Simpan" });
  const hapus = el("button", { type: "button", textContent: "Hapus" });
  simpan.onclick = () => aksi(async () => {
    await panggil("PUT", "/api/admin/produk/" + p.id, { nama: nama.value, harga: Number(harga.value), stok: Number(stok.value), aktif: aktif.checked });
    info("Produk disimpan.", false);
    await muat();
  });
  hapus.onclick = () => aksi(async () => {
    if (!confirm("Hapus produk " + p.nama + "?")) return;
    const d = await panggil("DELETE", "/api/admin/produk/" + p.id);
    info("Produk " + d.hasil + ".", false);
    await muat();
  });
  return el("tr", {}, el("td", {}, nama), el("td", {}, harga), el("td", {}, stok), el("td", {}, aktif), el("td", {}, simpan, " ", hapus));
}

function barisPesanan(o) {
  const pilih = el("select");
  (ALUR[o.status] || []).forEach((s) => pilih.append(el("option", { value: s, textContent: s })));
  const ubah = el("button", { type: "button", textContent: "Ubah", disabled: !pilih.options.length });
  ubah.onclick = () => aksi(async () => {
    await panggil("POST", "/api/admin/pesanan/" + o.kode + "/status", { status: pilih.value });
    info("Status pesanan diubah.", false);
    await muat();
  });
  const item = o.item.map((i) => i.nama + " x " + i.qty).join("; ");
  return el("tr", {}, el("td", { textContent: o.kode }), el("td", { textContent: o.nama }), el("td", { textContent: o.kontak }),
    el("td", { textContent: item }), el("td", { textContent: rp(o.total) }), el("td", { textContent: o.status }),
    el("td", {}, pilih, " ", ubah));
}

async function muat() {
  const [p, o] = await Promise.all([panggil("GET", "/api/admin/produk"), panggil("GET", "/api/admin/pesanan")]);
  $("#tabel-produk tbody").replaceChildren(...p.produk.map(barisProduk));
  $("#tabel-pesanan tbody").replaceChildren(...o.pesanan.map(barisPesanan));
  tampil(true);
}

$("#form-login").addEventListener("submit", (ev) => {
  ev.preventDefault();
  aksi(async () => {
    await panggil("POST", "/api/admin/login", { username: ev.target.username.value, password: ev.target.password.value });
    ev.target.password.value = "";
    info("", false);
    await muat();
  });
});
$("#form-tambah").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  aksi(async () => {
    await panggil("POST", "/api/admin/produk", { nama: f.nama.value, harga: Number(f.harga.value), stok: Number(f.stok.value), deskripsi: f.deskripsi.value });
    f.reset();
    info("Produk ditambahkan.", false);
    await muat();
  });
});
$("#keluar").onclick = () => aksi(async () => { await panggil("POST", "/api/admin/logout"); tampil(false); });
muat().catch(() => tampil(false));
