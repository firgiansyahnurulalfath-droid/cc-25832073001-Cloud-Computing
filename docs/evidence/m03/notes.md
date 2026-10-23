# Catatan temuan dan troubleshooting M03

- Sesi SSH sering terputus (Connection reset) karena idle lama; diatasi dengan login ulang dan keepalive.
- Paste file CSS sempat kacau di terminal; diatasi dengan menulis file dalam dua bagian.
- Perintah sudo sempat dijalankan di PowerShell laptop; harus dijalankan di dalam VPS.
- NSG Azure perlu dibuka untuk TCP 80 selain UFW.
