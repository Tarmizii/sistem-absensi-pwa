# Product Requirements Document (PRD)

## Sistem Presensi Siswa Berbasis Face Recognition dan Geolocation dengan Analisis Pola Kehadiran Menggunakan K-Means

**SMA Negeri 4 Lhokseumawe**  
**Versi:** 1.0 — Final Draft  
**Tanggal:** 21 September 2026

> Dokumen ini menjadi acuan produk, desain, pengembangan, pengujian, dan implementasi sistem dari awal sampai akhir.

# Kontrol Dokumen

| **Item**            | **Nilai**                                                                               |
|---------------------|-----------------------------------------------------------------------------------------|
| Nama dokumen        | Product Requirements Document (PRD)                                                     |
| Produk              | Sistem Presensi Siswa Berbasis Face Recognition dan Geolocation dengan Analisis K-Means |
| Lokasi implementasi | SMA Negeri 4 Lhokseumawe                                                                |
| Versi               | 1.0                                                                                     |
| Status              | Final Draft / Source of Truth pengembangan                                              |
| Platform            | Web responsif + Progressive Web App (PWA)                                               |
| Deployment          | VPS + domain + HTTPS                                                                    |
| Backend             | Python Flask                                                                            |
| Database            | MySQL                                                                                   |
| Frontend            | HTML, TailwindCSS, JavaScript                                                           |
| Face recognition    | OpenCV Haar Cascade + LBPH                                                              |
| Analisis            | K-Means (scikit-learn), K=3                                                             |

> **Prinsip dokumen**
> Semua kebutuhan yang tercantum sebagai “wajib” adalah scope versi skripsi. Contoh jam pada dokumen hanyalah contoh visual; jam aktual, toleransi, cutoff, dan jam pulang dikelola Admin dan tidak di-hardcode.

# Daftar Isi Ringkas

- 1\. Ringkasan Eksekutif

- 2\. Latar Belakang dan Masalah

- 3\. Visi, Tujuan, dan Indikator Keberhasilan

- 4\. Scope dan Batasan Produk

- 5\. Aktor, Role, dan Hak Akses

- 6\. Arsitektur dan Teknologi

- 7\. Aturan Bisnis Presensi

- 8\. User Journey End-to-End

- 9\. Kebutuhan Fungsional

- 10\. Face Recognition, Enrollment, dan Liveness

- 11\. Geolocation dan Schedule Engine

- 12\. Status Presensi dan Kalender

- 13\. Analisis K-Means

- 14\. Data Model dan Database

- 15\. Route dan Struktur Modul Flask

- 16\. UI/UX dan Design System

- 17\. Security, Privacy, dan Audit

- 18\. Non-Functional Requirements

- 19\. Deployment VPS, Domain, dan Operasional

- 20\. Error Handling dan Edge Cases

- 21\. Pengujian dan Acceptance Criteria

- 22\. Rencana Implementasi

- 23\. Risiko dan Mitigasi

- 24\. Out of Scope dan Roadmap

- 25\. Definition of Done

- Lampiran A–D.

# 1. Ringkasan Eksekutif

Produk ini adalah sistem presensi siswa berbasis web/PWA untuk menggantikan proses presensi manual di sekolah. Siswa melakukan presensi masuk dan pulang melalui perangkat mobile dengan validasi kombinasi jadwal, geolocation, liveness sederhana berbasis kedipan, dan face recognition. Guru wali kelas memonitor kelas serta menetapkan status manual untuk siswa yang belum melakukan presensi otomatis. Admin mengelola master data, jadwal, geofence, pengecualian jadwal, monitoring, ekspor, akun, data wajah, dan analisis pola kehadiran menggunakan K-Means.

Sistem dirancang sebagai modular monolith dalam satu repository Flask. Frontend menggunakan HTML, TailwindCSS, dan JavaScript; database menggunakan MySQL; pengenalan wajah menggunakan OpenCV Haar Cascade untuk deteksi dan LBPH untuk pengenalan; analisis clustering menggunakan scikit-learn. Sistem dideploy pada VPS dengan domain dan HTTPS agar dapat diakses dari berbagai perangkat tanpa harus berada pada jaringan lokal sekolah.

Fokus penelitian berada pada pengembangan sistem presensi dan analisis pola kehadiran. Sistem face recognition digunakan sebagai komponen validasi identitas, bukan sebagai penelitian akurasi biometrik tingkat lanjut.

# 2. Latar Belakang dan Masalah

Proses presensi yang masih bergantung pada pencatatan manual memiliki beberapa keterbatasan: membutuhkan waktu, sulit dipantau secara real time, rawan kesalahan pencatatan, dan membuka peluang terjadinya titip absen. Selain itu, data presensi yang tersebar atau tidak terstruktur menyulitkan sekolah untuk melihat pola kehadiran siswa secara cepat.

Produk yang dirancang harus menjawab kebutuhan operasional harian tanpa membuat proses siswa menjadi rumit. Oleh karena itu, satu aksi presensi harus mampu menentukan secara otomatis apakah siswa sedang melakukan check-in atau check-out, memvalidasi lokasi, memverifikasi liveness dan wajah, lalu menyimpan bukti yang dapat ditinjau oleh pihak sekolah.

- Presensi manual memerlukan pencatatan dan rekap tambahan.

- Validasi identitas dan kehadiran fisik siswa belum terotomasi.

- Sekolah membutuhkan jadwal presensi yang dapat berubah per hari dan kondisi khusus.

- Wali kelas membutuhkan monitoring kelas dan mekanisme input izin/sakit/alpa yang terkontrol.

- Admin membutuhkan rekap, ekspor, audit perubahan, dan analisis pola kehadiran.

- Siswa membutuhkan pengalaman presensi yang cepat, jelas, dan dapat digunakan melalui PWA mobile.

# 3. Visi, Tujuan, dan Indikator Keberhasilan

## 3.1 Visi Produk

Menyediakan sistem presensi sekolah yang mudah digunakan, dapat diverifikasi, memiliki jejak audit, dan mampu mengubah data presensi harian menjadi informasi pola kehadiran yang berguna bagi sekolah.

## 3.2 Tujuan Utama

1.  Mendigitalisasi check-in dan check-out siswa melalui PWA.

2.  Memverifikasi identitas siswa dengan face recognition serta liveness kedipan.

3.  Memastikan presensi dilakukan dalam radius lokasi yang dikonfigurasi sekolah.

4.  Menyediakan jadwal dinamis, hari libur, dan schedule exception tanpa perubahan kode.

5.  Menyediakan monitoring dan rekap per kelas/periode.

6.  Menyediakan analisis pola kehadiran dengan K-Means menggunakan tiga fitur: persentase kehadiran, jumlah terlambat, dan jumlah alpa.

7.  Menyediakan keamanan akses berbasis role dan jejak audit untuk perubahan data penting.

## 3.3 Indikator Keberhasilan Produk

| **Indikator**  | **Target penerimaan**                                                                                            |
|----------------|------------------------------------------------------------------------------------------------------------------|
| Presensi siswa | Check-in/check-out berhasil hanya setelah seluruh validasi wajib terpenuhi.                                      |
| Duplikasi      | Satu siswa hanya memiliki satu record presensi per tanggal; check-in dan check-out berada pada record yang sama. |
| Akses role     | Siswa, Guru, dan Admin hanya dapat mengakses fungsi sesuai perannya.                                             |
| Jadwal         | Perubahan jadwal dan exception dapat dilakukan Admin tanpa perubahan source code.                                |
| Geofence       | Koordinat dan akurasi lokasi disimpan dan divalidasi terhadap radius aktif.                                      |
| Enrollment     | Siswa memiliki tepat tiga pose enrollment: depan, kiri, kanan.                                                   |
| K-Means        | Analisis K=3 dapat dijalankan on-demand dan hasil/centroid tersimpan sebagai histori.                            |
| Audit          | Perubahan status/manual action penting tercatat dengan pelaku dan waktu.                                         |
| Deployment     | Aplikasi dapat diakses melalui domain HTTPS pada VPS.                                                            |

# 4. Scope dan Batasan Produk

## 4.1 In Scope

- Autentikasi Admin, Guru Wali Kelas, dan Siswa.

- Pembuatan akun siswa/guru oleh Admin dan reset password dengan password sementara.

- Enrollment wajah siswa tiga pose: front, left, right.

- Liveness challenge kedipan sebelum auto capture.

- Presensi masuk dan pulang dengan satu tombol dinamis.

- Validasi waktu server, jadwal, geofence, liveness, dan face recognition.

- Status Hadir, Terlambat, Izin, Sakit, Alpa, Libur, dan Belum Absen sebagai state tampilan.

- Jadwal berbeda per hari serta schedule exception sekolah/kelas.

- Riwayat kelas per tahun ajaran.

- Foto bukti presensi terkompresi untuk Guru/Admin.

- Monitoring dan ekspor Excel.

- Analisis K-Means on-demand oleh Admin.

- Audit log, backup dasar, PWA, VPS, domain, dan HTTPS.

## 4.2 Out of Scope Versi Skripsi

- Presensi per mata pelajaran/per jam pelajaran.

- Pengajuan izin/sakit mandiri oleh siswa.

- Approval workflow Admin untuk enrollment wajah.

- Permission builder/RBAC kompleks di luar tiga role tetap.

- Mobile app native Android/iOS.

- Offline attendance; presensi wajib terhubung ke server.

- Advanced anti-spoofing AI, depth camera, atau face recognition berbasis deep learning sebagai fokus penelitian.

- Notifikasi push, WhatsApp, SMS, atau email otomatis.

- Multi-school/multi-tenant.

- Payroll, nilai, LMS, atau akademik di luar kebutuhan penempatan kelas dan presensi.

# 5. Aktor, Role, dan Hak Akses

| **Role**        | **Perangkat target** | **Kewenangan inti**                                                                                                                          | **Pembatasan utama**                                                                                         |
|-----------------|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| Siswa           | Mobile PWA           | Enrollment wajah, presensi masuk/pulang, kalender bulan berjalan, profil, ubah password.                                                     | Tidak dapat input izin/sakit, melihat foto bukti, melihat bulan lama, atau mengubah jadwal.                  |
| Guru/Wali Kelas | Desktop + Mobile PWA | Monitoring kelas, riwayat, foto bukti, input Izin/Sakit/Alpa untuk siswa yang belum auto-presence.                                           | Tidak dapat membuat akun, reset wajah, mengubah geofence/jadwal, atau mengubah Hadir/Terlambat hasil sistem. |
| Admin           | Desktop              | CRUD master data, akun, tahun ajaran/kelas, penempatan, monitoring global, wajah/reset, jadwal, geofence, exception, export, K-Means, audit. | Tidak melakukan presensi sebagai siswa; UI utama tidak ditargetkan untuk mobile.                             |

> **Aturan otorisasi**
> Penyembunyian tombol di UI bukan mekanisme keamanan. Seluruh route dan operasi data wajib memvalidasi role serta kepemilikan/lingkup data di backend.

# 6. Arsitektur dan Teknologi

## 6.1 Arsitektur Aplikasi

Arsitektur menggunakan modular monolith: satu aplikasi Flask dan satu repository, namun fungsi dipisah ke blueprint/routes dan service layer. Pendekatan ini menjaga project tetap sederhana untuk skripsi sekaligus mencegah seluruh logika terkumpul dalam satu file.

Browser / PWA  
│ HTTPS  
▼  
Nginx  
▼  
Gunicorn  
▼  
Flask  
┌────┼───────────────┐  
Routes Services Auth/RBAC  
│ │  
│ ┌───┼────────────┐  
│ │ │ │  
│ Face Geofence K-Means  
│ OpenCV Haversine sklearn  
▼  
MySQL + protected file storage

## 6.2 Stack Teknologi

| **Layer**   | **Teknologi**                     | **Keterangan**                                                |
|-------------|-----------------------------------|---------------------------------------------------------------|
| Frontend    | HTML, TailwindCSS, JavaScript     | Server-rendered templates + interaksi kamera/geolocation/PWA. |
| Backend     | Python Flask                      | Routing, auth, business rules, service layer.                 |
| Auth        | Flask-Login / session-based auth  | Role and session handling.                                    |
| Database    | MySQL                             | Master data, presensi, audit, konfigurasi, K-Means.           |
| DB access   | PyMySQL                           | Raw SQL sederhana, tanpa kebutuhan ORM kompleks.              |
| Face        | opencv-contrib-python             | Haar Cascade detector + LBPH recognizer.                      |
| Numerik     | NumPy                             | Preprocessing citra/array.                                    |
| K-Means     | scikit-learn                      | StandardScaler + KMeans.                                      |
| Data/export | pandas + openpyxl                 | Agregasi analisis dan export Excel.                           |
| Chart       | Chart.js                          | Visualisasi dashboard dan hasil clustering.                   |
| PWA         | Web App Manifest + Service Worker | Installable UI; presensi tetap online.                        |
| Web server  | Nginx + Gunicorn                  | Reverse proxy dan WSGI production.                            |
| Deployment  | Linux VPS + Domain + TLS          | Akses publik melalui HTTPS.                                   |

# 7. Aturan Bisnis Presensi

| **Kode** | **Aturan**                                                                                                                                        |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| BR-01    | Presensi harian terdiri dari check-in dan check-out, bukan presensi per mata pelajaran.                                                           |
| BR-02    | Waktu referensi berasal dari server, bukan jam perangkat siswa.                                                                                   |
| BR-03    | Satu tombol presensi menentukan aksi secara otomatis dari record hari itu dan jadwal efektif.                                                     |
| BR-04    | Check-in sebelum jam mulai diperbolehkan apabila kebijakan jadwal aktif mengizinkannya; backend tetap menggunakan nilai konfigurasi yang berlaku. |
| BR-05    | Status terlambat ditentukan ketika check-in melewati batas late_after yang dikonfigurasi.                                                         |
| BR-06    | Setelah check-in cutoff, check-in baru ditolak.                                                                                                   |
| BR-07    | Check-out hanya dapat dilakukan setelah checkout_start dan setelah check-in berhasil.                                                             |
| BR-08    | Lokasi harus berada dalam radius geofence aktif; radius awal 75 meter dan dapat diubah Admin.                                                     |
| BR-09    | Face identity yang dikenali harus sama dengan student_id pada akun yang login.                                                                    |
| BR-10    | Liveness kedipan wajib sebelum auto capture untuk enrollment dan presensi.                                                                        |
| BR-11    | Guru hanya dapat menetapkan Izin/Sakit/Alpa untuk siswa pada kelasnya yang belum memiliki auto-presence yang valid.                               |
| BR-12    | Guru tidak dapat mengubah Hadir/Terlambat yang dihasilkan sistem.                                                                                 |
| BR-13    | Jika setelah cutoff tidak ada auto-presence atau status manual yang sah, sistem dapat menetapkan Alpa.                                            |
| BR-14    | Hari libur/exception tidak boleh menghasilkan Alpa otomatis.                                                                                      |
| BR-15    | Exception lebih prioritas daripada jadwal reguler; class-specific exception lebih prioritas daripada school-wide bila keduanya relevan.           |
| BR-16    | Student hanya melihat kalender bulan berjalan; Guru/Admin dapat mengakses histori sebelumnya.                                                     |
| BR-17    | Foto bukti dapat dilihat Guru kelas terkait dan Admin, tidak oleh siswa.                                                                          |
| BR-18    | Reset data wajah membuat face_registered=false dan siswa wajib enrollment ulang pada login berikutnya.                                            |

# 8. User Journey End-to-End

## 8.1 Siswa Baru — Akun sampai Siap Presensi

8.  Admin membuat akun siswa menggunakan NISN sebagai username dan password awal.

9.  Sistem membuat profil siswa dengan face_registered=false.

10. Siswa login.

11. Jika must_change_password=true, siswa wajib mengganti password terlebih dahulu.

12. Backend mendeteksi face_registered=false dan memaksa redirect ke enrollment; route normal siswa tidak dapat dilewati melalui URL.

13. Siswa menangkap tiga pose secara berurutan: depan, kiri, kanan. Setiap pose melalui deteksi wajah, quality check, blink challenge, auto capture, suara shutter, dan feedback visual.

14. Setelah tiga pose valid, gambar disimpan, model LBPH dilatih/diperbarui, face_registered=true.

15. Sistem menampilkan sukses enrollment lalu mengakhiri session.

16. Siswa login kembali dan baru memperoleh akses dashboard normal.

## 8.2 Presensi Masuk/Pulang

17. Siswa membuka Dashboard dan menekan satu tombol presensi dinamis.

18. Backend mengambil jadwal efektif: exception kelas → exception sekolah → jadwal reguler.

19. Backend menentukan apakah aksi saat ini check-in, menunggu checkout, check-out, atau selesai.

20. Browser meminta lokasi dan mengirim latitude, longitude, serta accuracy.

21. Server menghitung jarak ke titik sekolah dan memvalidasi radius.

22. Kamera aktif; sistem memvalidasi wajah, kualitas gambar, dan blink.

23. Setelah blink valid, sistem auto capture dan melakukan face recognition.

24. Identitas hasil recognition harus sama dengan akun login.

25. Foto bukti disimpan terkompresi; data waktu/lokasi/score/status disimpan pada record tanggal tersebut.

26. Siswa menerima success screen dan dashboard diperbarui.

## 8.3 Guru Wali Kelas

27. Guru login dan melihat dashboard kelas yang menjadi tanggung jawabnya.

28. Guru meninjau siswa yang belum presensi dan ringkasan status hari ini.

29. Untuk siswa tanpa auto-presence, Guru dapat menetapkan Izin, Sakit, atau Alpa disertai keterangan sesuai kebijakan.

30. Guru dapat melihat kalender histori siswa, check-in/check-out, lokasi valid, dan foto bukti.

31. Setiap perubahan manual dicatat pada audit log.

## 8.4 Admin

32. Admin mengelola master siswa, guru, tahun ajaran, kelas, wali kelas, dan penempatan siswa.

33. Admin mengatur jadwal per hari, geofence, dan schedule exception.

34. Admin memonitor presensi seluruh kelas serta mengekspor data berdasarkan filter.

35. Admin dapat melihat/reset data wajah dan reset password akun.

36. Admin menjalankan analisis K-Means secara on-demand untuk periode tertentu dan membuka histori hasil sebelumnya.

37. Admin meninjau audit log untuk aktivitas penting.

# 9. Kebutuhan Fungsional

## 9.1 Autentikasi dan Akun

| **ID**     | **Requirement**                                                                          | **Prioritas** |
|------------|------------------------------------------------------------------------------------------|---------------|
| FR-AUTH-01 | Sistem menyediakan satu halaman login untuk semua role.                                  | Must          |
| FR-AUTH-02 | Backend mengarahkan pengguna berdasarkan role.                                           | Must          |
| FR-AUTH-03 | Password disimpan dalam bentuk hash, bukan plaintext.                                    | Must          |
| FR-AUTH-04 | Reset password oleh Admin menghasilkan password sementara dan must_change_password=true. | Must          |
| FR-AUTH-05 | Pengguna wajib mengganti password sementara sebelum masuk dashboard.                     | Must          |
| FR-AUTH-06 | Logout mengakhiri session aktif.                                                         | Must          |
| FR-AUTH-07 | Akun dapat dinonaktifkan tanpa menghapus histori.                                        | Must          |

## 9.2 Modul Siswa

| **ID**    | **Requirement**                                                                                              | **Prioritas** |
|-----------|--------------------------------------------------------------------------------------------------------------|---------------|
| FR-STU-01 | Siswa dengan face_registered=false wajib enrollment sebelum menggunakan dashboard normal.                    | Must          |
| FR-STU-02 | Dashboard menampilkan tanggal, kelas, status hari ini, waktu masuk/pulang, jadwal efektif, dan CTA presensi. | Must          |
| FR-STU-03 | CTA presensi berubah otomatis: Presensi Masuk / Pulang mulai ... / Presensi Pulang / Presensi Selesai.       | Must          |
| FR-STU-04 | Riwayat siswa hanya menampilkan kalender bulan berjalan.                                                     | Must          |
| FR-STU-05 | Klik tanggal menampilkan status, jam masuk, jam pulang, dan keterangan relevan tanpa foto/koordinat teknis.  | Must          |
| FR-STU-06 | Profil menampilkan informasi dasar, kelas aktif, ubah password, dan logout.                                  | Must          |

## 9.3 Modul Guru

| **ID**    | **Requirement**                                                                                                           | **Prioritas** |
|-----------|---------------------------------------------------------------------------------------------------------------------------|---------------|
| FR-TCH-01 | Dashboard menampilkan ringkasan kelas: total siswa, hadir, terlambat, izin, sakit, alpa/belum, dan daftar perlu ditinjau. | Must          |
| FR-TCH-02 | Guru hanya dapat membaca data siswa yang berada pada kelas yang menjadi tanggung jawabnya.                                | Must          |
| FR-TCH-03 | Guru dapat memfilter riwayat kelas berdasarkan bulan/status dan mencari siswa.                                            | Must          |
| FR-TCH-04 | Guru dapat menetapkan Izin/Sakit/Alpa untuk siswa tanpa auto-presence.                                                    | Must          |
| FR-TCH-05 | Keterangan wajib untuk Izin/Sakit; Alpa dapat menggunakan catatan opsional.                                               | Should        |
| FR-TCH-06 | Guru tidak dapat mengubah Hadir/Terlambat hasil sistem.                                                                   | Must          |
| FR-TCH-07 | Guru dapat melihat foto bukti dan ringkasan validasi lokasi siswa kelasnya.                                               | Must          |
| FR-TCH-08 | Guru dapat melihat histori bulan sebelumnya.                                                                              | Must          |

## 9.4 Modul Admin

| **ID**    | **Requirement**                                                                  | **Prioritas** |
|-----------|----------------------------------------------------------------------------------|---------------|
| FR-ADM-01 | CRUD siswa dan guru serta manajemen akun.                                        | Must          |
| FR-ADM-02 | Kelola tahun ajaran, kelas, wali kelas, dan student class enrollment.            | Must          |
| FR-ADM-03 | Kelola jadwal presensi per hari dan aktif/nonaktif.                              | Must          |
| FR-ADM-04 | Kelola school/class schedule exceptions.                                         | Must          |
| FR-ADM-05 | Kelola titik geofence dan radius.                                                | Must          |
| FR-ADM-06 | Monitoring seluruh presensi dengan filter tanggal, kelas, status, dan pencarian. | Must          |
| FR-ADM-07 | Export hasil filter presensi ke Excel.                                           | Must          |
| FR-ADM-08 | Lihat status enrollment wajah dan reset wajah per siswa.                         | Must          |
| FR-ADM-09 | Reset password siswa/guru.                                                       | Must          |
| FR-ADM-10 | Jalankan K-Means on-demand dan lihat histori run/centroid/result.                | Must          |
| FR-ADM-11 | Lihat audit log.                                                                 | Must          |

# 10. Face Recognition, Enrollment, dan Liveness

## 10.1 Enrollment Wajah

Enrollment menggunakan tepat tiga capture per siswa: front, left, dan right. Capture bersifat otomatis setelah seluruh syarat kualitas dan blink terpenuhi. Data wajah enrollment dipisahkan dari foto bukti presensi.

- Hanya satu wajah yang boleh berada pada area capture.

- Face detector menemukan wajah dan memastikan ukuran/posisi memadai.

- Quality check minimum mencakup blur dan brightness; implementasi dapat menambahkan centering/face size.

- Sistem memberikan instruksi pose dan meminta siswa berkedip.

- Blink valid memicu auto capture, suara shutter, dan pesan keberhasilan.

- Pose disimpan dengan unique constraint (student_id, pose).

- Setelah tiga pose valid, model LBPH dilatih ulang/diperbarui.

- Enrollment selesai tanpa approval Admin, kemudian session diputus untuk fresh login.

## 10.2 Pengenalan Wajah Saat Presensi

38. Deteksi wajah menggunakan Haar Cascade.

39. Wajah di-crop dan diproses konsisten dengan data enrollment (grayscale dan resize).

40. LBPH memprediksi label student_id dan distance/score.

41. Sistem menerapkan threshold hasil pengujian implementasi; nilai threshold tidak di-hardcode sebagai asumsi akademik tanpa pengujian.

42. Predicted student_id wajib sama dengan student_id akun login.

43. Jika mismatch atau score tidak memenuhi threshold, presensi ditolak dan tidak membuat record sukses.

## 10.3 Liveness

Liveness versi skripsi menggunakan blink challenge sebagai mekanisme sederhana untuk mengurangi penggunaan foto statis. Deteksi kedipan memerlukan facial landmarks/eye state; pemilihan library landmark dapat dilakukan saat implementasi tanpa mengubah requirement produk.

> **Batasan liveness**
> Blink challenge bukan anti-spoofing tingkat tinggi dan tidak menjamin perlindungan terhadap replay/video atau spoofing perangkat yang canggih. Hal ini harus dinyatakan sebagai batasan sistem, bukan diklaim sebagai solusi biometrik sempurna.

# 11. Geolocation dan Schedule Engine

## 11.1 Geofence

- Admin menyimpan nama lokasi, latitude, longitude, radius_meters, dan status aktif.

- Radius awal 75 meter; dapat diubah Admin.

- Browser mengirim latitude, longitude, dan accuracy dari Geolocation API.

- Server menghitung jarak menggunakan rumus Haversine atau metode geodesic ekuivalen.

- Validasi akhir dilakukan server-side.

- Accuracy disimpan sebagai bukti teknis; bila hasil lokasi tidak cukup andal, pengguna diminta mencoba kembali.

## 11.2 Jadwal Reguler

Jadwal terikat ke tahun ajaran dan hari dalam minggu. Setiap hari memiliki checkin_start, late_after, checkin_cutoff, checkout_start, dan is_active. Dengan struktur ini, Jumat dapat memiliki jam pulang yang berbeda tanpa mengubah hari lain.

## 11.3 Schedule Exception

| **Jenis**       | **Contoh perilaku**                                   |
|-----------------|-------------------------------------------------------|
| holiday         | Tidak ada presensi dan tidak membuat Alpa.            |
| exam            | Dapat mengubah jam presensi untuk tanggal tertentu.   |
| school_activity | Dapat mengubah jam atau aturan hari tertentu.         |
| early_dismissal | Override checkout_start menjadi lebih awal.           |
| custom          | Override nilai jadwal sesuai kebutuhan administratif. |

Exception dapat memiliki scope school atau class. Untuk scope class, class_id wajib ada. Mesin jadwal mengevaluasi aturan berdasarkan tanggal, kelas, tahun ajaran aktif, dan prioritas exception.

## 11.4 Finalisasi Alpa

Karena aplikasi berjalan pada VPS, finalisasi Alpa sebaiknya dijalankan oleh job terjadwal di server (misalnya Linux cron yang memanggil Flask CLI command). Job memeriksa siswa yang seharusnya hadir setelah cutoff efektif, melewati hari libur/exception, dan hanya membuat status Alpa bila belum ada auto-presence maupun status manual yang sah.

# 12. Status Presensi dan Kalender

| **Status**  | **Sumber**       | **Warna UI**    | **Aturan**                                                                                     |
|-------------|------------------|-----------------|------------------------------------------------------------------------------------------------|
| Hadir       | Sistem           | Hijau \#82D96B  | Check-in valid sebelum/hingga batas terlambat.                                                 |
| Terlambat   | Sistem           | Oranye \#FF9364 | Check-in valid setelah late_after dan sebelum cutoff.                                          |
| Izin        | Guru             | Kuning \#F4D563 | Siswa belum auto-presence; keterangan wajib.                                                   |
| Sakit       | Guru             | Biru \#6BB7F0   | Siswa belum auto-presence; keterangan wajib.                                                   |
| Alpa        | Sistem/Guru      | Merah \#F06D6D  | Tidak ada presensi/status sah setelah cutoff, atau ditetapkan Guru untuk siswa belum presensi. |
| Libur       | Schedule engine  | Abu \#C9C9C9    | Hari tanpa kewajiban presensi.                                                                 |
| Belum Absen | Derived UI state | Putih + border  | Belum ada record dan cutoff belum lewat. Tidak perlu disimpan sebagai enum status.             |

## 12.1 Kalender Siswa

Siswa hanya dapat melihat bulan berjalan. Backend membatasi query, sehingga pembatasan bukan hanya visual. Klik tanggal menampilkan status, jam masuk/pulang, dan keterangan sederhana.

## 12.2 Kalender Guru/Admin

Guru dan Admin dapat meninjau bulan sebelumnya. Guru dibatasi pada siswa kelasnya, sedangkan Admin dapat mengakses seluruh kelas.

# 13. Analisis K-Means

## 13.1 Tujuan

K-Means digunakan untuk mengelompokkan pola kehadiran siswa menjadi tiga kelompok yang kemudian diinterpretasikan sebagai pola tinggi, sedang, dan rendah berdasarkan karakteristik centroid. Nomor cluster tidak memiliki makna tetap; label diberikan setelah centroid dianalisis.

## 13.2 Fitur Final

| **Fitur**             | **Definisi operasional**                                                                                                                                                                                  |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| attendance_percentage | Persentase kehadiran fisik siswa dalam periode analisis. Untuk tidak menghukum izin/sakit sebagai ketidakdisiplinan, denominator operasional direkomendasikan mengecualikan hari Izin dan Sakit yang sah. |
| late_count            | Jumlah tanggal dengan status Terlambat pada periode.                                                                                                                                                      |
| alpha_count           | Jumlah tanggal dengan status Alpa pada periode.                                                                                                                                                           |

> **Formula operasional**
> effective_days = scheduled_school_days − izin − sakit. attendance_percentage = ((hadir + terlambat) / effective_days) × 100. Hari libur dan exception libur tidak masuk scheduled_school_days. Bila metodologi proposal menetapkan formula berbeda, formula penelitian harus diseragamkan sebelum implementasi final.

## 13.3 Pipeline

44. Admin memilih tahun ajaran dan periode.

45. Sistem mengambil data presensi yang relevan.

46. Sistem menghitung tiga fitur per siswa.

47. Data divalidasi terhadap missing/invalid values.

48. Fitur dinormalisasi/standardisasi (misalnya StandardScaler) agar skala persentase dan count tidak mendominasi satu sama lain.

49. K-Means dijalankan dengan K=3 dan random state tetap agar hasil pengujian reproducible.

50. Centroid hasil standardisasi di-inverse transform untuk interpretasi pada skala asli.

51. Cluster diberi label high/medium/low berdasarkan kombinasi attendance tinggi dan late/alpha rendah atau sebaliknya.

52. Run, centroid, dan result per siswa disimpan sebagai histori; hasil lama tidak ditimpa.

## 13.4 Evaluasi Penelitian

Untuk bagian evaluasi clustering, aplikasi dapat menghitung metric seperti Silhouette Score dan/atau Davies-Bouldin Index. Metric ini merupakan evaluasi kualitas cluster, bukan “akurasi K-Means” terhadap label ground truth. Penyajian metric dapat ditempatkan pada halaman detail analisis atau hanya pada laporan penelitian sesuai kebutuhan.

# 14. Data Model dan Database

## 14.1 Daftar Tabel

| **Tabel**                 | **Fungsi**                                                      |
|---------------------------|-----------------------------------------------------------------|
| users                     | Akun login dan role.                                            |
| students                  | Profil siswa dan status enrollment wajah.                       |
| teachers                  | Profil guru.                                                    |
| academic_years            | Periode tahun ajaran.                                           |
| classes                   | Kelas per tahun ajaran dan wali kelas.                          |
| student_class_enrollments | Riwayat penempatan siswa per tahun ajaran.                      |
| student_faces             | Tiga pose enrollment siswa.                                     |
| attendance_schedules      | Jadwal reguler per hari.                                        |
| schedule_exceptions       | Pengecualian jadwal sekolah/kelas.                              |
| geofence_settings         | Titik dan radius lokasi presensi.                               |
| attendance_records        | Record harian check-in/check-out, status, lokasi, dan evidence. |
| audit_logs                | Jejak perubahan/aksi penting.                                   |
| kmeans_runs               | Metadata satu proses analisis.                                  |
| kmeans_results            | Fitur dan hasil cluster per siswa.                              |
| kmeans_centroids          | Centroid dan label per cluster.                                 |

## 14.2 Relasi Inti

users ── students ── student_faces  
│ │  
│ ├── student_class_enrollments ── classes ── academic_years  
│ │ │  
│ ├── attendance_records └── teachers (wali kelas)  
│ │  
│ └── kmeans_results ── kmeans_runs ── kmeans_centroids  
│  
└── teachers  
  
academic_years ── attendance_schedules  
academic_years ── schedule_exceptions  
geofence_settings  
audit_logs

## 14.3 Constraint Kritis

- users.username UNIQUE.

- students.nisn UNIQUE dan students.user_id UNIQUE.

- (student_id, academic_year_id) UNIQUE pada student_class_enrollments.

- (student_id, pose) UNIQUE pada student_faces.

- (academic_year_id, day_of_week) UNIQUE pada attendance_schedules.

- (student_id, attendance_date) UNIQUE pada attendance_records.

- (run_id, student_id) UNIQUE pada kmeans_results.

- (run_id, cluster_number) UNIQUE pada kmeans_centroids.

## 14.4 Attendance Record

Satu record menyimpan dua sisi transaksi: check-in dan check-out. class_id disimpan sebagai historical snapshot sehingga perubahan kelas berikutnya tidak mengubah konteks presensi lama.

| **Kelompok field** | **Field utama**                                                                  |
|--------------------|----------------------------------------------------------------------------------|
| Identitas          | id, student_id, class_id, attendance_date                                        |
| Check-in           | checkin_at, latitude, longitude, accuracy, photo, face_score, liveness_verified  |
| Check-out          | checkout_at, latitude, longitude, accuracy, photo, face_score, liveness_verified |
| Status             | status, status_source, notes                                                     |
| Audit teknis       | created_by, updated_by, created_at, updated_at                                   |

## 14.5 Penyimpanan File

storage/  
├── faces/  
│ └── student\_\<id\>/  
│ ├── front.jpg  
│ ├── left.jpg  
│ └── right.jpg  
├── attendance/  
│ └── YYYY/MM/student\_\<id\>/  
│ ├── YYYY-MM-DD_checkin.webp  
│ └── YYYY-MM-DD_checkout.webp  
└── models/  
└── lbph_model.yml

File biometrik/evidence tidak diletakkan sebagai public static asset. Akses foto dilakukan melalui route terautentikasi yang memverifikasi role dan scope sebelum mengirim file.

# 15. Route dan Struktur Modul Flask

## 15.1 Struktur Repository

student-attendance/  
├── run.py  
├── config.py  
├── requirements.txt  
├── .env  
├── app/  
│ ├── \_\_init\_\_.py  
│ ├── database.py  
│ ├── auth/routes.py  
│ ├── student/routes.py  
│ ├── teacher/routes.py  
│ ├── admin/routes.py  
│ ├── attendance/routes.py  
│ ├── face/routes.py  
│ ├── kmeans/routes.py  
│ ├── services/  
│ │ ├── auth_service.py  
│ │ ├── attendance_service.py  
│ │ ├── face_service.py  
│ │ ├── image_quality_service.py  
│ │ ├── liveness_service.py  
│ │ ├── geofence_service.py  
│ │ ├── schedule_service.py  
│ │ ├── kmeans_service.py  
│ │ ├── export_service.py  
│ │ └── audit_service.py  
│ ├── templates/{auth,student,teacher,admin}/  
│ └── static/{css,js,audio,icons,illustrations}/  
├── storage/{faces,attendance,models}/  
├── database/{schema.sql,seed.sql}/  
└── tests/

## 15.2 Route Map

| **Modul**        | **Route utama**                                                    | **Fungsi**                          |
|------------------|--------------------------------------------------------------------|-------------------------------------|
| Auth             | /login, /logout, /change-password                                  | Autentikasi dan password sementara. |
| Student          | /student/dashboard, /student/history, /student/profile             | UI siswa.                           |
| Teacher          | /teacher/dashboard, /teacher/attendance, /teacher/students/\<id\>  | Monitoring wali kelas.              |
| Admin            | /admin/dashboard, /admin/students, /admin/teachers, /admin/classes | Master data.                        |
| Admin Attendance | /admin/attendance, /admin/settings/attendance, /admin/audit-logs   | Monitoring dan konfigurasi.         |
| Face             | /face/enroll, /face/verify, /face/reset                            | Enrollment/verifikasi/reset.        |
| Attendance       | /attendance/check, /attendance/submit                              | State presensi dan submission.      |
| K-Means          | /admin/kmeans, /admin/kmeans/run, /admin/kmeans/results/\<id\>     | Analisis on-demand.                 |

## 15.3 Prinsip Service Layer

Route bertanggung jawab pada input/output HTTP, sedangkan aturan bisnis ditempatkan pada service. attendance_service mengorkestrasi schedule, geofence, face, liveness, duplicate prevention, evidence storage, database transaction, dan audit. Pemisahan ini mempermudah pengujian dan perubahan aturan tanpa mencampur dengan rendering UI.

# 16. UI/UX dan Design System

## 16.1 Arah Visual

Design language: Soft Bento School App. Karakter visual bersih, rounded, hangat, sedikit playful untuk siswa, namun lebih data-oriented untuk Guru dan Admin. Bento digunakan sebagai pola komposisi, bukan dipaksakan pada tabel atau form.

| **Token**    | **Nilai** | **Pemakaian**        |
|--------------|-----------|----------------------|
| Background   | \#F6F4EE  | Canvas utama         |
| Surface      | \#FFFFFF  | Card, input, modal   |
| Primary      | \#725CF6  | CTA dan active state |
| Primary soft | \#EEE9FF  | Bento/accent lembut  |
| Accent lime  | \#DDF68A  | Secondary highlight  |
| Text         | \#191919  | Teks utama           |
| Muted        | \#707070  | Teks sekunder        |
| Border       | \#E7E4DD  | Border halus         |

## 16.2 Typography, Icon, dan Illustration

- Typography: Plus Jakarta Sans pada implementasi UI web; dokumen PRD menggunakan Inter untuk keterbacaan.

- Icon library: Phosphor Icons saja agar konsisten.

- Ilustrasi: sekitar 5–7 AI-generated custom illustrations dengan satu master art direction.

- Ilustrasi dipakai pada login, enrollment intro, success, error/location, empty state, dan onboarding bila diperlukan; bukan pada setiap halaman.

- Art direction: 2D editorial, rounded geometry, minimal facial detail, cream background, purple dominan, lime secondary, no glossy 3D.

## 16.3 Navigation

| **Role**     | **Navigation**                                                                                                                                        |
|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| Siswa        | Bottom navigation: Beranda, Riwayat, Profil. Presensi adalah CTA dashboard, bukan menu.                                                               |
| Guru mobile  | Bottom navigation: Dashboard, Presensi, Siswa; profil di topbar/avatar.                                                                               |
| Guru desktop | Sidebar: Dashboard, Presensi Kelas, Data Siswa, Profil.                                                                                               |
| Admin        | Desktop sidebar 256px: Dashboard, Data Siswa, Data Guru, Kelas & Tahun Ajaran, Monitoring Presensi, Analisis K-Means, Pengaturan Presensi, Audit Log. |

## 16.4 Component Inventory

- Button: Primary, Secondary, Ghost, Danger.

- Input, Select, Date Picker, Time Input, Search.

- StatusBadge, StatCard, ProgressCard.

- AttendanceCalendar.

- DataTable dan responsive card list.

- Modal desktop dan BottomSheet mobile.

- Sidebar, Topbar, BottomNav.

- CameraFrame + quality/liveness feedback.

- Toast, EmptyState, Skeleton/LoadingState.

- Tabs untuk Detail Siswa, Kelas/Tahun Ajaran, dan Pengaturan Presensi.

## 16.5 Responsive

| **Range**  | **Perilaku**                                |
|------------|---------------------------------------------|
| \< 640px   | Mobile; Student primary, Teacher mobile.    |
| 640–1023px | Tablet; Teacher responsive.                 |
| ≥ 1024px   | Desktop; Admin primary dan Teacher desktop. |

Admin adalah desktop-only secara desain. Pada viewport kecil dapat ditampilkan unsupported-device message. Ini adalah batasan UX, bukan pengganti otorisasi backend.

# 17. Security, Privacy, dan Audit

| **Area**        | **Requirement**                                                                                            |
|-----------------|------------------------------------------------------------------------------------------------------------|
| Transport       | HTTPS wajib pada production karena kamera, geolocation, session, dan data biometrik.                       |
| Password        | Hash password menggunakan mekanisme password hashing tepercaya; tidak menyimpan plaintext.                 |
| Session         | Cookie HttpOnly, Secure pada HTTPS, SameSite sesuai kebutuhan, session timeout yang wajar.                 |
| Authorization   | Role check pada backend; teacher scope dibatasi class_id yang sah.                                         |
| CSRF            | Form/action mutating wajib memiliki proteksi CSRF atau mekanisme ekuivalen.                                |
| Login abuse     | Rate limiting dasar dan pesan login generik direkomendasikan.                                              |
| Biometric files | Enrollment/evidence disimpan di protected storage, bukan URL public langsung.                              |
| Upload/input    | Validasi tipe/ukuran payload kamera dan sanitasi input form.                                               |
| Database        | Prepared statements/parameterized query; tidak membangun SQL dari input mentah.                            |
| Audit           | Reset wajah, reset password, perubahan status, perubahan jadwal/geofence, dan master-data penting dicatat. |
| Backup          | Backup database dan protected file storage dilakukan berkala.                                              |

## 17.1 Privasi Data Biometrik

Data wajah dan foto presensi adalah data sensitif secara operasional dan harus diperlakukan sebagai data terbatas. Akses diberikan hanya sesuai role, file tidak diekspos langsung, serta kebijakan retensi harus ditetapkan sekolah. Untuk penelitian, bukti harus disimpan hanya selama periode yang diperlukan untuk tujuan penelitian/operasional.

> **Kebijakan yang perlu disahkan sekolah**
> Durasi retensi foto evidence (misalnya beberapa bulan), prosedur penghapusan setelah retensi, dan mekanisme persetujuan/informasi kepada siswa/orang tua adalah kebijakan administratif yang harus ditetapkan sebelum penggunaan production penuh.

# 18. Non-Functional Requirements

| **ID** | **Requirement**                                                                                                             |
|--------|-----------------------------------------------------------------------------------------------------------------------------|
| NFR-01 | Aplikasi production hanya diakses melalui HTTPS.                                                                            |
| NFR-02 | Presensi tidak boleh mengandalkan jam perangkat client.                                                                     |
| NFR-03 | Semua operasi presensi penting berjalan dalam transaksi yang mencegah partial/duplicate write.                              |
| NFR-04 | UI siswa dioptimalkan untuk smartphone; Guru responsif; Admin desktop.                                                      |
| NFR-05 | PWA dapat diinstall, tetapi attendance tidak tersedia offline.                                                              |
| NFR-06 | Jika koneksi putus saat submit, UI harus menunjukkan status tidak tersimpan dan aman untuk retry tanpa duplikasi.           |
| NFR-07 | Database memakai index pada student_id, class_id, attendance_date, status, dan field query utama.                           |
| NFR-08 | Foto evidence dikompresi setelah recognition berhasil; recognition menggunakan frame berkualitas sebelum heavy compression. |
| NFR-09 | K-Means tidak dijalankan pada setiap transaksi presensi; hanya on-demand Admin.                                             |
| NFR-10 | Source code menggunakan environment variables untuk secret, DB credential, dan config production.                           |
| NFR-11 | Logging aplikasi tidak boleh menulis password atau payload biometrik mentah.                                                |
| NFR-12 | Desain mendukung satu sekolah dengan data ribuan siswa; pengujian kapasitas final menyesuaikan jumlah siswa aktual.         |

# 19. Deployment VPS, Domain, dan Operasional

## 19.1 Topologi Production

Internet  
│  
▼  
Domain + DNS  
│ HTTPS  
▼  
Nginx  
│ reverse proxy  
▼  
Gunicorn  
│  
▼  
Flask Application ───── MySQL  
│  
└──── Protected Storage (faces/evidence/models)

## 19.2 Production Checklist

- Linux VPS telah di-hardening dan hanya port yang diperlukan dibuka.

- Domain mengarah ke VPS dan TLS certificate aktif.

- Nginx menangani HTTPS, static assets, request size, dan reverse proxy.

- Gunicorn menjalankan Flask sebagai service systemd agar restart otomatis.

- MySQL tidak diekspos ke internet publik; akses lokal/private network saja.

- .env tidak masuk repository.

- Folder storage memiliki permission minimum yang diperlukan aplikasi.

- Cron/Flask CLI job tersedia untuk finalisasi Alpa dan backup terjadwal.

- Log rotation dikonfigurasi agar disk tidak penuh.

- Monitoring storage penting karena evidence photo dapat tumbuh cepat.

## 19.3 Backup

Minimum operasional: database dibackup harian; folder faces/evidence dibackup berkala sesuai kapasitas VPS; model LBPH dapat diregenerasi dari enrollment face tetapi tetap dapat disertakan dalam backup. Backup harus diuji dengan restore, bukan hanya dibuat.

# 20. Error Handling dan Edge Cases

| **Skenario**                   | **Perilaku yang diharapkan**                                                                     |
|--------------------------------|--------------------------------------------------------------------------------------------------|
| Izin kamera ditolak            | Tampilkan instruksi mengaktifkan permission; presensi tidak dilanjutkan.                         |
| Izin lokasi ditolak            | Tampilkan instruksi permission; tidak membuka kamera untuk submit sukses.                        |
| Lokasi di luar radius          | Tolak presensi dan tampilkan pesan area tidak valid.                                             |
| GPS accuracy buruk             | Minta pengguna mencoba kembali/berpindah ke area lebih terbuka.                                  |
| Lebih dari satu wajah          | Jangan auto capture; minta hanya satu orang di frame.                                            |
| Wajah blur/gelap               | Jangan auto capture; tampilkan feedback kualitas.                                                |
| Blink tidak terdeteksi         | Tetap menunggu dan tampilkan instruksi, dengan opsi retry setelah timeout.                       |
| Wajah tidak cocok              | Tolak tanpa menyimpan successful attendance.                                                     |
| Check-in duplikat              | Kembalikan state existing record; jangan insert baru.                                            |
| Checkout terlalu awal          | CTA disabled / server menolak.                                                                   |
| Check-in setelah cutoff        | Tolak check-in.                                                                                  |
| Hari libur                     | Tampilkan Libur; CTA presensi tidak tersedia.                                                    |
| Exception pulang awal          | Gunakan checkout_start dari exception.                                                           |
| Internet putus setelah capture | Jangan mengklaim sukses sebelum server commit; retry harus idempotent.                           |
| Student pindah kelas           | Presensi lama tetap memakai snapshot class_id lama.                                              |
| Reset wajah                    | Hapus/deaktifkan data enrollment lama, retrain model, face_registered=false.                     |
| Model LBPH corrupt/missing     | Fail closed untuk presensi wajah; Admin diberi alert/log, model dapat direbuild dari enrollment. |

# 21. Pengujian dan Acceptance Criteria

## 21.1 Jenis Pengujian

- Unit test: schedule, Haversine, status calculation, permission logic, K-Means feature calculation.

- Integration test: login, enrollment state, attendance submit, DB transaction, export.

- Role/access test: direct URL access lintas role dan teacher cross-class access.

- Device test: Android browser/PWA untuk camera + geolocation; desktop untuk Admin/Guru.

- Network test: koneksi lambat, retry, timeout, duplicate submit.

- Face flow test: pose, blur, low light, mismatch, blink, threshold.

- Schedule test: Jumat berbeda, holiday, class exception, early dismissal.

- K-Means test: empty period, insufficient students, reproducibility, centroid label mapping.

- Security smoke test: CSRF, session logout, protected photo URL, SQL injection input, password handling.

## 21.2 Acceptance Scenarios Kritis

| **AC** | **Given / When / Then**                                                                                                              |
|--------|--------------------------------------------------------------------------------------------------------------------------------------|
| AC-01  | Given siswa baru face_registered=false, when login valid, then tidak dapat membuka dashboard dan wajib enrollment.                   |
| AC-02  | Given tiga pose belum lengkap, when siswa mencoba menyelesaikan enrollment, then face_registered tetap false.                        |
| AC-03  | Given siswa berada di luar radius, when submit presensi, then tidak ada check-in/check-out tersimpan.                                |
| AC-04  | Given wajah yang dikenali bukan akun login, when submit, then attendance ditolak.                                                    |
| AC-05  | Given belum check-in, when waktu valid dan seluruh verifikasi berhasil, then satu attendance record dibuat.                          |
| AC-06  | Given sudah check-in dan belum checkout_start, when mencoba submit, then server menolak checkout.                                    |
| AC-07  | Given sudah check-in dan waktu \>= checkout_start, when verifikasi berhasil, then record yang sama mendapat checkout_at.             |
| AC-08  | Given Guru kelas A, when membuka siswa kelas B melalui URL, then access denied.                                                      |
| AC-09  | Given siswa sudah Hadir/Terlambat, when Guru mencoba mengubah status, then operasi ditolak backend.                                  |
| AC-10  | Given school holiday, when job Alpa berjalan, then tidak ada siswa yang dibuat Alpa untuk hari tersebut.                             |
| AC-11  | Given class-specific early dismissal, when siswa kelas tersebut check-out, then schedule exception digunakan.                        |
| AC-12  | Given Admin menjalankan K-Means, when selesai, then run, centroid, feature, dan hasil setiap siswa tersimpan tanpa menimpa run lama. |

# 22. Rencana Implementasi

| **Fase**                     | **Output utama**                                                                             |
|------------------------------|----------------------------------------------------------------------------------------------|
| Fase 1 — Foundation          | Repository, config, MySQL schema, seed, auth, role decorator, base layout.                   |
| Fase 2 — Master Data         | Admin siswa, guru, tahun ajaran, kelas, enrollment kelas, reset password.                    |
| Fase 3 — Schedule & Geofence | Jadwal per hari, exception, geofence, schedule service, Haversine.                           |
| Fase 4 — Face Enrollment     | Camera UI, quality check, blink, 3 pose storage, LBPH training/reset.                        |
| Fase 5 — Attendance Engine   | Dynamic CTA, check-in/out, geofence, face verify, evidence, duplicate prevention.            |
| Fase 6 — Teacher Module      | Dashboard kelas, status manual, history, evidence photo.                                     |
| Fase 7 — Admin Monitoring    | Monitoring global, filters, detail, export Excel, audit.                                     |
| Fase 8 — K-Means             | Feature aggregation, scaling, clustering, centroid interpretation, history, charts.          |
| Fase 9 — PWA & UX Polish     | Manifest, service worker shell caching, loading/error/empty states, illustration/icon final. |
| Fase 10 — Deployment & QA    | VPS, Nginx, Gunicorn, domain, TLS, cron, backup, test, bug fixing, demo data.                |

## 22.1 Urutan Dependensi

Database/Auth  
↓  
Master Data + Tahun Ajaran/Kelas  
↓  
Schedule + Geofence  
↓  
Face Enrollment  
↓  
Attendance Engine  
├── Teacher Monitoring  
└── Admin Monitoring/Export  
↓  
K-Means  
↓  
PWA + Deployment + QA

# 23. Risiko dan Mitigasi

| **Risiko**                               | **Dampak**                                        | **Mitigasi**                                                                                                |
|------------------------------------------|---------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| GPS spoofing pada perangkat              | Lokasi dapat dipalsukan di level OS.              | Geofence + face + liveness; nyatakan sebagai limitasi. Tidak mengklaim geolocation anti-spoof sempurna.     |
| Blink spoof/replay                       | Liveness sederhana dapat dilewati teknik canggih. | Gunakan challenge real-time dan kualitas wajah; scope penelitian tidak mengklaim anti-spoof tingkat tinggi. |
| LBPH kurang stabil pada pencahayaan/pose | False reject/false match.                         | Quality check, 3 pose, threshold hasil pengujian, environment testing, reset/re-enrollment.                 |
| Jumlah hanya 3 gambar enrollment         | Data training terbatas.                           | Jaga capture berkualitas dan konsisten; dokumentasikan sebagai constraint.                                  |
| Evidence memenuhi storage VPS            | Disk penuh.                                       | Compression, monitoring disk, retention policy, backup/archival.                                            |
| Koneksi internet sekolah tidak stabil    | Presensi gagal/timeout.                           | Clear retry, idempotent endpoint, jangan menampilkan sukses sebelum commit.                                 |
| Salah konfigurasi jadwal                 | Status salah.                                     | Validation form, preview effective schedule, audit log, confirmation untuk perubahan kritis.                |
| K-Means sulit diinterpretasi             | Label cluster menyesatkan.                        | Interpretasi dari centroid; simpan feature/centroid; jangan mengikat nomor cluster ke label.                |
| Data biometrik bocor                     | Risiko privasi tinggi.                            | Protected storage, HTTPS, role access, least privilege, retention, backup aman.                             |

# 24. Out of Scope dan Roadmap

Fitur berikut tidak diperlukan untuk kelulusan versi skripsi, tetapi dapat menjadi roadmap bila sistem dikembangkan menjadi produk operasional sekolah penuh:

- Notifikasi orang tua ketika terlambat/alpa.

- Pengajuan izin/sakit oleh orang tua/siswa dengan approval wali kelas.

- Advanced face anti-spoofing/deep learning.

- Object storage eksternal untuk evidence photo.

- Multi-location geofence.

- Integrasi data akademik/SIAKAD sekolah.

- Multi-school tenancy.

- Push notification PWA.

- Policy-based retention otomatis dan archival.

- Dashboard kepala sekolah khusus analitik tanpa akses konfigurasi.

# 25. Definition of Done

- Seluruh requirement Must pada PRD telah diimplementasikan dan lulus acceptance test.

- Tiga role berhasil diuji dengan akses yang benar dan percobaan bypass URL ditolak.

- Enrollment 3 pose + blink + auto capture berjalan pada perangkat Android target.

- Check-in/check-out berjalan dengan jadwal, geofence, face, liveness, dan server time.

- Schedule exception dan finalisasi Alpa berjalan tanpa menghasilkan Alpa pada hari libur.

- Guru dapat memonitor kelas dan menetapkan Izin/Sakit/Alpa hanya sesuai aturan.

- Admin dapat melakukan seluruh konfigurasi, monitoring, export, reset, dan audit.

- K-Means on-demand menyimpan run, centroid, result, dan histori dengan K=3.

- PWA dapat diinstall dan menunjukkan pesan yang benar ketika offline.

- Aplikasi berhasil dideploy di VPS melalui domain HTTPS.

- Backup dan restore dasar telah diuji.

- Dokumentasi setup, environment, schema, dan deployment tersedia.

- Tidak ada password/secret di repository dan protected photos tidak dapat diakses tanpa otorisasi.

# Lampiran A — Ringkasan Halaman

| **Role** | **Halaman utama**                                                                                                                           |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------|
| Semua    | Login; Ganti Password.                                                                                                                      |
| Siswa    | Enrollment; Dashboard; Camera Presensi; Success; Riwayat; Detail Tanggal; Profil.                                                           |
| Guru     | Dashboard; Presensi Kelas; Kelola Status; Data Siswa; Detail Siswa; Detail Presensi; Profil.                                                |
| Admin    | Dashboard; Data Siswa; Detail Siswa; Data Guru; Kelas & Tahun Ajaran; Monitoring; Detail Presensi; K-Means; Pengaturan Presensi; Audit Log. |

# Lampiran B — Mapping Status UI

| **Status**  | **Color token**   | **Catatan**   |
|-------------|-------------------|---------------|
| Hadir       | \#82D96B          | Semantic only |
| Alpa        | \#F06D6D          | Semantic only |
| Izin        | \#F4D563          | Semantic only |
| Sakit       | \#6BB7F0          | Semantic only |
| Terlambat   | \#FF9364          | Semantic only |
| Libur       | \#C9C9C9          | Semantic only |
| Belum Absen | \#FFFFFF + border | Derived state |

# Lampiran C — Mapping Phosphor Icons

| **Fungsi**          | **Icon**                      |
|---------------------|-------------------------------|
| Beranda/Dashboard   | House / SquaresFour           |
| Riwayat             | CalendarDots                  |
| Profil              | UserCircle                    |
| Siswa               | Student                       |
| Guru                | ChalkboardTeacher             |
| Presensi            | CalendarCheck / ClipboardText |
| K-Means             | ChartScatter                  |
| Pengaturan          | SlidersHorizontal             |
| Audit               | ClockCounterClockwise         |
| Logout              | SignOut                       |
| Menu row action     | DotsThree                     |
| Password visibility | Eye / EyeSlash                |

# Lampiran D — Keputusan Desain yang Dikunci

- Satu repository Flask modular monolith.

- Siswa mobile PWA; Guru responsif; Admin desktop.

- Frontend HTML/TailwindCSS/JavaScript, bukan React/Vue.

- MySQL + PyMySQL; tidak membutuhkan ORM kompleks untuk versi awal.

- Haar Cascade + LBPH; enrollment tepat tiga pose.

- Blink challenge dan auto capture dengan suara/visual feedback.

- Satu tombol presensi dinamis.

- Radius default 75 m, configurable.

- Jadwal per hari dan schedule exception.

- Siswa tidak mengajukan izin; Guru yang menetapkan status manual.

- Siswa tidak melihat foto evidence.

- Reset password melalui Admin + temporary password + forced change.

- K-Means features: attendance_percentage, late_count, alpha_count; K=3; run on-demand.

- Deployment final: VPS + domain + HTTPS.

- UI: Soft Bento School App; palette cream/purple/lime; Phosphor Icons; 5–7 custom AI illustrations.

**— Akhir Dokumen PRD Versi 1.0 —**
