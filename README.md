# sistem-absensi-pwa

Sistem presensi siswa SMA Negeri 4 Lhokseumawe. Status saat ini: T00–T03 selesai; POC offline T04 tersedia tetapi uji lapangannya terhambat; T05–T11 selesai; T12–T35 masih direncanakan.

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

Catatan keputusan, keterbatasan, dan prosedur uji Android/HTTPS ada di [docs/T04_BIOMETRIC_POC.md](D:/ProjectWeb/sistem-absensi-pwa/docs/T04_BIOMETRIC_POC.md). Uji perangkat nyata, permission kamera, sampel berizin, dan threshold final belum tersedia sehingga POC belum menjadi bukti kesiapan biometrik.

### Menjalankan setup T04 di Android

Setup ini terisolasi dari login, database, enrollment, dan presensi. Pastikan laptop serta Android berada pada Wi-Fi yang sama. Git for Windows diperlukan karena setup memakai OpenSSL lokal.

```powershell
.venv\Scripts\python.exe -m scripts.setup_t04_android --ip 10.160.102.172
.venv\Scripts\python.exe -m scripts.run_t04_android
```

Ganti `10.160.102.172` dengan alamat Wi-Fi laptop bila berubah. Terminal menampilkan URL setup HTTP, URL kamera HTTPS, dan kode akses sementara. Buka URL setup dari Android, unduh `SMA4-T04-CA.crt`, pasang sebagai **Sertifikat CA**, lalu buka URL kamera HTTPS. Cocokkan sidik jari SHA-256 yang tampil sebelum melanjutkan. Bila Windows Firewall memblokir akses, izinkan Python pada jaringan Private atau buka TCP 8084 dan 8443 untuk jaringan lokal.

Di halaman kamera, centang persetujuan peserta, nyalakan kamera, uji satu wajah, tiga pose, cahaya/buram, kedipan, dan mismatch. Unduh `hasil-t04.json`; file ini tidak memuat foto. Hapus sertifikat `SMA4 T04 Local Test CA` dari Android setelah percobaan. Ini hanya bukti kelayakan T04; auto-capture, challenge server, penyimpanan enrollment, dan threshold produksi tetap dikerjakan pada T15–T16.

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
