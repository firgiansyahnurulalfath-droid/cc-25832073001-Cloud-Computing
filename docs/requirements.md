# Requirements

## Problem Statement
Mahasiswa mengalami kesulitan memantau jadwal kegiatan organisasi pada lingkungan kampus. Sistem akan menyediakan halaman daftar kegiatan sehingga informasi mudah diakses.

## Target Users
Sebagai mahasiswa, saya ingin melihat daftar kegiatan organisasi, sehingga saya tidak ketinggalan informasi.

## Functional Requirements
- FR-01 Sistem menampilkan halaman utama.
- FR-02 Sistem menyediakan health endpoint.
- FR-03 Sistem menampilkan metadata aplikasi.
- FR-04 Sistem menampilkan daftar objek utama proyek.

## Non-Functional Requirements
- NFR-01 Backend hanya listen pada loopback.
- NFR-02 Aplikasi dikelola systemd.
- NFR-03 Request publik masuk melalui reverse proxy.
- NFR-04 Secret tidak disimpan pada Git repository.
- NFR-05 Health endpoint mengembalikan HTTP 200 saat sehat.
- NFR-06 Deployment dapat direproduksi dari repository.
- NFR-07 Arsitektur sesuai VPS 1 vCPU/1 GB RAM.

## Scope M03
In scope: repository, requirements, architecture, ADR, aplikasi Flask dasar, hardening SSH, Gunicorn, systemd, Caddy, deployment HTTP.
Out of scope: database, Docker, IaC, CI/CD, TLS/domain, scaling, monitoring penuh.

## Constraints
1 vCPU, 1 GB RAM, 20 GB disk, Ubuntu Server 24.04, public IPv4.
