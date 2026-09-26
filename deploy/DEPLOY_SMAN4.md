# Deploy smkn4.klikide.my.id (VPS Linux + Cloudflare + HTTPS)

Target: `https://smkn4.klikide.my.id` → Nginx → Gunicorn → Flask, MySQL privat.
File siap pakai: `deploy/sman4-presensi.conf` (Nginx), `deploy/sman4-presensi.service` (systemd).

> Saya tidak punya akses ke akun Cloudflare kamu, jadi langkah DNS (no. 2)
> dikerjakan dari dashboard Cloudflare (±2 menit). Sisanya sudah disiapkan.

## 0. Prasyarat (belum ada)

- Satu VPS Linux (Ubuntu 22.04/24.04, RAM min. 2 GB) dengan IP publik, misal `203.0.113.10`.
- Akses root/SSH ke VPS.

## 1. Siapkan VPS

```bash
sudo apt update && sudo apt install -y python3.11-venv python3-pip mysql-server nginx certbot python3-certbot-nginx
sudo mysql_secure_installation
```

## 2. DNS di Cloudflare (dashboard kamu)

1. Buka domain `klikide.my.id` → menu **DNS** → **Add record**.
2. Type `A`, Name `smkn4`, IPv4 address = IP publik VPS, Proxy status **Proxied** (awan oranye).
3. Tunggu ±5 menit, pastikan `nslookup smkn4.klikide.my.id` mengarah ke IP VPS / Cloudflare.
4. Di menu **SSL/TLS**, set mode **Full (strict)**.

## 3. Aplikasi di VPS

```bash
sudo useradd -m -s /bin/bash presensi
sudo mkdir -p /opt/sistem-absensi-pwa /var/log/sman4-presensi
sudo chown presensi:www-data /opt/sistem-absensi-pwa /var/log/sman4-presensi
# Salin repo ke /opt/sistem-absensi-pwa (git clone / rsync dari laptop).
cd /opt/sistem-absensi-pwa
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gunicorn
```

Database (nama sesuai `.env.example`):

```bash
mysql -u root -p < database/schema.sql
```

Isi `/opt/sistem-absensi-pwa/.env` (JANGAN commit; contoh nama variabel di `.env.example`):

```ini
APP_ENV=production
SECRET_KEY=<acak-min-32-karakter>
HOST=127.0.0.1
PORT=8000
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=sistem_absensi
DB_USER=sistem_absensi
DB_PASSWORD=<password-kuat>
APP_TIMEZONE=Asia/Jakarta
```

Buat user MySQL aplikasi + Admin pertama:

```bash
mysql -u root -p -e "CREATE USER 'sistem_absensi'@'127.0.0.1' IDENTIFIED BY '<password-kuat>'; GRANT SELECT,INSERT,UPDATE,DELETE ON sistem_absensi.* TO 'sistem_absensi'@'127.0.0.1';"
set -a; source /opt/sistem-absensi-pwa/.env; set +a
.venv/bin/python -m scripts.create_admin --username admin
```

## 4. Gunicorn + Nginx + HTTPS

```bash
sudo cp deploy/sman4-presensi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sman4-presensi
sudo cp deploy/sman4-presensi.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/sman4-presensi /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d smkn4.klikide.my.id
```

Cek: `https://smkn4.klikide.my.id/healthz` harus `{"status":"ok"}`.

## 5. Operasional wajib (jangan dilewati)

- **Finalisasi Alpa**: cron harian setelah cutoff, misal `30 16 * * *` jalankan
  `.venv/bin/python -m scripts.finalize_alpa` dengan env production (zona Asia/Jakarta).
- **Backup**: dump MySQL harian + arsip folder storage privat berkala; uji restore.
- **Log rotation**: log Gunicorn/Nginx dirotasi (logrotate) agar disk tidak penuh.
- **Akun demo**: 130 akun demo di database development TIDAK ikut ke production.
  Buat ulang akun nyata lewat Admin production (atau impor resmi), jangan dump database dev.
- **Kamera/GPS Android** wajib diuji ulang via URL HTTPS ini sebelum dipakai harian.
