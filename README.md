# Info Kegiatan Kampus

Cloud Computing - PTI 2802, Pertemuan 3 - Project Inception

## Author
Firgiansyah Nurul Al Fath / 25832073001 / PTI 2A

## Problem
Mahasiswa mengalami kesulitan memantau jadwal kegiatan organisasi pada lingkungan kampus. Sistem akan menyediakan halaman daftar kegiatan sehingga informasi mudah diakses.

## Target Users
Sebagai mahasiswa, saya ingin melihat daftar kegiatan organisasi, sehingga saya tidak ketinggalan informasi.

## Features M03
Aplikasi dasar, health endpoint, deployment VPS.

## Architecture
Internet -> UFW -> Caddy -> Gunicorn -> Flask. Detail di docs/architecture.md.

## Infrastructure
Ubuntu Server 24.04, 1 vCPU, 1 GB RAM, 20 GB disk, Caddy, Gunicorn.

## Endpoint
http://20.92.76.50/ dan GET /health. Prosedur deployment ada di docs/deployment.md.

## Security
SSH key-only, root SSH nonaktif, UFW aktif, backend loopback-only.

## Limitations
HTTP saja, tanpa database, tanpa container, deployment manual.

## Roadmap
M04 DNS/HTTPS, M05 Data, M06 Container, M07 IaC, M09 CI/CD.
