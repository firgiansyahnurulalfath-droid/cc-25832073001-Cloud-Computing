# ADR-0001: Initial VPS Deployment Architecture

## Status
Accepted

## Context
VPS 1 vCPU, RAM 1 GB, disk 20 GB, Ubuntu Server 24.04.

## Decision
Flask, Gunicorn (1 worker), systemd, Caddy, UFW, GitHub.

## Alternatives
1. Node.js + PM2
2. NGINX + Gunicorn
3. Docker
4. PHP-FPM

## Rationale
Resource VPS terbatas (1 vCPU dan 1 GB RAM), sehingga dipilih komponen yang ringan dan sederhana. Flask cocok untuk aplikasi dasar, dan Gunicorn dengan 1 worker hemat memori. systemd dipilih karena sudah tersedia di Ubuntu, menjalankan ulang aplikasi otomatis saat gagal atau setelah reboot, dan lognya mudah dibaca. Caddy dipilih karena konfigurasinya singkat dan HTTPS mudah diaktifkan di M04. Node.js + PM2 dan PHP-FPM tidak dipilih karena aplikasi memakai Python. NGINX + Gunicorn umum dipakai, tetapi konfigurasinya lebih panjang dibanding Caddy. Docker ditunda karena baru dipelajari di M06 dan menambah beban memori pada VPS kecil.

## Consequences
Positif: Arsitektur ringan, mudah dipahami dan di-debug, aplikasi hidup kembali otomatis setelah reboot, dan konfigurasi proxy singkat.
Negatif: Deployment masih manual lewat git pull, hanya satu server tanpa cadangan, belum memakai HTTPS, dan kapasitas terbatas karena hanya 1 worker.

## Review Trigger
Review pada M06/M07.
