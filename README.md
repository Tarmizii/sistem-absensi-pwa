# sistem-absensi-pwa

Sistem presensi siswa SMA Negeri 4 Lhokseumawe. Status saat ini: T00–T30 selesai; redesign T31 diterapkan dan diverifikasi sebagian. Penutupan T31 masih menunggu audit visual semua route/state, zoom 200%, dan baseline screenshot yang tidak tersimpan sebelum perubahan; T32–T35 menunggu T31. T04 diterima pengguna dengan batasan yang tercatat.

- [PRD](PRD_Sistem_Presensi_SMA_Negeri_4_Lhokseumawe.md): kebutuhan dan batasan produk.
- [Panduan pengembangan](AGENTS.md): aturan kerja dan kontrak implementasi.
- [Rencana task](TASK_PLAN.md): 36 task berurutan, dependensi, kriteria selesai, dan pencatatan progres.

## Menjalankan fondasi lokal

Perintah berikut sudah diverifikasi pada Windows dengan Python 3.11.9:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:APP_ENV = "development"
$env:SECRET_KEY = "dev-local-only"
.venv\Scripts\python.exe run.py
```

Buka `http://127.0.0.1:5000/` untuk halaman awal atau `http://127.0.0.1:5000/healthz` untuk readiness check. File `.env.example` hanya menjadi referensi nama konfigurasi pada tahap ini; loader `.env` belum ditambahkan karena belum diperlukan oleh fondasi T01.

Verifikasi yang lulus pada T01: application-factory test, halaman `/` HTTP 200, `/healthz` HTTP 200, `pip check`, `compileall`, dan smoke test server development.

## Menyiapkan database T02

1. Jalankan MySQL melalui Laragon atau server development setempat.
2. Import [database/schema.sql](D:/ProjectWeb/sistem-absensi-pwa/database/schema.sql) melalui HeidiSQL. File ini membuat database dan tabel dasar akun, audit, Guru, Siswa, kelas, penempatan, serta jadwal, tetapi tidak membuat akun default.
3. Isi variabel `DB_*` dari `.env.example` pada environment PowerShell yang sedang digunakan.
4. Buat Admin pertama secara interaktif sehingga password tidak masuk shell history atau file SQL:

```powershell
.venv\Scripts\python.exe -m scripts.create_admin --username admin
```

Password akan diminta dua kali secara tersembunyi. `DB_PASSWORD` wajib tersedia untuk environment production. Import schema, koneksi PyMySQL, rollback, dan unique constraint sudah diverifikasi pada database `sistem_absensi` melalui koneksi lokal `127.0.0.1:3306`.

## Autentikasi T03

T03 menyediakan `/login`, `/logout`, `/change-password`, dashboard awal untuk tiga role, guard akses backend, CSRF untuk request mutasi, cookie session yang dilindungi, dan pembatasan dasar percobaan login. Akun nonaktif diperiksa ulang pada setiap request sehingga session lama tidak dapat dipakai.

Jalankan verifikasi lokal dari root repository dengan virtual environment:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app config.py run.py scripts
.venv\Scripts\python.exe -m pip check
```

Throttle login T03 masih bersifat per-process untuk fondasi lokal. Sebelum deployment multi-worker, gantikan dengan limiter bersama yang memakai storage terpusat.

## POC biometrik T04

Dependensi OpenCV contrib dan NumPy dipasang untuk POC terisolasi. POC hanya memeriksa preprocessing grayscale/equalize/resize, sinyal brightness-sharpness, Haar face/eye detection seam, state blink provisional, serta API LBPH dengan gambar sintetis:

```powershell
.venv\Scripts\python.exe -m scripts.run_face_poc
```

Catatan keputusan, keterbatasan, dan prosedur uji Android/HTTPS ada di [docs/T04_BIOMETRIC_POC.md](D:/ProjectWeb/sistem-absensi-pwa/docs/T04_BIOMETRIC_POC.md). Hasil Android/Chrome T04 diterima untuk melanjutkan pekerjaan, tetapi baru menangkap dua pose dan belum menguji prediksi; kualitas/blink Haar tetap provisional dan bukan bukti kesiapan biometrik produksi.

### Menjalankan uji T04 melalui tautan publik

Cloudflare Quick Tunnel menerbitkan URL HTTPS sementara. Android dapat memakai Wi-Fi atau data seluler; laptop harus tetap hidup dan terhubung ke internet. Pasang `cloudflared.exe` satu kali, lalu:

```powershell
.venv\Scripts\python.exe -m scripts.setup_t04_android
.venv\Scripts\python.exe -m scripts.run_t04_public start
```

Terminal menampilkan URL `trycloudflare.com` yang sudah diverifikasi dan kode akses terpisah. Buka URL dari Chrome Android, masukkan kode, baca pemberitahuan bahwa frame melewati jaringan Cloudflare, centang persetujuan peserta, lalu nyalakan kamera. Pilih satu peserta untuk tiga pose; pilih orang sama/berbeda dan kondisi uji saat membaca distance. Unduh JSON laporan dari bagian Catatan percobaan. Jangan sertakan foto wajah di laporan.

```powershell
.venv\Scripts\python.exe -m scripts.run_t04_public status
.venv\Scripts\python.exe -m scripts.run_t04_public stop
```

Server hanya mendengarkan loopback pada port 8443. Tunnel memakai HTTP/2 dan mempercayai CA lokal yang dibuat untuk origin; endpoint publik hanya diumumkan setelah halaman, CSS, dan JavaScript merespons. Launcher mencatat proses yang dibuatnya dan hanya menghentikan proses tersebut. Log, URL aktif, kode akses, kunci, dan sertifikat disimpan di `instance/t04/` yang diabaikan Git. Sampel/model ada di memori hingga sesi berakhir, batas 30 menit, atau server dihentikan.

Untuk uji jaringan Wi-Fi lokal tanpa tautan publik dan tanpa tunnel, tersedia `.venv\Scripts\python.exe -m scripts.run_t04_android` (perangkat harus memasang sertifikat CA lokal). Mengakses browser HP melalui IP publik membawa frame wajah melewati layanan tunnel; gunakan peserta yang menyetujui alur tersebut. Ini uji kelayakan T04, bukan enrollment presensi produksi; auto-capture, challenge server, storage, dan threshold final dikerjakan pada T15–T16.

## Status presensi T17

Migration [012_create_attendance_records.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/012_create_attendance_records.sql) membuat tabel `attendance_records` dengan `UNIQUE (student_id, attendance_date)`, sisi check-in/check-out, snapshot `class_id`, `status` (`present`/`late`/`permit`/`sick`/`absent`, NULL sebelum ada presensi), dan `status_source`. `Belum Absen` serta `Libur` tidak pernah disimpan — keduanya berasal dari service dan schedule engine. Instalasi baru memakai [database/schema.sql](D:/ProjectWeb/sistem-absensi-pwa/database/schema.sql).

`app/services/attendance_state_service.py` menentukan satu CTA per hari dari record tersimpan dan jadwal efektif (`resolve_schedule`). Status manual/record tersimpan tetap terlihat jika jadwal kemudian berubah atau tidak tersedia; untuk check-in tanpa checkout pada jadwal yang sudah berubah, aksi dinonaktifkan sampai aturan jadwal tersedia. Tanpa record, service membedakan tanpa jadwal, libur, waktu sebelum/mulai/terlambat/tertutup. Label CTA mengikuti FR-STU-03 (`Presensi Masuk`, `Pulang mulai HH:MM`, `Presensi Pulang`, `Presensi Selesai`). Batas waktu memakai `evaluate_checkin` dan `can_checkout` yang sama dengan service jadwal, jadi awal dan cutoff inklusif.

Dashboard `/student/dashboard` memanggil `get_student_day_state` lalu merender `student/dashboard.html`. Tombol selalu memakai `cta_enabled` dari server; state disabled menampilkan `reason` sehingga siswa tahu kapan presensi dibuka. Browser tidak menentukan kelayakan sendiri. Submit presensi nyata (kamera, lokasi, LBPH) dikerjakan T18–T19.

Verifikasi T17:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_attendance_state.py -v
.venv\Scripts\python.exe -m scripts.smoke_t17
```

Smoke T17 memakai data sintetis dan menghapus seluruh baris uji setelah selesai.

## Dashboard, kalender, dan profil Siswa T21

`GET /student/attendance-state` mengembalikan state harian yang aman untuk akun pada session; identitas dari parameter URL ditolak. `/student/history` menampilkan hanya bulan berjalan menurut `Asia/Jakarta`; record tersimpan menjadi sumber utama meskipun jadwal berubah, sedangkan hari tanpa record memakai penempatan kelas dan resolver jadwal untuk membedakan Libur, Tidak ada jadwal, dan Belum Absen. Tanggal ke depan diberi label Belum berlangsung. Detail tidak mengirim foto, storage key, koordinat, accuracy, score wajah, atau metadata liveness.

Dashboard menampilkan identitas/kelas, tanggal dan jam, status, jadwal efektif, serta CTA server. State diperbarui tiap 30 detik saat halaman aktif dan kamera tidak berjalan, juga setelah halaman kembali atau koneksi pulih. Ketika respons frame hilang setelah server commit, browser menghentikan kamera/frame, mengunci CTA, lalu tombol **Cek status presensi** memeriksa aksi yang sama. Bila check-in sudah tersimpan, halaman memuat ulang state tersebut; browser tidak memulai check-out otomatis. Profil Siswa memuat nama, NISN, kelas/tahun ajaran, ubah password, dan logout.

Verifikasi T21 pada Windows:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m scripts.smoke_t21
node scripts/test_attendance_recovery.mjs
node --check app/static/js/attendance-checkin.js
node --check app/static/js/attendance-state.js
npm run build:css
```

Pada sesi implementasi T21, 195 unit test lulus; smoke MySQL T21 dan smoke regresi T16–T20 lulus berurutan dengan cleanup. Harness Node mensimulasikan commit sukses dengan respons frame hilang dan memastikan pengecekan state menemukan check-in tanpa aksi/frame berikutnya. Uji Android kamera/GPS presensi tetap masuk T32.

## Monitoring Guru T22

Dashboard `/teacher/dashboard` menampilkan ringkasan roster aktif kelas hari ini dan daftar tindak lanjut untuk Alpa, belum masuk setelah cutoff, serta belum pulang setelah jadwal pulang. Guru dapat membuka jurnal bulanan di `/teacher/attendance`, roster di `/teacher/students`, dan kalender histori lintas bulan di `/teacher/students/<id>`. Jurnal dan roster mendukung filter nama/NISN serta pagination server-side 25 baris.

Setiap pembacaan memeriksa penugasan kelas yang berlaku saat request. Histori memakai snapshot `attendance_records.class_id`; kelas lama tetap bisa dibaca selama masih ditugaskan, sedangkan record tanpa snapshot kelas tidak muncul bagi Guru. Akun siswa nonaktif tetap tersedia pada histori/roster kelas. Dashboard ringkasan mengikuti roster aktif dan histori hanya menampilkan status yang benar-benar tersimpan. Halaman ini baca-saja; foto evidence belum ditampilkan dan masuk T23. Tidak ada migration atau dependency baru.

Verifikasi T22:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m scripts.smoke_t17
.venv\Scripts\python.exe -m scripts.smoke_t18
.venv\Scripts\python.exe -m scripts.smoke_t19
.venv\Scripts\python.exe -m scripts.smoke_t20
.venv\Scripts\python.exe -m scripts.smoke_t21
.venv\Scripts\python.exe -m scripts.smoke_t22
npm run build:css
node --check app/static/js/attendance-checkin.js
node --check app/static/js/attendance-state.js
git diff --check
```

Pada verifikasi T22, 200 unit test dan seluruh smoke T17–T22 lulus berurutan; fixture dibersihkan melalui `finally` pada setiap smoke. Harness respons hilang T21, build CSS, pemeriksaan sintaks JavaScript, kompilasi Python, dan `git diff --check` juga lulus. Pemeriksaan browser visual manual pada ukuran mobile/desktop belum dilakukan; halaman dan navigasi diuji lewat Flask test client serta smoke MySQL. Uji kamera/GPS Android tetap mengikuti T32.

## Evidence presensi T23

Guru yang sedang ditugaskan pada kelas snapshot dapat membuka detail evidence melalui histori. Admin dapat membuka evidence terbaru dari detail Siswa. Detail menampilkan foto masuk/pulang bila tersedia, waktu WIB, dan status ketersediaan lokasi beserta accuracy yang tersimpan. Koordinat, score wajah, dan storage key tidak dikirim ke HTML. Otorisasi dicek ulang pada setiap request gambar; hanya key dari record yang lolos scope yang dapat dipakai. File privat yang hilang atau key rusak memberi 404 tanpa path filesystem. Semua respons privat memakai `Cache-Control: no-store`.

Verifikasi T23:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_attendance_evidence.py -v
.venv\Scripts\python.exe -m scripts.smoke_t23
.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run build:css
.venv\Scripts\python.exe -m pip check
```

Smoke MySQL sintetis menguji penugasan Guru yang berubah saat runtime, record tanpa snapshot kelas, akses Admin, pembacaan foto privat, dan cleanup. Tujuh tes route dan 207 unit test lulus. Pemeriksaan visual browser untuk halaman evidence masuk verifikasi UI T31; kamera/GPS Android tetap pada T32. T23 tidak menambah migration atau dependency.

## Status manual Guru T24

Detail Siswa Guru menyediakan form status manual untuk tanggal hari ini menurut waktu server WIB. Aksi hanya tersedia bagi Guru yang sedang ditugaskan pada kelas aktif dan Siswa yang aktif; hari libur menolak perubahan. Izin dan Sakit wajib memiliki keterangan. Alpa hanya dapat dibuat sesudah cutoff efektif; status Alpa dari job dapat dikoreksi pada hari yang sama. Hadir/Terlambat otomatis atau record dengan check-in tidak dapat diubah. Status yang dibuat Guru dapat dibatalkan sampai cutoff jika belum ada check-in otomatis.

Penyimpanan membaca ulang record di dalam transaksi dengan row lock agar status Guru, check-in, dan finalisasi Alpa yang berdekatan tidak saling menimpa. Transisi enum status diaudit; teks keterangan tidak disalin ke audit. Endpoint mengikuti CSRF dan scope kelas server-side.

Verifikasi T24:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_teacher_manual_status.py -v
.venv\Scripts\python.exe -m unittest discover -s tests -p test_audit.py -v
.venv\Scripts\python.exe -m scripts.smoke_t24
.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run build:css
.venv\Scripts\python.exe -m pip check
```

Enam tes status manual dan enam tes audit terkait lulus; suite penuh memiliki 214 tes lulus. Smoke MySQL T20, T22, T23, dan T24 dijalankan berurutan dengan cleanup. Smoke T24 menjalankan race dua koneksi antara status Guru dan finalisasi Alpa serta memverifikasi hanya satu record per Siswa/tanggal dan transisi audit yang aman. Uji browser lintas ukuran masuk T31; T24 tidak menambah migration atau dependency.

## Monitoring Admin T25

`/admin/attendance` menyediakan jurnal semua kelas dengan filter tanggal, kelas, status tersimpan, nama/NISN, dan pagination stabil 25 baris. Nama Siswa membuka detail profil beserta histori record untuk bulan yang dipilih; tautan bukti menuju halaman evidence terlindungi T23. Navigasi Monitoring Presensi kini aktif. Semua halaman bersifat privat dan memakai `no-store`.

Ringkasan memakai tanggal dan kelas terpilih, tidak berubah ketika status/pencarian jurnal berubah, dan dihitung di luar batas halaman. Hari ini seluruh hitungan dibatasi pada roster akun aktif di kelas/tahun ajaran aktif: status mengikuti record tersimpan, sedangkan siswa tanpa status tersimpan dihitung sebagai Belum Absen. Tidak ada Alpa yang disimpulkan dari record kosong, termasuk saat hari libur. Untuk tanggal lampau hanya status tersimpan dihitung, tanpa merekonstruksi roster atau menebak Alpa. Kelas historis tetap bisa dipilih untuk membaca record tersimpan. Kegagalan database menampilkan aksi muat ulang dengan filter dipertahankan.

Verifikasi T25:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_admin_attendance.py -v
.venv\Scripts\python.exe -m scripts.smoke_t25
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app scripts tests
.venv\Scripts\python.exe -m pip check
git diff --check
```

Lima tes route T25 lulus. Smoke MySQL memeriksa hitungan lintas kelas, roster aktif, libur kelas, filter, batas 25 baris, histori tersimpan dan status kosong, tautan evidence, empty state, serta field privat; fixture dibersihkan. Smoke regresi T20, T22, T23, T24, dan T25 serta seluruh 219 unit test lulus berurutan. Build CSS tidak dijalankan karena tidak ada perubahan CSS/JavaScript atau utility Tailwind baru. Pemeriksaan visual browser masuk T31; tidak ada migration atau dependency baru.

## Ekspor dan audit Admin T26

Jurnal `/admin/attendance` menyediakan tautan Unduh Excel yang mempertahankan filter tanggal, kelas, status, dan pencarian. `/admin/attendance/export.xlsx` mengekspor seluruh baris cocok tanpa batas pagination 25 dan hanya memuat tanggal, kelas, identitas siswa, status/sumber, waktu masuk/pulang, serta keterangan. Teks database yang dapat menyerupai formula Excel ditulis sebagai teks biasa. Foto, koordinat, score wajah, liveness, dan storage key tidak diekspor.

Admin dapat membuka `/admin/audit-logs` untuk mencari pelaku, menyaring rentang waktu/aksi, dan menelusuri 25 baris per halaman. Tampilan audit menghilangkan metadata mentah sehingga secret atau data biometrik tidak dirender. Dua route memeriksa role Admin pada server dan memakai respons privat `no-store`.

Verifikasi T26:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_admin_exports_audit.py -v
.venv\Scripts\python.exe -m scripts.smoke_t25
.venv\Scripts\python.exe -m scripts.smoke_t26
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app scripts tests
.venv\Scripts\python.exe -m pip check
git diff --check
```

Delapan tes terarah ekspor/audit lulus. Smoke T25 dan T26 lulus berurutan dengan cleanup; T26 memeriksa workbook 27 baris setelah header, semua filter, formula-like text yang tersimpan sebagai teks, privasi kolom, filter audit serta pagination 25. Semua 227 unit test lulus, bersama `compileall`, `pip check`, dan `git diff --check`. Dependency baru: `pandas==3.0.6` dan `openpyxl==3.1.5`; tidak ada migration. T31 mencakup review visual browser.

## Snapshot hari dan agregasi analitik T27

Migration [013_create_attendance_day_snapshots.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/013_create_attendance_day_snapshots.sql) menambahkan snapshot per kelas/tanggal. Check-in, status manual, atau finalisasi pertama yang menggunakan tanggal tersebut membekukan apakah kelas wajib hadir; insert berikutnya tidak mengubah hasil. Untuk database yang sudah ada, pilih database aplikasi di HeidiSQL lalu jalankan migration 013 setelah 012. Instalasi baru menggunakan `database/schema.sql`.

Untuk tahun ajaran yang telah berakhir, isi tanggal tanpa snapshot menggunakan `.venv\Scripts\python.exe -m scripts.backfill_attendance_day_snapshots` atau tambahkan `--year-id <ID>`. Perintah aman dijalankan ulang: snapshot lama dipertahankan dan tanggal yang dibuat dari resolver jadwal saat ini bertanda `reconstructed`. Rekonstruksi tersebut bukan bukti histori jadwal yang tidak pernah tersimpan.

Service agregasi menerima periode lampau dalam satu tahun ajaran yang berakhir. Setiap tanggal periode untuk kelas pada penempatan siswa harus mempunyai snapshot dan setiap hari wajib hadir harus mempunyai status tersimpan; status kosong menolak seluruh periode dan tidak disimpulkan sebagai Alpa. Formula PRD dipakai: `effective_days = scheduled_school_days - permit - sick`, persentase `(present + late) / effective_days * 100`, `late_count` dan `alpha_count` dihitung dari status tersimpan. Jika `effective_days` nol, siswa ditandai tidak layak analisis; akun siswa nonaktif tetap masuk melalui penempatan historisnya.

Verifikasi T27:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_kmeans_aggregation.py -v
.venv\Scripts\python.exe -m scripts.smoke_t27
.venv\Scripts\python.exe -m scripts.smoke_t18
.venv\Scripts\python.exe -m scripts.smoke_t19
.venv\Scripts\python.exe -m scripts.smoke_t20
.venv\Scripts\python.exe -m scripts.smoke_t24
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app scripts tests
.venv\Scripts\python.exe -m pip check
git diff --check
```

Sembilan tes T27 lulus. Smoke T27 membuktikan backfill 6 hari idempotent, hari libur tidak dihitung, perubahan jadwal tidak menimpa snapshot, hasil manual 66,6667%, siswa nonaktif tetap ada dan denominator nol ditandai tidak layak; periode dengan status wajib yang kosong ditolak. Smoke check-in, check-out, finalisasi, dan status manual lulus. Semua 236 unit test lulus pada saat T27 ditutup. Migration 013 diterapkan ke database development lokal. Tidak ada UI/chart atau dependency baru pada T27.

## Mesin dan histori K-Means T28

`scikit-learn==1.9.1` menjalankan K-Means K=3 pada fitur terstandardisasi (`random_state=42`, `n_init=10`). Centroid dikembalikan ke skala aslinya dan diberi label tinggi/sedang/rendah menurut arah fitur kehadiran, terlambat, dan Alpa. Dataset kurang dari tiga siswa layak atau tiga pola berbeda ditolak.

Migration [014_create_kmeans_run_history.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/014_create_kmeans_run_history.sql) membuat histori run, fitur per siswa, dan centroid. Ketiganya tersimpan dalam satu transaksi; run lama tidak ditimpa. Untuk database yang sudah ada, jalankan migration 014 setelah 013 di HeidiSQL. Instalasi baru memakai schema penuh.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_kmeans_clustering.py -v
.venv\Scripts\python.exe -m scripts.smoke_t28
```

Smoke sintetis membuktikan hasil run berulang stabil, histori lama tetap, siswa tidak layak tetap tercatat tanpa cluster, dan kegagalan setelah insert hasil menggulung balik transaksi. Log traceback pada kasus terakhir memang berasal dari kegagalan sintetis yang sengaja disuntikkan.

## Halaman analisis Admin T29

Admin membuka **Analitik** untuk memilih tahun ajaran yang sudah berakhir dan periode lampau. Periode belum lengkap ditolak sebelum run tersimpan. Histori 25 baris membuka detail run dari data tersimpan, termasuk versi formula/label, centroid asli, hasil siswa, dan penanda snapshot rekonstruksi. Chart.js 4.5.1 dilayani dari bundle lokal `app/static/js/vendor/`, tanpa CDN. Grafik memisahkan satuan persentase kehadiran dari jumlah terlambat/Alpa; tabel memakai nilai centroid yang sama.

Migration 015 menambah hash token submit dengan unique key pada MySQL untuk mencegah run ganda saat request paralel atau diulang. Tombol browser dinonaktifkan sesudah submit; token form yang kedaluwarsa menghasilkan HTTP 409. Untuk database dengan migration 014, jalankan [015_add_kmeans_submission_key.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/015_add_kmeans_submission_key.sql). Instalasi baru telah mencakup kolom ini di schema.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_admin_kmeans.py -v
.venv\Scripts\python.exe -m scripts.smoke_t29
node --check app/static/js/admin-kmeans.js
npm run build:css
```

Tes route memeriksa role, nonce sekali pakai, kegagalan periode/penyimpanan, run hilang, dan data grafik/tabel. Smoke MySQL membuat serta membuka run dengan akun sintetis, mengulang request key untuk membuktikan satu run, dan menghapus fixture. Pemeriksaan tampilan lintas viewport dilakukan pada T31.

## PWA dan koneksi T30

Manifest lokal tersedia di `/static/manifest.webmanifest`; start URL `/login?source=pwa` mengarahkan pengguna baru ke autentikasi dan mengembalikan session aktif ke dashboard sesuai role. Aplikasi mendaftarkan `/service-worker.js` dengan scope `/`. Worker hanya menyimpan daftar eksplisit berisi CSS, script status jaringan, manifest, dua ikon, dan halaman offline umum. Navigasi selalu meminta server; saat permintaan navigasi gagal, browser mendapat halaman offline tanpa data pengguna. API, halaman privat, foto, request presensi, logout POST, dan request lintas origin tidak dimasukkan ke cache atau antrean.

Versi cache saat ini `presensi-shell-v8`; allowlist mencakup CSS, script status jaringan, manifest, font lokal, dua ikon, sembilan aset ilustrasi publik (tujuh WebP v2 dan dua SVG sementara), dan halaman offline umum. Bila daftar aset offline atau kontennya berubah, naikkan versinya di `app/static/service-worker.js`. Aktivasi menghapus versi lama dengan prefix aplikasi saja, bukan cache service worker lain pada origin yang sama. Banner global memberi tahu bahwa presensi memerlukan koneksi dan menyediakan tombol **Muat ulang** setelah online kembali. Status presensi siswa tetap diperbarui oleh alur T21.

Verifikasi T30 berbasis tes kode:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_pwa -v
node --test tests/test_service_worker.mjs tests/test_pwa_network.mjs
node --check app/static/service-worker.js
node --check app/static/js/pwa-register.js
npm run build:css
```

Tes menjalankan worker dengan Cache Storage sintetis untuk mengecek allowlist, fallback offline, navigasi privat yang tetap online-only, API/foto/logout/presensi yang tidak di-cache, serta pembersihan cache versi lama. Tes route memastikan manifest dan icon lokal valid serta worker diberi `Service-Worker-Allowed: /`. Belum ada bukti installability/offline dari Android nyata; itu bagian uji perangkat T32.

Regresi penutupan T30: 253 unit test lulus; smoke MySQL T25–T29 dijalankan berurutan dan seluruh cleanup lulus. `compileall`, `pip check`, lima tes Node Service Worker/banner, syntax check JavaScript, build CSS, dan `git diff --check` juga lulus. Android nyata belum diuji pada tahap ini.

### Audit terarah T23–T30 (26 September 2026)

Audit kode menemukan dan memperbaiki enam masalah ketepatan data/akses: koreksi status manual kini menolak record dengan snapshot kelas berbeda atau kosong; analisis K-Means menolak record yang snapshot kelasnya tidak cocok dengan penempatan dan status tersimpan yang bertentangan dengan snapshot hari libur/tanpa jadwal; angka centroid pecahan tidak dipotong saat ditampilkan; filter tanggal audit di batas kalender dan nomor halaman histori K-Means yang terlalu panjang menghasilkan HTTP 400, bukan error server. Tidak ada perubahan schema.

Tes regresi menutup tiap temuan, dan tes evidence ditambah untuk akses setelah logout serta file hilang, malformed, atau kategori yang salah. Simulasi Service Worker kini memeriksa cache hit saat offline dan menolak query string, origin lain, serta script di luar allowlist. Smoke MySQL T17–T29 mengembalikan PASS dan cleanup=ok; setelah MySQL tersedia lagi, suite penuh pascaperbaikan lulus **261 tes**, kemudian smoke T24 dan T27 yang mencakup pemeriksaan record tanpa snapshot kelas/ketidaksesuaian status juga lulus dengan cleanup. Enam tes Node PWA, pemeriksaan pemulihan respons transaksi, `compileall`, pemeriksaan syntax JavaScript, dan `git diff --check` lulus. Pemeriksaan tersebut mendahului redesign T31; untuk hasil T31 lihat catatan di bawah. Verifikasi perangkat Android tetap mengikuti T32.

## Redesign visual T31

Template produk Siswa, Guru, Admin, autentikasi, profil, enrollment, evidence, monitoring, dan analitik mengikuti latar cream, panel putih, aksen coral/mint/kuning, teks ink, kartu membulat, dan CTA coral gelap. Status memakai label selain warna. Plus Jakarta Sans variable dibundel sebagai font lokal dengan lisensi OFL di `app/static/fonts/` dari [repositori Google Fonts](https://github.com/google/fonts/tree/main/ofl/plusjakartasans); tidak ada font yang dimuat dari layanan eksternal. Tujuh ilustrasi WebP v2 serta dua SVG sementara ditempatkan pada sambutan, presensi, pengantar enrollment, keberhasilan enrollment yang dikonfirmasi server, bantuan lokasi, dan kondisi kosong/offline. Ilustrasi sukses tidak ditampilkan hanya karena tiga pose tersimpan. Dashboard Admin menautkan area kerja aktif tanpa statistik contoh. Navigasi role, URL, data, guard, alur kamera, dan selector JavaScript dipertahankan; halaman POC T04 mempertahankan warna dan font semula. Cache Service Worker naik ke `presensi-shell-v7` dan tetap terbatas pada aset publik.

CSS dibangun dengan Tailwind lokal. Suite penuh lulus **272 tes**; enam tes Node PWA, tes pemulihan submit presensi, pemeriksaan syntax JavaScript yang berubah, dan `git diff --check` lulus. Tes rasio mendapat 6.15:1 untuk teks putih pada CTA, 5.31:1 untuk muted pada cream, 5.15:1 untuk tinta di panel coral, dan 4.51–4.88:1 pada badge status; tinta pada panel mint/kuning/lime mencapai 7.20:1 atau lebih. Screenshot fixture sintetis setelah perubahan meninjau Siswa 360px, Guru 768px, Admin 1024px, serta ilustrasi Guru pada desktop. Tabel Admin 1440px dan kalender Siswa 390px juga telah diperiksa sebelumnya.

T31 masih terbuka: tangkapan baseline sebelum perubahan tidak tersimpan; pemeriksaan zoom teks 200%, semua route/state, dan alur keyboard menyeluruh belum ditutup. T32 tetap menjadi verifikasi perangkat nyata.

## UI T05

UI T05 memakai Tailwind CSS v4 lokal dengan build yang dapat diulang:

```powershell
npm install
npm run build:css
```

Shell role tersedia pada `/admin/dashboard`, `/teacher/dashboard`, dan `/student/dashboard` setelah login. Token visual serta keputusan responsif dicatat di [DESIGN.md](D:/ProjectWeb/sistem-absensi-pwa/DESIGN.md), sedangkan perilaku navigasi dan state ada di [UX-CONTRACT.md](D:/ProjectWeb/sistem-absensi-pwa/UX-CONTRACT.md).

## Password dan profil T06

Akun dengan `must_change_password=1` selalu diarahkan ke `/change-password` sebelum dapat membuka dashboard atau profil. Form memeriksa password saat ini, panjang minimum 12 karakter, dan konfirmasi sebelum menyimpan hash baru serta menghapus flag sementara. Profil tersedia sesuai role di `/admin/profile`, `/teacher/profile`, dan `/student/profile`; `/profile` mengarahkan ke profil role aktif. Logout tetap menggunakan POST dengan CSRF.

Verifikasi T06 dijalankan bersama suite fondasi:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Audit dan protected storage T07

Migration [002_create_audit_logs.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/002_create_audit_logs.sql) menambahkan audit actor/action/target/metadata dengan foreign key ke pengguna. Perubahan password dan audit berada dalam satu transaksi, tanpa menyimpan password, hash, atau payload biometrik di metadata. Session memakai credential stamp sehingga sesi lama dicabut setelah password berubah.

Folder `storage/faces`, `storage/attendance`, dan `storage/models` berada di luar `static`, menggunakan nama acak dari server, dan tidak mempunyai endpoint file publik. Gambar kamera dibatasi ukuran, MIME, dimensi, jumlah pixel, dan hasil decode; metadata gambar dibersihkan sebelum disimpan. Terapkan schema penuh atau migration 002 sebelum menjalankan aplikasi:

```powershell
.venv\Scripts\python.exe -m scripts.smoke_t07
```

Smoke test memakai akun sintetis sementara dan membersihkannya setelah selesai. Otorisasi file berdasarkan kelas baru ditambahkan bersama fitur evidence T23.

## Kelola Guru T08

Admin dapat membuka `/admin/teachers` untuk mencari, menambah, melihat detail, mengedit, menonaktifkan, dan mereset password akun Guru. Akun dan profil Guru dibuat dalam satu transaksi. Password sementara hanya ditampilkan pada respons sukses, memaksa perubahan saat login pertama, dan tidak masuk audit log.

Migration [003_create_teachers.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/003_create_teachers.sql) perlu diterapkan setelah migration 002, atau gunakan [database/schema.sql](D:/ProjectWeb/sistem-absensi-pwa/database/schema.sql) untuk instalasi baru. Smoke test lokal menggunakan data sintetis dan membersihkan data setelah selesai:

```powershell
.venv\Scripts\python.exe -m scripts.smoke_t08
```

## Kelola Siswa T09

Admin dapat membuka `/admin/students` untuk mencari, menambah, melihat detail, mengedit, menonaktifkan, dan mereset password akun Siswa. NISN disimpan sebagai teks sehingga angka nol di depan tetap utuh dan selalu disinkronkan dengan username akun. Akun baru dimulai dengan `face_registered=false`; password sementara hanya tampil pada respons sukses dan memaksa perubahan saat login pertama.

Migration [004_create_students.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/004_create_students.sql) perlu diterapkan setelah migration 003, atau gunakan [database/schema.sql](D:/ProjectWeb/sistem-absensi-pwa/database/schema.sql) untuk instalasi baru. Smoke test lokal menggunakan data sintetis dan membersihkan data setelah selesai:

```powershell
.venv\Scripts\python.exe -m scripts.smoke_t09
```

## Tahun ajaran, kelas, dan penempatan T10

Admin dapat membuka `/admin/classes` untuk mengelola kelas, wali kelas, dan roster Siswa. Periode tahun ajaran dikelola dari `/admin/academic-years`; hanya periode yang dipilih sebagai aktif yang menjadi default operasional. Migration [005_create_academic_years_classes_enrollments.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/005_create_academic_years_classes_enrollments.sql) menambahkan tiga tabel master dan constraint satu penempatan Siswa per tahun ajaran. Relasi tidak dihapus saat kelas dinonaktifkan agar histori tetap tersedia.

```powershell
.venv\Scripts\python.exe -m scripts.smoke_t10
```

Baseline ini mengikuti constraint PRD. Perpindahan kelas intra-tahun belum diaktifkan; jika sekolah membutuhkannya, aturan periode efektif dan migrasi histori harus ditetapkan lebih dulu.

## Jadwal reguler T11

Admin dapat membuka `/admin/schedules` untuk menyimpan jadwal per hari dan tahun ajaran, termasuk mulai check-in, mulai terlambat, cutoff check-in, mulai check-out, dan status aktif. `/admin/schedules/<id>/edit` memperbarui jadwal yang sudah ada. Migration [006_create_attendance_schedules.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/006_create_attendance_schedules.sql) menambahkan constraint satu jadwal per hari/tahun ajaran dan urutan waktu di database.

Resolver memakai waktu server dengan `APP_TIMEZONE=Asia/Jakarta`; browser tidak menjadi sumber waktu. Baseline saat ini menerima check-in tepat pada `checkin_start` dan `checkin_cutoff`, menandai waktu mulai `late_after` sebagai Terlambat, serta menolak waktu sesudah cutoff. Batas akhir check-out belum ditetapkan.

```powershell
.venv\Scripts\python.exe -m scripts.smoke_t11
```

## Exception dan preview jadwal T12

Admin mengelola hari libur, ujian, kegiatan sekolah, pulang awal, dan exception lain pada `/admin/schedule-exceptions`. Exception dapat berlaku untuk seluruh sekolah atau satu kelas. Waktu yang tidak dioverride mewarisi nilai dari prioritas berikutnya; urutannya exception kelas, exception sekolah, lalu jadwal reguler. Hari libur menghasilkan jadwal efektif tanpa kewajiban presensi.

Preview pada layar yang sama menerima tanggal, tahun ajaran, dan kelas opsional serta memanggil resolver `resolve_schedule`, yang juga disediakan untuk alur presensi. Satu exception per tanggal/scope/kelas diperbolehkan; konflik ditolak. Perubahan dicatat di audit log. Migration [007_create_schedule_exceptions.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/007_create_schedule_exceptions.sql) perlu diterapkan setelah migration 006, atau gunakan `database/schema.sql` untuk instalasi baru.

Verifikasi T12:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_schedule_exception.py -v
.venv\Scripts\python.exe -m scripts.smoke_t12
```

Unit suite penuh lulus dengan 91 test. Smoke MySQL T12 mencakup prioritas scope, pewarisan waktu, duplikasi, hari libur, perubahan status, audit rollback, dan cleanup data sintetis.

## Geofence T13

Admin dapat mengelola konfigurasi pada `/admin/geofence`. Migration [008_create_school_geofences.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/008_create_school_geofences.sql) menambahkan titik sekolah, nama, radius awal 75 meter, kebijakan max accuracy, dan status aktif. `geofence_service` memvalidasi rentang koordinat serta accuracy, menghitung jarak server-side dengan Haversine, dan menolak konfigurasi yang belum aktif atau pembacaan accuracy yang tidak andal. Tombol “Periksa lokasi perangkat ini” menangani izin browser, timeout, sinyal lokasi, accuracy, radius, dan retry; browser hanya meminta lokasi setelah pengguna menekan tombol.

Verifikasi T13:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_geofence.py -v
.venv\Scripts\python.exe -m scripts.smoke_t13
```

Unit test dan smoke MySQL lulus dengan titik sintetis, termasuk audit rollback dan cleanup. Database lokal belum memiliki koordinat sekolah atau max accuracy. Geofence sengaja tetap nonaktif sampai sekolah memberikan titik terverifikasi dan menetapkan ambang accuracy. Uji perangkat Android/HTTPS dengan lokasi sebenarnya menjadi bagian T32.

## Gate enrollment Siswa T14

Siswa dengan `face_registered=false` harus mengganti password sementara terlebih dahulu, kemudian diarahkan ke `/student/enrollment`. Halaman menunjukkan progres pose depan, kiri, dan kanan yang tersimpan untuk akun tersebut. Dashboard, profil, dan endpoint blueprint siswa, presensi, serta wajah terlindungi dari akses langsung; Siswa tidak dapat membaca progres atau storage key milik siswa lain. Enrollment tidak dianggap selesai sebelum T16 melatih dan memperbarui model.

Migration [009_create_student_faces.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/009_create_student_faces.sql) menyiapkan constraint satu pose per siswa. Terapkan migration ini setelah 008 untuk database lama; instalasi baru dapat memakai [database/schema.sql](D:/ProjectWeb/sistem-absensi-pwa/database/schema.sql). Perekaman foto dan pose valid dilaksanakan di T15.

Verifikasi T14:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_student_enrollment.py -v
.venv\Scripts\python.exe -m scripts.smoke_t14
```

Smoke T14 memakai akun/pose sintetis sementara dan menghapus semua data uji setelah selesai.

## Capture enrollment tiga pose T15

Halaman enrollment Siswa meminta informasi penyimpanan dibaca sebelum kamera diaktifkan. Kamera berjalan melalui HTTPS; server menerima frame untuk pemeriksaan satu wajah dan quality signal sementara, lalu memandu urutan buka mata → kedip → buka mata. Sampel yang lolos otomatis dipotong dan disimpan pada `storage/faces/` di luar folder publik. Setiap pose hanya memiliki satu baris; mengambil ulang pose mengganti sampel lama setelah capture baru berhasil. Sampel dari pose gagal tetap utuh.

Challenge acak berumur 45 detik disimpan di database bersama user, sesi login, dan pose. Challenge dihapus setelah capture sehingga replay token ditolak; client tidak mengirim klaim `blink=true`. Status tiga pose tidak mengubah `face_registered`; training/finalisasi model, threshold, dan logout untuk login ulang berada di T16. Arah pose kiri/kanan masih mengikuti panduan Siswa dan belum diverifikasi otomatis oleh model arah kepala. Quality dan blink memakai sinyal Haar provisional; penerimaan T04 tidak menyatakan akurasi biometrik siap production.

Untuk database lama, jalankan migration [010_create_face_enrollment_challenges.sql](D:/ProjectWeb/sistem-absensi-pwa/database/migrations/010_create_face_enrollment_challenges.sql) setelah 009 melalui HeidiSQL. Database baru dapat memakai [schema.sql](D:/ProjectWeb/sistem-absensi-pwa/database/schema.sql). Setelah migration:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_face_enrollment.py -v
.venv\Scripts\python.exe -m scripts.smoke_t15
```

Smoke T15 memakai DB development dan frame/crop sintetis; ia memeriksa challenge sekali pakai, expiry, binding sesi, unique pose, file privat, serta memastikan `face_registered` tetap false. Persetujuan dan kebijakan retensi/penghapusan data biometrik sekolah tetap perlu ditetapkan sebelum penggunaan production.

Pada penyelesaian T15, seluruh 108 unit test, smoke MySQL T15, build CSS, pemeriksaan sintaks JavaScript, compileall, dan strict UI audit lulus. Migration 010 sudah diterapkan pada database development lokal; database lain perlu menerapkannya sebelum memakai enrollment. Alur enrollment T15 belum dicoba dengan kamera Android. Arah pose masih dipandu teks, belum diverifikasi otomatis; threshold LBPH dan finalisasi wajah dikerjakan pada T16.

## Check-in tervalidasi T18

Alur mengikuti PRD §8.2 secara berurutan: dashboard menunjukkan CTA dari state server; tekan CTA meminta lokasi perangkat terlebih dahulu (`POST /attendance/checkin/start` memvalidasi state checkin dan geofence sebelum kamera dibuka); kamera memeriksa satu wajah, quality, dan blink server-side (`POST /attendance/checkin/frame`); setelah blink lengkap, LBPH memprediksi identitas dan label wajib sama dengan akun login; foto bukti dikompresi ke WebP dan disimpan di `storage/attendance/` hanya setelah identitas cocok; record `attendance_records` dibuat dengan status `Hadir`/`Terlambat`, snapshot `class_id`, dan audit `attendance_checkin` dalam satu transaksi.

Yang ditolak tanpa menulis presensi sukses: di luar radius geofence (422), accuracy tidak andal atau geofence belum dikonfigurasi (422), jendela check-in tertutup/libur/status manual (409), tantangan kedaluwarsa/token salah (410/400), wajah tidak cocok (403), dan model hilang/rusak (503 fail-closed dengan log). Check-in duplikat mengembalikan record existing tanpa insert baru. Kegagalan transaksi menghapus file evidence yang sudah ditulis. Klik ganda dicegah di UI sebagai bantuan UX; backend tetap memvalidasi ulang jadwal dan akun pada setiap submit (AC-03–AC-05).

Verifikasi T18:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_attendance_checkin.py -v
.venv\Scripts\python.exe -m scripts.smoke_t18
```

Smoke T18 memakai dua akun sintetis, enrollment nyata, jadwal sintetis, dan geofence sintetis yang di-inject; ia membuktikan AC-03/04/05 dengan model LBPH nyata lalu membersihkan semua data uji. Uji kamera/GPS perangkat nyata, threshold LBPH final, dan beban konkurensi nyata mengikuti T32–T33.

## Check-out dan retry aman T19

CTA `Presensi Pulang` (state `checkout`) memakai alur yang sama dengan check-in tetapi pada session dan endpoint terpisah: `POST /attendance/checkout/start` memvalidasi state server (`can_checkout_now`, sudah check-in, belum checkout), lokasi geofence, lalu menerbitkan challenge terpisah (`_attendance_checkout`); kamera berjalan blink server-side pada `POST /attendance/checkout/frame`; setelah identitas cocok, server mengunci record hari itu (`SELECT … FOR UPDATE`), mengunci ulang keadaan, dan mengisi kolom `checkout_*` ( waktu UTC server, koordinat challenge, evidence WebP, `checkout_liveness_verified`, `updated_by` ) beserta audit `attendance_checkout` dalam satu transaksi.

Retry terikat per aksi dan tanggal: challenge check-in tidak dapat dipakai untuk check-out dan sebaliknya (key session berbeda); check-out duplikat (rowcount 0 karena `checkout_at IS NULL` sudah terisi) atau dua submit bersamaan menghasilkan respons duplikat tanpa insert/kedua; check-out tanpa check-in ditolak 409. Kegagalan transaksi menghapus file evidence. UI tidak pernah menyatakan sukses sebelum konfirmasi server — setelah sukses halaman dimuat ulang sehingga state server yang menjadi otoritas; respons hilang diperlakukan sebagai “belum terkonfirmasi” dan diselesaikan dengan memuat ulang state, bukan klaim client (AC-06, AC-07, AC-11).

Verifikasi T19:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_attendance_checkout.py -v
.venv\Scripts\python.exe -m scripts.smoke_t19
```

Smoke T19 memakai satu akun sintetis dengan enrollment nyata, jadwal sintetis (`checkout_start=23:59`), dan exception kelas `early_dismissal` (`checkout_start=00:00`); ia membuktikan AC-06 (checkout terlalu awal → 409, tanpa tulis), AC-07 (record yang sama menerima `checkout_at` + evidence), AC-11 (exception dipakai saat resolver merge jadwal), dan duplikat idempoten, lalu membersihkan semua data uji.

## Finalisasi Alpa T20

`scripts/finalize_alpa.py` adalah job server (PRD §11.4, BR-13, BR-14) yang menandai Alpa siswa wajib hadir setelah cutoff efektif:

- **Kandidat** = penempatan aktif pada tahun ajaran aktif yang mencakup tanggal, kelas aktif, akun `role='student'` dan `is_active=1`.
- **Cutoff** diambil dari jadwal efektif per grup kelas (exception kelas → sekolah → reguler). Job hanya menulis bila momen **setelah** cutoff secara strict (tepat pada cutoff check-in masih terbuka, konsisten dengan `evaluate_checkin`). Backfill tanggal lampau tidak terblokir jam hari ini (`for_date` dibandingkan terpisah dari `at`).
- **Dilewati bila**: tanpa jadwal, libur (AC-10), belum lewat cutoff, sudah ada `checkin_at` (auto-presence), atau sudah ada `status` apa pun (Izin/Sakit/Alpa manual Guru). Libur/exception tidak pernah menghasilkan Alpa otomatis.
- **Tulis**: `INSERT` atau `UPDATE` record yang sama dengan `status='absent'`, `status_source='finalization_job'`, snapshot `class_id`, dan audit `attendance_alpa_finalized` (actor NULL) — semuanya dalam satu transaksi dengan `SELECT … FOR UPDATE` dan re-check keputusan sehingga check-in yang berlangsung bersamaan selalu menang (diterjemahkan ke skip, bukan failure). Constraint DB `chk_attendance_source_checkin` melarang record `finalization_job` memiliki `checkin_at`.
- **Idempoten**: run kedua melihat record sudah berstatus → skip; tidak ada duplikat record atau audit ganda. Gagal per-siswa dihitung dan dicatat ke log tanpa menghentikan run lain; job tidak pernah memproses akun nonaktif/kelas nonaktif/tahun ajaran di luar tanggal.

Pemanggilan (aman diulang; output hanya counts — tanpa nama/NISN):

```powershell
.venv\Scripts\python.exe -m scripts.finalize_alpa            # hari ini (Asia/Jakarta)
.venv\Scripts\python.exe -m scripts.finalize_alpa --date 2026-09-22   # backfill
.venv\Scripts\python.exe -m scripts.finalize_alpa --dry-run  # hitung saja
```

Contoh cron produksi (VPS Linux; sesuaikan path):

```cron
*/10 6-18 * * 1-6 cd /opt/sistem-absensi && .venv/bin/python -m scripts.finalize_alpa >> logs/finalize_alpa.log 2>&1
```

Exit code 1 bila ada kegagalan (untuk alerting scheduler); tanggal format salah dan tanggal masa depan ditolak. Skenario front-end/admin manual untuk T20 tidak berubah — tidak ada route/UI baru; Admin/Guru tidak perlu menjalankan job ini secara manual kecuali untuk backfill.

Verifikasi T20:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_finalization_service.py -v
.venv\Scripts\python.exe -m scripts.smoke_t20
```

Smoke T20 memakai tiga siswa sintetis (hadir/izin/kosong) pada jadwal nyata; ia membuktikan before-cutoff tidak menulis, after-cutoff hanya mengubah siswa kosong, double-run idempoten, dry-run tidak menulis, dan AC-10 (exception libur sekolah → 0 Alpa), lalu membersihkan seluruh fixture. Uji benturan dengan endpoint status manual Guru diulang pada T24; frekuensi cron pasti dan retensi log diatur saat deployment T34.


### Ilustrasi v2 — 26 September 2026

Tujuh ilustrasi original sudah dibuat melalui built-in imagegen dan dipasang, termasuk sambutan khusus Guru dan Admin. Master PNG dan prompt: `design/illustrations/v2/`; WebP: `app/static/illustrations/`, total 748102 byte. Dua aset (`location-v2`, `empty-v2`) **masih tertunda karena kuota imagegen**; SVG lama tetap digunakan. Cache aktif v7, hanya aset publik. Paket sembilan ilustrasi dan T31 belum ditandai selesai. Rincian penempatan, verifikasi, batas pembesaran teks, dan bukti screenshot lokal: [catatan ilustrasi v2](design/illustrations/v2/README.md).


### Login mobile — 26 September 2026

Varian `.login-page` pada viewport <640px memakai header coral ringkas dan kartu form putih solid, radius 24px, padding 20px, margin luar 16px. Form dan kontrol tetap sama; judul mobile menjadi “Masuk ke Presensi”. Desktop tidak memakai varian ini. Password toggle dapat membungkus saat teks diperbesar, banner jaringan mengikuti alur dokumen. Cache aset terkini **v8**, menggantikan v7 dari tahap ilustrasi. Verifikasi: 273 unit test, enam tes Node PWA, build CSS, syntax Service Worker, serta pemeriksaan browser ukuran 320–1440px dan teks 200% lulus. [Bukti dan batas verifikasi](docs/LOGIN_MOBILE_REDESIGN.md). T31 keseluruhan dan T32 tetap terpisah.
