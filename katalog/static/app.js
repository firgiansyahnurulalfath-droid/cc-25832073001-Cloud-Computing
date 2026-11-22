"use strict";
const $ = (s) => document.querySelector(s);
const rp = (n) => "Rp " + Number(n).toLocaleString("id-ID");
const kunciBaru = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2));
let kunci = kunciBaru();

function pesan(el, teks, galat) {
  el.textContent = teks;
  el.className = galat ? "galat" : "ok";
}

$("#form-pesan").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, tombol = f.querySelector("button"), info = $("#status-pesan");
  const item = [...document.querySelectorAll(".kartu")]
    .map((k) => ({ produk_id: Number(k.dataset.id), qty: Number((k.querySelector(".qty") || {}).value || 0) }))
    .filter((i) => i.qty > 0);
  if (!item.length) return pesan(info, "Pilih minimal satu produk (jumlah lebih dari 0).", true);
  tombol.disabled = true;
  try {
    const r = await fetch("/api/pesanan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nama: f.nama.value, kontak: f.kontak.value, item, idempotency_key: kunci }),
    });
    const d = await r.json();
    if (!r.ok) return pesan(info, d.error || "Pesanan gagal dikirim.", true);
    pesan(info, "Total " + rp(d.total) + ".", false);
    $("#out-kode").textContent = d.kode;
    $("#out-token").textContent = d.token;
    $("#hasil-pesan").hidden = false;
    kunci = kunciBaru();
    document.querySelectorAll(".qty").forEach((q) => (q.value = 0));
  } catch (e) {
    pesan(info, "Koneksi bermasalah. Tekan tombol lagi, pesanan tidak akan ganda.", true);
  } finally {
    tombol.disabled = false;
  }
});

$("#form-cek").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, info = $("#status-cek"), daftar = $("#detail-cek");
  daftar.replaceChildren();
  try {
    const r = await fetch("/api/pesanan/" + encodeURIComponent(f.kode.value.trim()), {
      headers: { "X-Order-Token": f.token.value.trim() },
    });
    const d = await r.json();
    if (!r.ok) return pesan(info, d.error || "Gagal memuat pesanan.", true);
    pesan(info, "Status: " + d.status + " | Total " + rp(d.total), false);
    d.item.forEach((i) => {
      const li = document.createElement("li");
      li.textContent = i.nama + " x " + i.qty + " (" + rp(i.harga) + ")";
      daftar.append(li);
    });
  } catch (e) {
    pesan(info, "Koneksi bermasalah. Coba lagi.", true);
  }
});
