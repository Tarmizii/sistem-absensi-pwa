# Panduan Agen — Sistem Presensi SMA Negeri 4 Lhokseumawe

## Acuan dan lingkup kerja

- Baca `PRD_Sistem_Presensi_SMA_Negeri_4_Lhokseumawe.md` versi 1.0, 21 September 2026, terutama bagian yang terkait tugas. PRD adalah acuan kebutuhan produk; file ini merangkum panduan pengembangan dan tidak menggantikan PRD.
- Ikuti permintaan pengguna untuk menentukan pekerjaan yang dilakukan. Daftar fitur, roadmap, dan contoh dalam PRD bukan perintah untuk langsung membangun atau men-deploy seluruh sistem.
- Pertahankan perbedaan requirement Must, Should, rekomendasi, dan contoh. Jangan mengubah keputusan produk yang dikunci tanpa arahan pengguna.
- Gunakan bahasa Indonesia untuk komunikasi, dokumentasi produk, dan teks UI. Pertahankan identifier teknis yang konsisten dengan PRD.
- Jangan membawa asumsi dari proyek presensi lain. Jika ada konflik atau aturan produk belum jelas, catat dan klarifikasi pada tahap yang terdampak; lanjutkan pekerjaan independen yang sudah jelas.

## Kondisi repositori dan perintah

- Pada saat inisialisasi, repositori hanya berisi PRD, README, dan `.gitattributes`; belum tersedia aplikasi, schema, dependency manifest, atau test runner.
- Struktur di bawah adalah target PRD, bukan klaim bahwa file atau fitur sudah tersedia.
- Belum ada perintah install, build, run, atau test yang terverifikasi. Setelah tooling ditambahkan, dokumentasikan perintah yang benar-benar berhasil di `README.md`.
- Lingkungan pengembangan saat inisialisasi menggunakan Windows/PowerShell. Target production tetap Linux VPS + domain + HTTPS.

## Dokumentasi library: Context7

- Gunakan Context7 MCP untuk dokumentasi terkini ketika tugas membahas library, framework, SDK, API, CLI, atau cloud service, termasuk sintaks, konfigurasi, setup, migrasi versi, dan debugging khusus library.
- Mulai dengan `resolve-library-id`, kecuali pengguna memberikan ID tepat dalam format `/org/project`. Pilih hasil berdasarkan kecocokan nama, relevansi, reputasi sumber, jumlah snippet, dan benchmark; gunakan ID versi bila versi ditentukan.
- Lanjutkan dengan `query-docs` menggunakan pertanyaan spesifik untuk satu konsep. Pisahkan konsep berbeda, kecuali pertanyaan membahas interaksi antar-konsep. Utamakan hasil dokumentasi tersebut daripada ingatan atau pencarian web umum.
- Tidak perlu untuk refactoring murni, skrip dari nol tanpa pertanyaan library, debugging logika bisnis, code review, atau konsep pemrograman umum.
- Jika Context7 tidak tersedia, nyatakan keterbatasannya dan gunakan dokumentasi resmi sebagai fallback; jangan mengklaim sudah melakukan lookup.

## Stack dan struktur target

- Satu repository Flask modular monolith; server-rendered HTML/templates, TailwindCSS, dan JavaScript. Jangan mengganti frontend dengan React/Vue atau memecahnya menjadi microservices.
- Autentikasi berbasis session/Flask-Login. Database MySQL dengan PyMySQL dan parameterized raw SQL; tidak membutuhkan ORM kompleks.
- Face recognition: `opencv-contrib-python`, Haar Cascade, LBPH, dan NumPy. Pemilihan library facial landmarks/eye state untuk blink belum dikunci.
- Analisis: scikit-learn (`StandardScaler`, `KMeans`); agregasi/ekspor: pandas + openpyxl; grafik: Chart.js.
- PWA: Web App Manifest + Service Worker. Production: Nginx → Gunicorn → Flask, MySQL, dan protected storage.
- Struktur target sesuai PRD §15:
  - `run.py`, `config.py`, `requirements.txt`.
  - `app/__init__.py`, `app/database.py`.
  - Blueprint `auth`, `student`, `teacher`, `admin`, `attendance`, `face`, `kmeans`, masing-masing dengan `routes.py`.
  - `app/services/` untuk auth, attendance, face, image quality, liveness, geofence, schedule, K-Means, export, dan audit.
  - `app/templates/{auth,student,teacher,admin}/` dan `app/static/{css,js,audio,icons,illustrations}/`.
  - `database/schema.sql`, `database/seed.sql`, `tests/`, serta `storage/{faces,attendance,models}/`.
- Route menangani input/output HTTP; service memegang aturan bisnis. `attendance_service` mengorkestrasi seluruh validasi, penyimpanan evidence, transaksi, dan audit.
- Simpan secrets dalam environment, jangan commit `.env`. Dokumentasikan variabel melalui contoh tanpa kredensial asli.

## Invarian presensi dan jadwal

- Backend menjadi otoritas waktu, tanggal presensi, jadwal efektif, role/scope, lokasi, liveness, identitas wajah, dan hasil transaksi. UI menampilkan state dari backend.
- Satu siswa hanya mempunyai satu `attendance_records` per tanggal: UNIQUE `(student_id, attendance_date)`. Check-in dan check-out mengubah record yang sama.
- Satu CTA menentukan check-in, menunggu jam pulang, check-out, atau selesai berdasarkan jadwal efektif dan record hari itu.
- Check-in mengikuti `checkin_start`, `late_after`, dan `checkin_cutoff`; check-out memerlukan check-in berhasil dan waktu minimal `checkout_start`. Jangan hardcode jam contoh PRD.
- Prioritas jadwal: exception kelas → exception sekolah → jadwal reguler, dengan tanggal, kelas, dan tahun ajaran yang relevan. Hari libur tidak menerima presensi atau menghasilkan Alpa otomatis.
- Finalisasi Alpa berjalan setelah cutoff efektif untuk siswa yang wajib hadir dan belum memiliki auto-presence atau status manual sah. Job harus aman dijalankan ulang.
- Geofence awal 75 meter, dapat diubah Admin. Server menghitung jarak dari latitude/longitude dan menyimpan accuracy; lokasi tidak andal harus ditolak dengan arahan retry. Jangan mengarang koordinat sekolah.
- Presensi sukses memerlukan waktu/jadwal, lokasi, kualitas wajah, blink, dan identitas hasil recognition yang cocok dengan siswa login.
- Gunakan transaksi dan constraint database untuk mencegah partial write, race, dan duplikasi. Retry harus idempotent; UI hanya menyatakan sukses setelah konfirmasi commit server.
- `Belum Absen` adalah derived UI state, bukan enum tersimpan yang wajib. `Libur` berasal dari schedule engine. Simpan `class_id` sebagai snapshot historis pada presensi.

## Akun, role, dan biometrik

- Tiga role tetap: Siswa, Guru/Wali Kelas, Admin. Validasi role dan lingkup data pada setiap route/operasi, termasuk akses URL langsung dan file.
- Admin membuat akun; NISN menjadi username siswa. Reset password menghasilkan password sementara dan `must_change_password=true`; pengguna wajib menggantinya sebelum dashboard.
- Siswa dengan `face_registered=false` wajib enrollment dan tidak dapat melewati gate melalui URL. Setelah enrollment berhasil, akhiri session dan minta login ulang.
- Enrollment tepat tiga capture: `front`, `left`, `right`, UNIQUE `(student_id, pose)`. Setiap pose memerlukan satu wajah, quality check, blink, auto capture, suara shutter, dan feedback visual.
- Tandai enrollment selesai setelah tiga pose valid dan model berhasil dilatih/diperbarui. Tidak ada approval Admin untuk enrollment.
- Gunakan preprocessing konsisten (crop, grayscale, resize). Threshold LBPH harus dikalibrasi melalui pengujian; score bukan otomatis probabilitas akurasi.
- Reset wajah menonaktifkan/menghapus enrollment lama, memperbarui model, dan mengembalikan `face_registered=false`. Model hilang/rusak harus menolak presensi wajah dan menghasilkan log/alert yang dapat ditindaklanjuti.
- Siswa hanya dapat membaca kalender bulan berjalan miliknya; batasi query backend. Jangan tampilkan foto evidence atau koordinat teknis kepada siswa.
- Guru hanya mengakses kelas tanggung jawabnya dan menetapkan Izin/Sakit/Alpa jika belum ada auto-presence valid. Guru tidak boleh mengubah Hadir/Terlambat hasil sistem.
- PRD §12 mewajibkan keterangan Izin/Sakit, sedangkan FR-TCH-05 berprioritas Should; catat perbedaan prioritas ini saat menetapkan acceptance modul Guru. Catatan Alpa opsional.
- Guru kelas terkait dan Admin dapat melihat evidence; Admin mengelola master data, konfigurasi, reset, monitoring, ekspor, K-Means, dan audit. Admin tidak melakukan presensi sebagai siswa.
- Pertahankan histori saat akun dinonaktifkan atau penempatan kelas berubah. Ikuti seluruh tabel dan unique constraint PRD §14.

## Analisis K-Means

- Hanya dijalankan on-demand oleh Admin, dengan K=3 dan fitur `attendance_percentage`, `late_count`, `alpha_count`; jangan menjalankannya pada setiap transaksi presensi.
- Formula operasional PRD: `effective_days = scheduled_school_days - izin - sakit`; `attendance_percentage = ((hadir + terlambat) / effective_days) * 100`. Hari libur tidak masuk hari wajib hadir.
- Selaraskan formula dengan metodologi penelitian sebelum implementasi final. Tangani denominator nol, data kosong/tidak valid, dan siswa/data berbeda yang tidak memadai untuk tiga cluster secara eksplisit.
- Standardisasi fitur, gunakan random state tetap, dan inverse-transform centroid untuk interpretasi. Nomor cluster tidak boleh langsung diikat ke label tinggi/sedang/rendah.
- Simpan metadata run, fitur/hasil tiap siswa, centroid, dan label sebagai histori; jangan menimpa run lama.
- Silhouette Score/Davies-Bouldin Index, bila digunakan, adalah metrik kualitas cluster, bukan akurasi terhadap ground truth.

## Kontrak UI/UX

- Ikuti PRD §16 dan Lampiran A–D: Soft Bento School App, rounded, bersih, hangat; tabel/form tetap mengutamakan keterbacaan.
- Token: background `#F6F4EE`, surface `#FFFFFF`, primary `#725CF6`, primary soft `#EEE9FF`, lime `#DDF68A`, text `#191919`, muted `#707070`, border `#E7E4DD`.
- Gunakan Plus Jakarta Sans dan Phosphor Icons. Ilustrasi custom sekitar 5–7 aset, konsisten bergaya editorial 2D, cream/purple/lime, tanpa glossy 3D; gunakan pada konteks yang ditetapkan PRD.
- Siswa: mobile PWA; bottom nav Beranda, Riwayat, Profil. Presensi adalah CTA dashboard.
- Guru mobile: bottom nav Dashboard, Presensi, Siswa; profil melalui topbar/avatar. Guru desktop: sidebar Dashboard, Presensi Kelas, Data Siswa, Profil.
- Admin: desktop, sidebar 256px dengan delapan tujuan pada PRD §16.3; viewport kecil boleh menampilkan pesan perangkat tidak didukung.
- Breakpoint PRD: mobile <640px, tablet 640–1023px, desktop ≥1024px. Jangan mengimpor batas lebar atau navigasi dari proyek lain.
- Gunakan warna status pada Lampiran B; sertakan label teks. Sediakan loading, empty, error, retry, dan disabled state yang jelas, termasuk permission kamera/lokasi.
- PWA hanya menyimpan shell/aset yang aman. Presensi wajib online; jangan antrekan presensi offline atau cache respons sensitif/foto biometrik melalui Service Worker.

## Keamanan dan operasi

- Hash password; gunakan cookie HttpOnly, Secure pada HTTPS, dan SameSite sesuai kebutuhan. Lindungi aksi mutasi dengan CSRF atau mekanisme ekuivalen.
- Validasi tipe/ukuran payload kamera dan input. Gunakan parameterized SQL, jangan interpolasi input pengguna ke query.
- Simpan faces, evidence, dan model di protected storage, bukan public static. Route file harus memverifikasi role serta scope sebelum mengirim konten.
- Recognition menggunakan frame berkualitas; kompres evidence setelah recognition berhasil. Jangan log password atau payload biometrik mentah.
- Audit reset wajah/password, status manual, perubahan jadwal/geofence, dan master data penting, dengan pelaku serta waktu.
- Production menggunakan domain HTTPS, Nginx/Gunicorn, service systemd, MySQL private, job finalisasi Alpa, log rotation, dan monitoring storage.
- Backup database harian dan protected storage berkala; uji restore. Retensi foto, prosedur penghapusan, dan persetujuan/informasi biometrik perlu kebijakan sekolah sebelum production penuh.

## Ambiguitas yang harus ditangani saat fitur terkait dikerjakan

- PRD belum menetapkan timezone aplikasi secara eksplisit, batas akhir check-out, inklusivitas tepat pada cutoff, nilai batas accuracy GPS, atau detail kebijakan check-in sebelum jam mulai.
- Perjelas konflik exception pada scope/tanggal yang sama, perubahan jadwal terhadap histori, dan interaksi status manual dengan percobaan presensi otomatis berikutnya.
- Selaraskan kebutuhan perpindahan kelas dalam tahun ajaran dengan UNIQUE `(student_id, academic_year_id)` pada penempatan kelas; snapshot presensi lama wajib tetap benar.
- Dokumentasikan pilihan landmark/blink, timeout challenge, threshold hasil kalibrasi, formula analisis, dan cara memberi label centroid. Jangan menyajikan pilihan implementasi ini sebagai keputusan eksplisit PRD.

## Tahapan dan verifikasi

- Ikuti dependensi PRD §22 sesuai tugas yang diminta: Foundation → Master Data → Schedule/Geofence → Face Enrollment → Attendance → Teacher → Admin Monitoring → K-Means → PWA/UX → Deployment/QA.
- Untuk perubahan logika, jalankan pengujian yang relevan dan kaitkan hasil dengan requirement/acceptance PRD §21, terutama AC-01 sampai AC-12. Laporkan checks yang belum dapat dijalankan beserta penyebabnya.
- Verifikasi batas jadwal/exception/libur, Haversine, role dan cross-class access, gate password/enrollment, transaksi/retry/duplikasi, ekspor, serta kalkulasi dan histori K-Means.
- Uji CSRF, logout, protected photos, input SQL, dan penanganan password pada fitur yang terdampak. Gunakan data sintetis; jangan memasukkan secrets, wajah nyata, atau dump produksi ke repository.
- Pengujian sintetis tidak menggantikan pengujian Android/PWA melalui HTTPS untuk kamera, GPS, pose, blink, pencahayaan, mismatch, dan koneksi lambat/putus.
- Jangan mengklaim GPS/blink kebal spoofing atau replay. Bedakan fitur simulasi, implementasi teruji, dan validasi perangkat nyata.
- Definition of Done produk mengikuti PRD §25, termasuk acceptance Must, deployment HTTPS, backup/restore, dan dokumentasi; menyelesaikan satu fase tidak berarti seluruh produk selesai.
- Jangan menambah fitur di luar scope tanpa permintaan: presensi per mata pelajaran, izin mandiri siswa, approval enrollment, native app, offline attendance, notifikasi otomatis, multi-school, atau advanced anti-spoofing.
