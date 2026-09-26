# Sistem Presensi SMA Negeri 4 Lhokseumawe

Aplikasi presensi siswa berbasis PWA dengan verifikasi wajah, geofence sekolah, dan tantangan blink. Presensi dicatat dari perangkat siswa sendiri (kamera + lokasi), divalidasi di server, dan disimpan satu record per siswa per tanggal.

Dokumen ini berisi deskripsi produk dan cara menjalankan aplikasi, termasuk cara mengaksesnya dari perangkat lain (HP siswa, tablet, atau komputer kedua). Catatan teknis per-task ada di [docs/IMPLEMENTATION-LOG.md](docs/IMPLEMENTATION-LOG.md).

## Tentang Proyek

Presensi sekolah biasanya diisi secara manual: siswa mencatat sendiri, buku absen dibawa guru, dan data baru baru berguna setelah hari berakhir. Proyek ini menggantikan proses itu dengan satu aplikasi yang dipakai tiga pihak sekaligus:

- **Siswa** melakukan check-in dan check-out dari HP-nya sendiri pada hari sekolah.
- **Guru** memantau kehadiran kelasnya dan mencatat status manual bila diperlukan.
- **Admin** mengelola master data, jadwal, geofence, monitoring, ekspor, dan analitik.

Prinsip yang dipegang:

- **Backend adalah otoritas.** Waktu, tanggal presensi, jadwal efektif, role, lokasi, liveness, identitas wajah, dan hasil transaksi ditentukan server. UI hanya menampilkan state dari server; browser tidak memutuskan kelayakan sendiri.
- **Satu siswa, satu record per hari.** Dibatasi constraint `UNIQUE (student_id, attendance_date)`. Check-in dan check-out mengubah record yang sama.
- **Presensi wajib online.** Tidak ada antrean presensi offline, dan Service Worker hanya menyimpan shell serta aset publik — bukan foto biometrik atau respons sensitif.
- **Presensi tidak bisa diubah sepihak oleh Guru/Admin.** Guru hanya boleh menetapkan Izin/Sakit/Alpa bila belum ada auto-presence yang valid; status Hadir/Terlambat hasil sistem tidak dapat ditimpa.
- **Bukti dan jejak diaudit.** Foto evidence disimpan di protected storage (bukan public static), hanya dapat diakses sesuai role dan scope, dan reset/penggantian status tercatat di audit log.

### Peran Pengguna

| Peran | Halaman Utama | Kemampuan |
|---|---|---|
| **Siswa** | Dashboard mobile (bottom nav: Beranda, Riwayat, Profil) | Enrollment wajah 3 pose, check-in/check-out dengan kamera + lokasi, kalender kehadiran, riwayat bulanan, ubah kata sandi |
| **Guru / Wali Kelas** | Dashboard Guru (mobile: bottom nav; desktop: sidebar) | Monitoring presensi kelas tanggung jawab, daftar dan detail siswa, tetapkan Izin/Sakit/Alpa, lihat evidence |
| **Admin** | Dashboard desktop (sidebar 8 menu) | Master data siswa/guru/kelas/tahun ajaran, jadwal & exception, geofence, reset kata sandi dan wajah, monitoring semua kelas, ekspor XLSX, K-Means, audit log |

## Fitur Utama

- **Enrollment wajah** — tiga pose (`front`, `left`, `right`), satu wajah per pose, quality check, tantangan blink, suara shutter, dan umpan balik visual. Setelah tiga pose valid, model dilatih/diperbarui dan `face_registered` aktif. Siswa tanpa enrollment terkunci di gate dan tidak dapat melewati lewat URL.
- **Presensi check-in / check-out** — satu tombol CTA yang statusnya berubah antara check-in, menunggu jam pulang, check-out, atau selesai, mengikuti jadwal efektif dan record hari itu. Berisi kamera, lokasi (geofence), kualitas wajah, blink, dan hasil recognition yang harus cocok dengan siswa yang login.
- **Jadwal & exception** — prioritas resolution: exception kelas → exception sekolah → jadwal reguler, dengan tanggal, kelas, dan tahun ajaran yang relevan. Hari libur tidak menerima presensi dan tidak menghasilkan Alpa otomatis. Snapshot histori tetap benar meski jadwal berubah.
- **Geofence** — radius default 75 meter, dapat diubah Admin. Jarak dihitung di server dengan rumus Haversine; `accuracy` GPS disimpan bersama koordinat. Lokasi yang tidak andal ditolak dengan arahan retry.
- **Status manual Guru** — Izin/Sakit/Alpa hanya bila belum ada auto-presence atau status manual sah. Tindakan Guru yang datang lebih dulu mengalah terhadap kehadiran manual Guru lain yang berjalan bersamaan.
- **Monitoring & ekspor** — jurnal semua kelas dengan filter tanggal, kelas, status, nama/NISN, dan pagination; halaman detail siswa beserta histori; tautan bukti ke halaman evidence terlindungi; ekspor `.xlsx` (pandas + openpyxl).
- **Analitik K-Means** — dijalankan on-demand oleh Admin dengan K=3 pada fitur `attendance_percentage`, `late_count`, `alpha_count`. Centroid di-inverse-transform ke skala asli untuk interpretasi; run, fitur per siswa, dan centroid disimpan sebagai histori (run lama tidak ditimpa). Nomor cluster tidak boleh langsung diikat ke label tinggi/sedang/rendah.
- **PWA** — Web App Manifest + Service Worker untuk akses cepat dari layar utama. Navigasi privat, API, evidence, dan POST presensi selalu online-only; aset privat tidak pernah masuk cache.
- **Audit log** — reset wajah/kata sandi, status manual, perubahan jadwal/geofence, dan master data penting tercatat dengan pelaku dan waktu.
- **Finalisasi Alpa** — job yang berjalan setelah cutoff efektif untuk siswa yang wajib hadir dan belum punya auto-presence atau status manual sah. Idempoten (aman dijalankan ulang), dan status manual yang ada selalu menang.

## Teknologi

| Lapisan | Teknologi |
|---|---|
| Backend | Python 3.11, Flask 3.1 (application factory, blueprint modular) |
| Database | MySQL 8, PyMySQL, parameterized raw SQL (tanpa ORM kompleks) |
| Biometrik | opencv-contrib-python, Haar Cascade, LBPH, NumPy |
| Analitik | scikit-learn (`StandardScaler`, `KMeans`), pandas, openpyxl |
| Grafik | Chart.js (dilayani lokal, tanpa CDN) |
| Frontend | Server-rendered Jinja templates, TailwindCSS 4 (build via npm) |
| PWA | Web App Manifest + Service Worker |
| Produksi | Nginx → Gunicorn → Flask, MySQL privat, protected storage |

## Kebutuhan Sistem

- **Python 3.11** (diverifikasi pada Windows dengan 3.11.9; Ubuntu 22.04/24.04 juga dipakai di VPS).
- **MySQL 8** — lokal (Laragon/HeidiSQL) untuk pengembangan, service MySQL privat untuk produksi.
- **Node.js 20** — hanya untuk membangun CSS Tailwind (`npm run build:css`). Tidak dibutuhkan untuk menjalankan aplikasi.
- **`cloudflared`** (opsional) — hanya untuk uji coba akses lewat internet pada bagian [Cloudflare Quick Tunnel](#opsi-a--cloudflare-quick-tunnel-uji-coba). Tidak dipakai di produksi.
- **Git for Windows** (opsional) — hanya untuk membuat TLS lokal pada POC biometrik T04.

## Struktur Proyek

```
.
├── run.py                 # entry point pengembangan
├── config.py              # konfigurasi berbasis environment variable
├── requirements.txt
├── app/
│   ├── __init__.py        # application factory + guard
│   ├── database.py
│   ├── routes.py          # landing, /healthz, /service-worker.js
│   ├── role_routes.py     # dashboard per role
│   ├── auth/ student/ teacher/ admin/ attendance/ face/   # blueprint
│   ├── services/          # auth, attendance, face, geofence, schedule,
│   │                      # kmeans, export, audit, storage, liveness, dll.
│   ├── templates/         # auth/ student/ teacher/ admin/
│   └── static/            # css, js, audio, icons, illustrations, fonts
├── database/
│   ├── schema.sql         # instalasi baru (17 tabel)
│   ├── migrations/        # 001–015 untuk upgrade
│   └── seed.sql           # sengaja kosong; Admin dibuat via scripts.create_admin
├── scripts/               # create_admin, finalize_alpa, smoke T07–T29, dll.
├── tests/                 # unittest suite
├── deploy/                # DEPLOY_SMAN4.md, Nginx conf, systemd unit
└── storage/               # protected storage: faces, attendance, models
```

## Menjalankan di Komputer Sendiri

Perintah di bawah sudah diverifikasi pada Windows dengan Python 3.11.9. Untuk Linux/macOS, ganti `.venv\Scripts\python.exe` dengan `.venv/bin/python` dan set variabel environment sesuai shell Anda.

```powershell
# 1. Virtual environment + dependensi
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Konfigurasi environment (loader .env belum ada; set per terminal)
$env:APP_ENV = "development"
$env:SECRET_KEY = "dev-local-only"          # ganti di produksi
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_NAME = "sistem_absensi"
$env:DB_USER = "root"
$env:DB_PASSWORD = ""

# 3. Jalankan server
.venv\Scripts\python.exe run.py
```

Buka `http://127.0.0.1:5000/` untuk halaman awal, atau `http://127.0.0.1:5000/healthz` untuk readiness check (`{"status":"ok"}`). Nilai default konfigurasi ada di [`.env.example`](.env.example); jangan pernah commit file `.env` berisi kredensial.

### Menyiapkan Database

Database **belum** berisi akun apa pun. `seed.sql` sengaja kosong demi keamanan.

1. Jalankan MySQL (Laragon, HeidiSQL, atau service MySQL lokal/production).
2. **Instalasi baru:** import [`database/schema.sql`](database/schema.sql) — file ini membuat database dan 17 tabel. **Upgrade dari versi lama:** jalankan migration `001`–`015` di [`database/migrations/`](database/migrations) sesuai urutan nomor.
3. Buat akun Admin pertama secara interaktif (password tidak masuk shell history atau file SQL):

```powershell
.venv\Scripts\python.exe -m scripts.create_admin --username admin
```

4. Bangun CSS Tailwind (hanya perlu sekali, atau setiap kali token desain berubah):

```powershell
npm install
npm run build:css
```

## Akun dan Peran

- Akun **hanya** dibuat oleh Admin lewat halaman Master Data (Guru, Siswa, tahun ajaran, kelas). Akun demo di database development tidak boleh ikut ke production.
- **Username siswa = NISN.** Guru memakai username yang dibuat Admin.
- **Reset kata sandi** menghasilkan kata sandi sementara dengan `must_change_password=true`; pengguna wajib menggantinya sebelum masuk dashboard.
- **Siswa baru wajib enrollment wajah** sebelum bisa presensi. Selama enrollment belum selesai, siswa terkunci di gate — tidak bisa dilewati dengan mengakses URL lain. Setelah enrollment berhasil, session diakhiri dan siswa diminta login ulang.
- **Akun nonaktif** langsung ditolak pada setiap request, sehingga session lama tidak dapat dipakai.
- **Scope data:** Guru hanya mengakses kelas tanggung jawabnya; Guru kelas terkait dan Admin dapat melihat evidence; Admin tidak melakukan presensi sebagai siswa.

## Menjalankan di Perangkat Lain

Aplikasi ini dirancang untuk dipakai dari HP siswa. Bagian ini menjelaskan cara membuatnya dapat diakses dari perangkat lain.

### Prasyarat: HTTPS itu wajib

Browser hanya mengizinkan kamera (`getUserMedia`), GPS (`geolocation`), dan Service Worker (dasar PWA) pada **secure context** — yaitu `https://` atau `localhost`. Konsekuensinya:

- `http://192.168.x.x:5000` (HTTP di jaringan lokal): halaman **terbuka**, tetapi kamera, GPS, dan pasang-aplikasi **tidak berfungsi** di HP. Opsi ini hanya berguna untuk melihat tampilan.
- `https://<domain>` atau `https://*.trycloudflare.com` — kamera, GPS, PWA, dan presensi berfungsi.

Karena itu, ada dua jalur resmi: **tunnel HTTPS sementara untuk uji coba** dan **VPS + domain untuk produksi**.

### Opsi A — Cloudflare Quick Tunnel (uji coba)

Cara tercepat menguji aplikasi dari HP tanpa mengubah router atau membeli domain:

```powershell
# Terminal 1 — server lokal, hanya loopback agar tidak terekspos langsung
$env:APP_ENV = "development"
$env:SECRET_KEY = "dev-local-only"
$env:HOST = "127.0.0.1"
$env:PORT = "5000"
.venv\Scripts\python.exe run.py

# Terminal 2 — tunnel HTTPS (butuh cloudflared.exe di PATH)
cloudflared tunnel --url http://127.0.0.1:5000
```

Cloudflare mencetak URL seperti `https://random-words.trycloudflare.com`. Buka URL tersebut dari Chrome Android (melalui Wi-Fi atau data seluler), login, lalu uji izin kamera dan lokasi. Pastikan juga `http://127.0.0.1:5000/healthz` tetap merespons `ok` di Terminal 1.

**Batasan yang wajib diketahui:**

- **URL berubah setiap kali tunnel dimulai.** Bookmark tidak berlaku permanen; jalankan ulang `cloudflared` untuk URL baru.
- **Laptop harus tetap hidup dan online** selama pemakaian. Mematikan server = tunnel mati.
- **Frame wajah melewati jaringan Cloudflare.** Quick Tunnel bersifat sementara dan tidak cocok untuk data produksi atau penggunaan harian dengan data biometrik nyata.
- **`APP_ENV=development`** berarti cookie session tidak `Secure` dan `DEBUG` aktif. Jangan memakai mode ini untuk pemakaian nyata.

> Catatan: `scripts.run_t04_public` adalah launcher terpisah untuk POC biometrik terisolasi, **bukan** untuk aplikasi utama. Untuk aplikasi utama, gunakan langkah manual di atas.

### Opsi B — VPS + domain HTTPS (produksi)

Untuk pemakaian harian, jalankan di VPS Linux + domain + HTTPS. Panduan lengkap ada di [`deploy/DEPLOY_SMAN4.md`](deploy/DEPLOY_SMAN4.md). Ringkasan alurnya:

1. **VPS** — Ubuntu 22.04/24.04, RAM ≥ 2 GB, IP publik, dengan Nginx, Gunicorn, dan MySQL.
2. **DNS** — record `A` untuk subdomain (misal `smkn4.klikide.my.id`) → IP VPS, proxy **Proxied**. SSL/TLS mode **Full (strict)**.
3. **Aplikasi** — salin repo ke `/opt/sistem-absensi-pwa`, buat virtual environment, import `database/schema.sql`, isi file `.env` production (`APP_ENV=production`, `SECRET_KEY` acak ≥ 32 karakter, `DB_PASSWORD` kuat).
4. **HTTPS** — Gunicorn di `127.0.0.1:8000` (unit systemd sudah disiapkan di `deploy/sman4-presensi.service`), Nginx sebagai reverse proxy (`deploy/sman4-presensi.conf`), lalu `certbot --nginx` untuk sertifikat Let's Encrypt.
5. **Verifikasi** — `https://<domain>/healthz` harus mengembalikan `{"status":"ok"}`. Sebelum dipakai harian, uji kamera/GPS/PWA dari HP melalui URL HTTPS ini.

**Operasional wajib di produksi** (dijelaskan lengkap di `deploy/DEPLOY_SMAN4.md`):

- Job finalisasi Alpa via cron setelah cutoff efektif.
- Backup MySQL harian + arsip protected storage berkala, dan uji restore.
- Log rotation untuk Gunicorn dan Nginx.
- Kamera/GPS Android **wajib** diuji ulang lewat URL HTTPS produksi sebelum dipakai harian — pengujian sintetis di laptop tidak menggantikan ini.

### Memasang Aplikasi di Layar Utama (PWA)

Setelah aplikasi dapat diakses via HTTPS, siswa dapat memasangnya sebagai aplikasi mandiri:

- **Android / Chrome** — buka halaman login, banner "Pasang Presensi di layar utama" akan muncul; tekan **Pasang**. Alternatif: menu ⋮ → **Tambahkan ke layar utama**.
- **iOS / Safari** — iOS tidak menampilkan banner otomatis. Gunakan **Share → Tambah ke Layar Utama**.

PWA tetap membutuhkan koneksi internet saat dipakai (khususnya untuk presensi).

### Checklist Penggunaan dari HP

- [ ] URL yang dipakai adalah **HTTPS**.
- [ ] Izin **kamera** diberikan saat diminta.
- [ ] Izin **lokasi** diberikan; akurasi GPS cukup baik (server menolak lokasi yang kurang andal dengan arahan retry).
- [ ] Sinyal internet stabil.
- [ ] Login dengan akun sendiri (username siswa = NISN).
- [ ] Enrollment wajah sudah selesai sebelum presensi.
- [ ] Setelah selesai, tekan **Logout** agar HP tidak tertinggal dalam keadaan login dan bisa disalahgunakan oleh pengguna lain.

## Perintah Verifikasi

```powershell
# Suite unit penuh
.venv\Scripts\python.exe -m unittest discover -s tests -v

# Kompilasi dan konsistensi paket
.venv\Scripts\python.exe -m compileall -q app config.py run.py scripts
.venv\Scripts\python.exe -m pip check

# Build CSS dan cek sintaks Service Worker/JS
npm run build:css
node --check app/static/service-worker.js
node --check app/static/js/pwa-register.js
node --check app/static/js/attendance-checkin.js

# Smoke test per task (butuh MySQL)
.venv\Scripts\python.exe -m scripts.smoke_t07
# ... hingga smoke_t29 sesuai area yang diubah
```

Verifikasi yang sering dipakai per area perubahan:

```powershell
# Presensi (check-in, check-out, state, status manual)
.venv\Scripts\python.exe -m unittest discover -s tests -p test_attendance_checkin.py -v
.venv\Scripts\python.exe -m unittest discover -s tests -p test_attendance_checkout.py -v
.venv\Scripts\python.exe -m unittest discover -s tests -p test_teacher_manual_status.py -v

# Finalisasi Alpa (idempoten)
.venv\Scripts\python.exe -m unittest discover -s tests -p test_finalization_service.py -v

# K-Means
.venv\Scripts\python.exe -m unittest discover -s tests -p test_kmeans_clustering.py -v
.venv\Scripts\python.exe -m unittest discover -s tests -p test_kmeans_aggregation.py -v

# UI/UX dan kontras
.venv\Scripts\python.exe -m unittest discover -s tests -p test_ui.py -v
```

Finalisasi Alpa (dipakai oleh cron produksi):

```powershell
.venv\Scripts\python.exe -m scripts.finalize_alpa            # hari ini (Asia/Jakarta)
.venv\Scripts\python.exe -m scripts.finalize_alpa --date 2026-09-22   # backfill
.venv\Scripts\python.exe -m scripts.finalize_alpa --dry-run  # hitung saja, tidak menulis
```

Contoh cron produksi (VPS Linux; sesuaikan path):

```cron
*/10 6-18 * * 1-6 cd /opt/sistem-absensi && .venv/bin/python -m scripts.finalize_alpa >> logs/finalize_alpa.log 2>&1
```
