# Architecture v0.1

## Deployment View
Internet -> UFW -> Caddy :80 -> Gunicorn 127.0.0.1:8000 -> Flask

## Client, Repository, VPS
Laptop -> (SSH) -> VPS
Laptop -> (browser) -> GitHub -> (git clone/pull via deploy key) -> VPS

## Security Decisions
- administrasi lewat user non-root
- autentikasi SSH dengan key, password SSH dimatikan
- UFW aktif
- backend hanya listen di loopback

## Current Limitations
HTTP saja, satu VPS, tanpa database, tanpa container, tanpa CI/CD.

## Planned Evolution
M04 DNS dan HTTPS, M05 data persisten, M06 container, M07 IaC, M09 CI/CD.
