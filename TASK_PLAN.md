# Rencana Task Pengembangan Sistem Presensi

**Acuan:** [PRD versi 1.0](PRD_Sistem_Presensi_SMA_Negeri_4_Lhokseumawe.md) dan [AGENTS.md](AGENTS.md).  
**Tanggal:** 22 September 2026.  
**Status:** T00–T03 selesai; T04 memiliki POC offline tetapi uji lapangan terhambat; T05–T14 selesai; T13 siap pada level implementasi dan uji sintetis, sedangkan aktivasi nyata menunggu koordinat sekolah dan kebijakan accuracy; T15–T35 masih TODO.

## Cara menggunakan rencana ini

- Kerjakan satu task aktif sampai hasilnya dapat diperiksa. Setiap task memiliki satu hasil utama, dependensi, dan kriteria selesai.
- Nomor menunjukkan urutan yang disarankan. Dependensi adalah prasyarat minimum; task berikutnya boleh dikerjakan jika prasyaratnya selesai.
- Gunakan status `TODO`, `DOING`, `BLOCKED`, `DONE`. Jika terhambat, tulis penyebab spesifik dan lanjutkan task independen yang sudah jelas.
- Untuk task fitur, hasil mencakup schema/query yang dibutuhkan, service/route, UI terkait, validasi, dan pengujian yang relevan. Jangan membuat task terpisah untuk setiap file atau tombol.
- `DONE` berarti kriteria selesai terpenuhi dan bukti verifikasi tercatat. Mock/simulasi tidak menjadi bukti bahwa kamera, GPS, atau biometrik sudah berfungsi di perangkat nyata.
- Batas praktis satu task adalah satu perubahan yang nyaman direview dan didemokan. Bila terlalu besar, pecah menjadi maksimal beberapa subtask dengan hasil terpisah; jangan memecah sekadar berdasarkan jumlah file.
- Tidak perlu persetujuan ulang untuk setiap task yang sudah masuk lingkup implementasi yang diminta pengguna. Klarifikasi hanya keputusan produk yang masih terbuka dan benar-benar memengaruhi task.
- Rencana ini tidak otomatis menjalankan implementasi, membuat task baru di aplikasi Codex, atau mengizinkan deployment. Ia menjadi backlog bersama untuk pelaksanaan berikutnya.
- Tabel tahap adalah ringkasan; bagian **Breakdown pelaksanaan T00–T35** adalah checklist kerja. ID seperti `T00.1` dapat digunakan untuk melanjutkan pekerjaan secara spesifik. Subtask dikerjakan berurutan dalam task induknya, kecuali dinyatakan independen.
- Checklist yang dicentang harus mempunyai hasil yang dapat diperiksa. Seluruh subtask selesai belum cukup jika kriteria selesai task induk belum terpenuhi. Detail teknis boleh disempurnakan saat task dimulai berdasarkan kondisi kode dan dokumentasi saat itu.

## Batas agar tetap sederhana

- Tetap satu aplikasi Flask, satu MySQL, HTML/templates + TailwindCSS + JavaScript, dan PyMySQL. Route tipis dengan service per kebutuhan; hindari generic repository, plugin system, dan lapisan abstraksi tanpa pemakaian nyata.
- Tambahkan modul, dependency, dan komponen saat diperlukan. Tidak perlu membuat semua folder kosong atau seluruh sistem komponen di awal.
- Gunakan tiga role tetap dan pemeriksaan scope kelas langsung. Tidak membangun permission builder.
- Gunakan file SQL berurutan untuk perubahan schema dan catat versi yang diterapkan; tidak membangun migration engine sendiri. Jangan meminta pengguna menghapus database setiap kali schema berubah.
- Mulai dengan proses sinkron untuk enrollment/training dan K-Means, disertai pengendalian konkurensi sederhana. Tambahkan antrean pekerjaan hanya bila pengukuran menunjukkan kebutuhan nyata.
- Tidak menambahkan Redis, Celery, WebSocket, microservices, Kubernetes, atau Docker sebagai prasyarat versi awal. Pembaruan dashboard cukup melalui request biasa; kebutuhan lebih lanjut harus dibuktikan.
- Tidak membangun offline attendance, push notification, izin mandiri siswa, multi-school, atau fitur roadmap lain.
- Keamanan, transaksi, audit, dan pengujian aturan penting tetap bagian minimum. Penyederhanaan tidak boleh menghilangkan validasi server atau perlindungan data wajah.
- Tidak memberi estimasi tanggal sebelum uji biometrik awal dan kondisi perangkat diketahui. Nilai kemajuan dari task yang terverifikasi, bukan banyaknya halaman yang dibuat.

## Hasil T00 — baseline dan keputusan bertahap

T00.1–T00.6 diselesaikan pada 22 September 2026. Bagian ini membedakan hal yang sudah dikunci oleh PRD, batas implementasi yang diturunkan dari PRD, keputusan yang masih terbuka, dan kebutuhan eksternal yang belum tersedia. Tanda `terbuka` berarti belum menjadi keputusan sekolah dan tidak boleh diam-diam diubah menjadi perilaku aplikasi.

### Baseline yang sudah dikunci oleh PRD (T00.1)

- Produk berada dalam scope versi skripsi dengan tiga role tetap: Siswa, Guru/Wali Kelas, dan Admin (PRD §4–5).
- Arsitektur adalah satu Flask modular monolith dengan HTML/template, TailwindCSS, JavaScript, MySQL + PyMySQL, PWA, dan deployment target VPS + domain + HTTPS (PRD §6, §19). React/Vue, native app, microservices, dan offline attendance berada di luar scope (PRD §4.2).
- Attendance menggunakan satu record per siswa/tanggal; check-in dan check-out berada pada record yang sama. Backend adalah otoritas waktu server, jadwal, geofence, liveness, face match, role/scope, dan commit transaksional (PRD §7, §14.3–14.4, §18).
- Jadwal efektif memprioritaskan exception kelas, lalu exception sekolah, lalu jadwal reguler. Hari libur tidak menerima presensi dan tidak menghasilkan Alpa otomatis. Radius geofence awal 75 meter dan dapat dikonfigurasi Admin (PRD §7, §11, §20).
- Enrollment wajah menggunakan tepat tiga pose (`front`, `left`, `right`) dengan Haar Cascade + LBPH, quality check, blink challenge, auto capture, dan protected storage (PRD §10, §14.5). Blink bukan klaim anti-spoofing tingkat tinggi (PRD §10.3, §23).
- Guru menetapkan Izin/Sakit/Alpa untuk siswa yang belum memiliki auto-presence sah; Guru tidak mengubah Hadir/Terlambat hasil sistem. Siswa tidak melihat foto evidence (PRD §5, §7, §9, §12).
- K-Means hanya dijalankan on-demand oleh Admin, K=3, dengan fitur `attendance_percentage`, `late_count`, dan `alpha_count`; run, centroid, serta hasil siswa disimpan sebagai histori (PRD §13–14).
- Kontrak UI yang dikunci: Soft Bento School App, palette cream/purple/lime, Phosphor Icons, navigasi berbeda per role, Siswa mobile PWA, Guru responsif, dan Admin desktop (PRD §16, Lampiran A–D).

### Batas implementasi yang langsung dapat dipakai (T00.1/T00.3)

- Mulai dari fondasi kecil dan dapat dijalankan; tidak membuat seluruh folder, service, atau component library sebelum dipakai.
- Route mengurus HTTP dan service mengurus aturan bisnis. Query memakai parameter; file wajah/evidence/model tidak diletakkan di static publik.
- Secrets berasal dari environment; data uji harus sintetis/berizin. Uji unit/integrasi tidak boleh disebut sebagai bukti kamera, GPS, atau biometrik perangkat nyata.
- Enrollment/training dan K-Means dimulai sinkron. Antrean/worker hanya dipertimbangkan bila pengukuran nyata menunjukkan kebutuhan.
- Semua task berikut boleh menyempurnakan detail teknis, tetapi tidak boleh mengubah baseline PRD tanpa keputusan yang dicatat.

### Keputusan yang perlu diselesaikan bertahap (T00.2–T00.5)

Ini adalah daftar pertanyaan dan rekomendasi untuk dibahas bersama pengguna/pihak sekolah. Rekomendasi tidak mengubah PRD sampai disetujui.

| Keputusan | Status | Batas waktu | Rekomendasi / pertanyaan yang harus dijawab | Penentu |
|---|---|---|---|---|
| Zona waktu dan batas presensi | Baseline sementara | Sebelum presensi produksi/T18 | T11 memakai `Asia/Jakarta`, mulai dan cutoff inklusif, check-in sebelum `checkin_start` ditolak, `late_after` mulai terlambat, dan belum ada batas akhir check-out. Jam tetap dikelola Admin; perubahan kebijakan harus dicatat sebelum presensi produksi. | Pengguna/pihak sekolah |
| Histori kelas | Baseline sementara | Sebelum T10 / sebelum perpindahan intra-tahun | Implementasi T10 mengikuti constraint PRD `(student_id, academic_year_id) UNIQUE`: satu penempatan per Siswa dalam satu tahun ajaran. Jika sekolah membutuhkan perpindahan intra-tahun, tetapkan periode efektif dan migrasi histori sebelum mengubah constraint; snapshot `class_id` pada attendance lama tetap wajib. | Pengguna/pihak sekolah |
| Histori jadwal dan exception | Terbuka | Sebelum T11/T12 | Usulan: exception bertumpuk pada scope dan tanggal yang sama ditolak; konfigurasi baru tidak menulis ulang interpretasi attendance lama. Sepakati aturan bila ada kebutuhan koreksi historis. | Pengguna/pihak sekolah |
| Status manual | Sebagian terkunci | Sebelum T24 | Terkunci: Guru hanya untuk kelasnya dan siswa tanpa auto-presence sah; Hadir/Terlambat sistem tidak dapat diubah. Tetapkan apakah Izin/Sakit selalu wajib keterangan, batas koreksi, dan interaksi status manual dengan submit otomatis berikutnya. | Pengguna/pihak sekolah |
| Lokasi dan biometrik | Sebagian terkunci | Sebelum T13/T15/T16 | Terkunci: radius awal 75 m, validasi server, tiga pose, blink, Haar/LBPH. Tetapkan batas `accuracy`, quality check, timeout blink, dan threshold LBPH berdasarkan uji perangkat; jangan menebak angka final. Koordinat sekolah harus diverifikasi. | Pengguna + hasil uji |
| Metodologi K-Means | Sebagian terkunci | Sebelum T27 | Terkunci: K=3, tiga fitur, on-demand, histori run. Selaraskan formula `effective_days`, denominator nol, periode final, siswa yang memenuhi syarat, data kurang dari tiga cluster, dan aturan label centroid dengan metodologi penelitian. | Pengguna/pembimbing |
| Operasional dan privasi | Terbuka | Sebelum T34/T35 | Siapkan perangkat target, perkiraan jumlah siswa, VPS/domain, pemilik akses, retensi evidence, prosedur penghapusan, dan persetujuan/informasi biometrik. Tidak menghambat T01–T03. | Pihak sekolah/operator |

### Kebutuhan eksternal dan statusnya (T00.4)

| Kebutuhan | Status saat T00 selesai | Dampak |
|---|---|---|
| Koordinat sekolah dan radius operasional | Belum diberikan | Implementasi dan uji sintetis T13 selesai; konfigurasi aktif, uji lapangan, dan production tertahan sampai titik diverifikasi serta kebijakan accuracy ditetapkan. |
| Perangkat Android/browser + HTTPS uji | Belum diverifikasi | T04/T32 belum dapat dinyatakan selesai; jangan memakai simulasi sebagai bukti perangkat. |
| Sampel wajah berizin | Belum tersedia di repository | T04/T15/T16 memerlukan data uji berizin; gunakan fixture non-biometrik untuk task lain. |
| Jumlah siswa dan pola jam masuk | Belum diberikan | T33 hanya dapat memakai dataset sintetis sampai kapasitas target diketahui. |
| VPS/domain dan kebijakan data sekolah | Belum tersedia | T34/T35 belum dapat dijalankan; tidak menghambat fondasi lokal. |
| Pemilik keputusan produk/metodologi | Belum ditetapkan dalam repository | Pertanyaan di tabel di atas perlu dijawab pengguna/pihak sekolah/pembimbing sesuai topiknya. |

### Prioritas pembahasan (T00.5)

1. Tidak ada keputusan produk tambahan yang diperlukan untuk memulai T01–T03; fondasi boleh berjalan dengan environment lokal dan fixture sintetis.
2. Jawaban histori kelas diperlukan sebelum T10.
3. Jawaban timezone dan batas waktu diperlukan sebelum T11, sedangkan konflik exception diperlukan sebelum T12.
4. Koordinat terverifikasi dan kebijakan accuracy diperlukan sebelum geofence T13 dapat diaktifkan untuk presensi nyata.
5. Bukti perangkat/sampel berizin menentukan T04 serta threshold T15–T16; tidak boleh diganti klaim dari unit test.
6. Kebijakan status manual diperlukan sebelum T24; formula K-Means sebelum T27; operasional/privacy sebelum T34–T35.

T00 mengajukan pertanyaan-pertanyaan tersebut kepada pengguna melalui catatan ini. Jawaban dapat dimasukkan kembali ke tabel tanpa mengubah PRD lain secara diam-diam.

### Penutupan T00 (T00.6)

- T00 berstatus selesai karena setiap isu sudah memiliki status, batas task, rekomendasi/pertanyaan, dan penentu yang perlu memberi jawaban.
- T01 dapat dimulai sekarang. T01 tidak membutuhkan koordinat, wajah, VPS, atau keputusan formula K-Means.
- T10, T11–T13, T15–T16, T24, T27, dan T34–T35 tetap memiliki gate keputusan/eksternal sebagaimana tabel di atas.
- Tidak ada kode aplikasi, kredensial, koordinat nyata, wajah, atau data produksi yang dibuat sebagai bagian T00.

## A. Fondasi dan uji risiko awal

**Hasil tahap:** aplikasi dasar dapat dijalankan, akses tiga role aman, dan ada bukti awal kelayakan biometrik.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| DONE · T00 | **Rapikan keputusan awal.** Tinjau tabel keputusan; catat keputusan yang sudah tersedia dan pemilik kebutuhan yang belum jelas. | — | Ambiguitas memiliki batas tahap penyelesaian; tidak ada asumsi tersembunyi yang dianggap keputusan sekolah. Tidak menunggu seluruh keputusan production untuk memulai fondasi. |
| DONE · T01 | **Aplikasi minimal yang dapat dijalankan.** Entry point Flask, konfigurasi environment, dependency awal, `.gitignore`, `.env.example`, halaman sederhana, petunjuk setup Windows. | T00 | Fresh setup dapat menjalankan aplikasi; konfigurasi rahasia tidak masuk repository; README berisi perintah yang sudah dicoba. |
| DONE · T02 | **Koneksi MySQL dan akun awal.** Schema `users`, koneksi/transaction helper secukupnya, prosedur perubahan schema, pembuatan Admin pertama secara aman, fixture tes sintetis. | T01 | Database kosong dapat disiapkan; username unik; password tersimpan sebagai hash; kegagalan transaksi rollback; setup tidak menyimpan password default di SQL. |
| DONE · T03 | **Login, logout, dan akses tiga role.** Satu form login, session, role guard, penolakan akun nonaktif, CSRF aksi mutasi, redirect per role, perlindungan dasar percobaan login. | T02 | Login/logout berfungsi; akses URL lintas role ditolak backend; akun nonaktif ditolak termasuk session yang sudah aktif; request mutasi tanpa CSRF sah ditolak. |
| BLOCKED · T04 | **Uji awal kamera, blink, dan LBPH.** POC offline OpenCV sudah tersedia; percobaan Android melalui HTTPS, tiga pose, kualitas frame, eye-state/blink, dan pencocokan wajah menunggu perangkat serta sampel berizin. | T01 | Ada bukti uji perangkat nyata, contoh berhasil/gagal, dan keputusan kelayakan untuk T15. Sampai perangkat/data tersedia, bagian lapangan tetap terhambat dan biometrik belum dinyatakan siap. Tidak membuat presensi produksi pada task ini. |

T04 dilakukan lebih awal untuk mengurangi risiko teknis; enrollment produk tetap menunggu master data dan aturan akses. HTTPS untuk percobaan perangkat tidak harus menunggu deployment production.

## B. UI dasar, akun, dan master data

**Hasil tahap:** Admin dapat menyiapkan pengguna dan kelas; shell UI mengikuti kontrak PRD.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| DONE · T05 | **Layout tiga role dan komponen dasar.** Token PRD, font/icon, navigasi, button/form/status badge, feedback error/loading, login yang konsisten. | T03 | Siswa mobile, Guru mobile/desktop, dan Admin desktop memiliki navigasi benar; menu belum tersedia diberi state jelas; hanya komponen yang langsung dipakai dibuat. |
| DONE · T06 | **Ganti password dan profil.** Forced password change, ubah password sendiri, profil dasar dan logout. | T03, T05 | Password sementara tidak dapat melewati gate melalui URL; password lama tidak berlaku setelah perubahan; pengguna hanya mengakses profilnya. |
| DONE · T07 | **Audit minimum dan protected storage.** Tabel audit, pencatatan pelaku/waktu/aksi, helper penyimpanan privat dengan validasi payload/path. | T02, T03 | Aksi contoh tercatat tanpa password/payload biometrik; file tidak dapat dibaca melalui public static atau path traversal. Otorisasi file per kelas ditambahkan bersama fitur evidence. |
| DONE · T08 | **Kelola Guru.** Tambah, daftar/cari, edit profil, nonaktifkan, dan reset password sementara melalui Admin. | T05, T06, T07 | Input tidak valid/duplikat ditolak; reset memaksa perubahan password; nonaktif tidak menghapus histori; perubahan penting diaudit. |
| DONE · T09 | **Kelola Siswa.** Tambah, daftar/cari, edit, nonaktifkan, reset password; NISN sebagai username dan status awal belum enrollment. | T05, T06, T07 | NISN unik; akun dan profil tersimpan atomik; reset serta nonaktif aman dan diaudit; tersedia data sintetis untuk langkah berikutnya. |
| DONE · T10 | **Tahun ajaran, kelas, wali kelas, dan penempatan.** CRUD sederhana serta penempatan siswa mengikuti baseline satu penempatan per tahun ajaran. | T08, T09; baseline constraint PRD | Tahun ajaran/kelas aktif dapat ditentukan; penempatan ganda yang tidak sah ditolak; tidak menghapus relasi yang masih dipakai; scope Guru dapat dihitung dan diuji. |

## C. Jadwal dan lokasi

**Hasil tahap:** sistem dapat menjawab siapa wajib hadir, kapan, dan di lokasi mana, tanpa biometrik atau transaksi presensi terlebih dahulu.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| DONE · T11 | **Jadwal reguler dan waktu aplikasi.** Form Admin per hari/tahun ajaran, validasi urutan jam, aktif/nonaktif, service waktu/jadwal. | T10; baseline timezone dan batas waktu | Jadwal Jumat dapat berbeda; batas waktu diuji sebelum/tepat/sesudah batas; perubahan diaudit dan mengikuti baseline; tidak memakai jam browser sebagai otoritas. |
| DONE · T12 | **Exception dan preview jadwal efektif.** Exception sekolah/kelas, libur, pulang awal, dan preview untuk tanggal/kelas tertentu. | T11; baseline konflik tercatat | Prioritas kelas → sekolah → reguler, pewarisan field, libur, konflik, audit, dan preview diverifikasi melalui unit serta smoke MySQL. |
| DONE · T13 | **Pengaturan dan validasi geofence.** Form Admin, pemeriksaan lokasi browser, service jarak server, dan uji sintetis tersedia. | T07, T10; koordinat dan kebijakan accuracy diperlukan untuk aktivasi nyata | Radius awal 75 m dapat diubah; lokasi di dalam/tepat batas/luar radius diuji; data tidak valid dan accuracy buruk ditolak; konfigurasi belum lengkap tidak menerima presensi. |

## D. Enrollment wajah

**Hasil tahap:** siswa baru dapat mendaftarkan tiga pose, kemudian login ulang; Admin dapat mereset wajah dengan aman.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| DONE · T14 | **Gate dan state enrollment.** Akses khusus siswa belum terdaftar, urutan ganti password → enrollment → dashboard, status tiga pose. | T06, T09 | Dashboard/route normal tidak bisa dilewati lewat URL; tiga pose belum lengkap tetap `face_registered=false`; respons API dan halaman konsisten. AC-01 dan state awal AC-02. |
| TODO · T15 | **Capture enrollment tiga pose.** Integrasikan hasil T04: kamera, satu wajah, blur/brightness, pose depan/kiri/kanan, challenge blink, auto capture, suara dan feedback. | T04, T07, T14 | Tiga pose tersimpan unik; payload buruk, challenge tidak sah/kedaluwarsa, multi-face, dan pose belum lengkap ditolak. Server tidak cukup mempercayai boolean `blink=true` dari client. Ada retry tanpa kehilangan pose valid. |
| TODO · T16 | **Model LBPH, finalisasi, dan reset wajah.** Training/publish model dengan pengendalian akses bersamaan sederhana, threshold teruji, finalisasi enrollment, status/detail wajah dan reset oleh Admin. | T15 | Model siap sebelum enrollment ditandai selesai; session siswa berakhir; reset menghapus/menonaktifkan data lama dan memperbarui model; model corrupt/missing menolak verifikasi; kegagalan training tidak menghasilkan status siap palsu. AC-02. |

## E. Presensi siswa end-to-end

**Hasil tahap:** satu siswa dapat check-in dan check-out dengan seluruh validasi, tanpa duplikasi, lalu melihat riwayatnya.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| TODO · T17 | **State presensi dan CTA.** Schema record harian, unique siswa/tanggal, snapshot kelas, endpoint state; keadaan masuk, menunggu, pulang, selesai, libur, cutoff lewat. | T12, T14; keputusan waktu/status manual | State berasal dari server dan dapat diuji dengan waktu terkontrol; check-out tanpa check-in tidak tersedia; UI tidak menentukan status sendiri. |
| TODO · T18 | **Check-in tervalidasi.** Alur lokasi → kamera/blink → face match akun → evidence privat → commit record dan status Hadir/Terlambat. | T13, T16, T17 | Lokasi/wajah/liveness/waktu tidak sah tidak menyimpan presensi sukses; record beserta evidence konsisten saat gagal; jadwal dan akun diperiksa kembali saat submit. AC-03, AC-04, AC-05. |
| TODO · T19 | **Check-out dan retry aman.** Isi sisi pulang pada record yang sama; cegah submit bersamaan dan retry menggandakan/mengubah aksi. | T18 | Check-out terlalu awal ditolak; check-out sah memperbarui satu record; retry check-in setelah timeout tidak berubah menjadi check-out; duplicate/concurrent submit aman. AC-06, AC-07, AC-11. |
| TODO · T20 | **Finalisasi Alpa.** Command server untuk siswa yang wajib hadir dan melewati cutoff, dengan transaksi/idempotensi. | T12, T19 | Tidak menimpa presensi/status manual; tidak membuat Alpa pada libur atau siswa yang tidak wajib hadir; dijalankan dua kali tetap konsisten; benturan dengan submit/manual aman. AC-10. |
| TODO · T21 | **Dashboard dan riwayat Siswa.** Data nyata, CTA, success/error, kalender bulan berjalan, detail tanggal, profil lengkap. | T10, T19, T20 | Dashboard menampilkan tanggal/kelas/jadwal/jam/status benar; API menolak bulan lama dan siswa lain; detail tidak mengekspos evidence/koordinat teknis; koneksi terputus memberi status belum terkonfirmasi dan cara cek ulang. FR-STU-02–06. |

Ketika respons submit hilang, client belum tahu apakah commit berhasil. UI meminta pengecekan state/retry aman dan tidak langsung mengklaim sukses atau pasti gagal tersimpan.

## F. Guru dan monitoring Admin

**Hasil tahap:** sekolah dapat memonitor data nyata, mengelola status manual, serta mengekspor hasil.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| TODO · T22 | **Dashboard dan daftar siswa Guru.** Ringkasan kelas, presensi kelas, cari/filter, detail siswa dan riwayat lintas bulan, pagination sederhana. | T10, T20, T21 | Angka ringkasan sesuai record; seluruh query dibatasi kelas yang sah; manipulasi URL/filter ke kelas lain ditolak. AC-08; FR-TCH-01–03, FR-TCH-08. |
| TODO · T23 | **Detail evidence yang terlindungi.** Foto masuk/pulang, waktu, dan ringkasan lokasi untuk Guru terkait/Admin. | T07, T19, T22 | URL foto langsung tetap memeriksa session/role/scope; Siswa dan Guru kelas lain ditolak; file hilang ditangani tanpa membocorkan path server. FR-TCH-07. |
| TODO · T24 | **Status manual Guru.** Izin/Sakit/Alpa dan catatan, audit perubahan, perlindungan benturan dengan presensi otomatis. | T20, T22; keputusan status manual | Hadir/Terlambat otomatis tidak dapat diubah; input dan koreksi mengikuti kebijakan; perubahan atomik dan diaudit; diuji race dengan submit/finalisasi Alpa. AC-09; FR-TCH-04–06. |
| TODO · T25 | **Dashboard dan monitoring Admin.** Ringkasan global, filter tanggal/kelas/status/pencarian, detail siswa/presensi, akses fitur pengelolaan yang telah dibuat. | T22, T23, T24 | Semua filter menghasilkan data konsisten dan memiliki pagination; Admin dapat membuka seluruh kelas; state kosong/error jelas. FR-ADM-06. |
| TODO · T26 | **Ekspor Excel dan halaman audit.** Export mengikuti filter monitoring; audit dapat ditelusuri berdasarkan pelaku/waktu/aksi. | T07, T25 | Isi ekspor cocok dengan hasil filter, akses Admin dipaksakan backend, input teks tidak menjadi formula berbahaya; log tidak menampilkan secrets/biometrik mentah. FR-ADM-07, FR-ADM-11. |

## G. Analisis K-Means

**Hasil tahap:** Admin menjalankan analisis yang dapat direproduksi dan membuka histori run tanpa menimpa hasil lama.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| TODO · T27 | **Agregasi tiga fitur.** Hitung attendance percentage, late count, alpha count berdasarkan periode, jadwal historis, dan penempatan siswa. | T20, T24; keputusan metodologi | Dataset kecil yang dihitung manual cocok dengan hasil; libur/Izin/Sakit/perpindahan kelas tertangani; nol hari efektif, periode belum final, dan data tidak lengkap memberi hasil/penolakan eksplisit. |
| TODO · T28 | **K-Means dan penyimpanan run.** Scaling, K=3, random state tetap, centroid skala asli, label yang dapat dijelaskan, simpan run/result/centroid secara konsisten. | T27 | Data tidak memadai ditolak dengan jelas; hasil dapat direproduksi pada input/config yang sama; label bukan nomor cluster tetap; run lama tetap utuh dan run gagal tidak tampak sukses. AC-12. |
| TODO · T29 | **Halaman analisis dan histori.** Form periode/tahun ajaran, aksi run Admin, ringkasan cluster, chart, centroid, daftar siswa dan detail run. | T25, T28 | Admin dapat menjalankan dan membuka kembali hasil; non-Admin ditolak; loading/error/empty tersedia; konfigurasi/metode tercatat agar hasil bisa dijelaskan dalam skripsi. FR-ADM-10. |

## H. PWA, penerimaan, dan deployment

**Hasil tahap:** aplikasi terverifikasi di perangkat target dan siap dijalankan dengan prosedur operasi yang jelas.

| Status / ID | Task dan hasil utama | Dependensi | Selesai apabila |
|---|---|---|---|
| TODO · T30 | **PWA dan kondisi jaringan.** Manifest/icon, installability, Service Worker untuk shell/aset aman, offline notice, update cache/logout yang benar. | T21, T22 | Terpasang di Android; shell offline tidak mengklaim presensi tersedia; tidak menyimpan biometrik/respons privat dalam cache; reconnect/retry tidak menduplikasi presensi. |
| TODO · T31 | **Penyelesaian visual dan aksesibilitas.** Lengkapi 5–7 ilustrasi konsisten, responsivitas, feedback kamera, fokus keyboard, label, kontras, loading/empty/error pada halaman yang sudah ada. | T26, T29, T30 | Review visual mobile/tablet/desktop sesuai target role; navigasi dan aksi jelas; tidak ada tombol tanpa aksi atau state; tidak mengubah kontrak UI yang sudah disepakati. |
| TODO · T32 | **Uji penerimaan perangkat nyata.** Jalankan alur akun baru → password → tiga pose → login → masuk/pulang → monitoring pada Android HTTPS. Kalibrasi dan ulangi kasus GPS/kamera/kualitas/mismatch/blink/jaringan. | T31 | Hasil per perangkat/kasus dicatat; threshold dipilih dari bukti; kegagalan utama diperbaiki dan diuji ulang. Jika akses perangkat belum ada, task tetap belum selesai. |
| TODO · T33 | **Regresi keamanan dan kapasitas.** Jalankan AC-01–12, pemeriksaan akses/CSRF/session/file, konkurensi, ekspor, dan beban mendekati jumlah siswa serta pola jam masuk target. | T32 | Tidak ada temuan kritis terbuka; hasil pengukuran dan batas kapasitas dicatat; optimasi hanya untuk hambatan yang terbukti. Pengujian tiap fitur sebelumnya tetap wajib, task ini integrasi akhir. |
| TODO · T34 | **Deployment VPS dan operasi dasar.** Siapkan konfigurasi Nginx/Gunicorn/service, domain/TLS, MySQL private, secrets, cron Alpa, log rotation, backup dan runbook restore/rollback. Terapkan saat deployment diminta dan akses tersedia. | T33; kebutuhan operasional tersedia | Domain HTTPS berfungsi; service restart dan job teruji; backup database + protected storage berhasil dipulihkan ke lingkungan uji; dokumentasi setup dari kosong terverifikasi. Konfigurasi siap tanpa akses VPS belum berarti deployed. |
| TODO · T35 | **UAT dan serah terima.** Siswa, Guru, Admin menjalankan skenario inti pada deployment; tutup checklist PRD §25 dan dokumentasikan batasan serta panduan pengguna/operator. | T34 | Seluruh Must memiliki bukti penerimaan, isu penghambat selesai, kebijakan penggunaan biometrik tersedia, dan sekolah dapat menjalankan prosedur operasi. Jangan menandai selesai hanya karena demonstrasi UI berhasil. |

## Breakdown pelaksanaan T00–T35

### T00 — Rapikan keputusan awal

**Output:** daftar keputusan di dokumen ini yang membedakan kebutuhan terkunci, usulan, dan pertanyaan terbuka. T00 tidak menghasilkan kode aplikasi.

- [x] **T00.1 — Catat baseline.** Cocokkan stack, tiga role, navigasi, aturan utama, dan out-of-scope dengan PRD; catat rujukan bagiannya. Jangan mengubah kebutuhan yang sudah eksplisit.
- [x] **T00.2 — Daftar pertanyaan produk.** Uraikan waktu/cutoff/check-out, histori kelas/jadwal, konflik exception, status manual, formula analisis, serta kebijakan biometrik menjadi pertanyaan yang dapat dijawab secara spesifik.
- [x] **T00.3 — Siapkan rekomendasi sederhana.** Untuk setiap pertanyaan, tulis satu usulan utama beserta dampaknya pada perilaku aplikasi/data. Tandai sebagai usulan sampai ada keputusan, tanpa membuat banyak alternatif yang tidak diperlukan.
- [x] **T00.4 — Petakan kebutuhan eksternal.** Catat kebutuhan koordinat sekolah, perangkat Android, data uji berizin, jumlah siswa, VPS/domain, dan pihak yang memberikan informasi. Bedakan yang sudah tersedia dan belum diketahui; jangan menyalin secrets ke dokumen.
- [x] **T00.5 — Bahas sesuai prioritas.** Ajukan keputusan yang memengaruhi tahap terdekat kepada pengguna; rekam jawaban dan task yang terpengaruh. Kebutuhan untuk tahap berikutnya tetap boleh terbuka dengan batas penyelesaian yang jelas.
- [x] **T00.6 — Tutup perencanaan awal.** Pastikan setiap isu mempunyai status `disepakati` atau `terbuka`, rujukan/task terdampak, dan pihak yang perlu menjawab. Catat apakah T01 dapat dimulai dan hambatan spesifik jika ada; jangan menyatakan semua aturan telah dikunci bila belum.

### T01 — Aplikasi minimal

- [x] **T01.1 — Siapkan lingkungan minimum.** Periksa runtime yang tersedia, pilih versi dependency awal yang kompatibel melalui dokumentasi terkini, dan buat lingkungan proyek tanpa memasang library fitur yang belum digunakan.
- [x] **T01.2 — Buat bootstrap.** Tambahkan entry point, konfigurasi development/production secukupnya, dan halaman sederhana untuk memastikan aplikasi hidup.
- [x] **T01.3 — Atur konfigurasi aman.** Tambahkan `.gitignore` dan `.env.example`; konfigurasi wajib yang hilang memberi pesan jelas tanpa membocorkan nilainya.
- [x] **T01.4 — Verifikasi setup.** Jalankan dari langkah setup yang bersih dan tulis perintah aktual di README; catat versi runtime yang berhasil digunakan.

### T02 — Database dan Admin awal

- [x] **T02.1 — Buat schema akun.** Tambahkan tabel `users`, role tetap, status aktif, flag ganti password, dan unique username; sediakan perubahan SQL berurutan.
- [x] **T02.2 — Hubungkan database.** Implementasikan pembukaan/penutupan koneksi, parameterized query, dan transaksi yang diperlukan; gunakan database tes terpisah.
- [x] **T02.3 — Buat Admin pertama.** Sediakan prosedur input kredensial aman dan hash password; cegah pembuatan ulang yang menimpa akun tanpa sengaja. Fixture tes harus sintetis.
- [x] **T02.4 — Verifikasi database.** Uji setup dari kosong, unique constraint, rollback saat gagal, dan prosedur pembaruan schema tanpa menghapus data lama.

### T03 — Autentikasi dan role

- [x] **T03.1 — Login dan session.** Implementasikan form login, verifikasi hash, pesan kegagalan generik, redirect sesuai role, dan logout.
- [x] **T03.2 — Pembatasan backend.** Tambahkan guard login/role dan status akun aktif, termasuk pengecekan akun yang dinonaktifkan saat session masih ada.
- [x] **T03.3 — Proteksi autentikasi.** Pasang CSRF pada aksi mutasi, konfigurasi cookie/session, dan pembatasan percobaan login dasar sesuai deployment yang direncanakan.
- [x] **T03.4 — Uji akses.** Periksa login salah/benar, session setelah logout, nonaktif, lintas role melalui URL, dan request tanpa CSRF; jangan hanya memeriksa tombol tersembunyi.

### T04 — Uji awal biometrik

- [ ] **T04.1 — Siapkan percobaan terbatas.** Tentukan perangkat/browser, akses HTTPS untuk uji, dan sampel berizin; pisahkan hasil percobaan dari data presensi.
- [ ] **T04.2 — Uji capture.** Periksa permission kamera, frame depan/kiri/kanan, satu wajah, blur/brightness, dan deteksi eye state/blink dengan library yang kompatibel.
- [ ] **T04.3 — Uji recognition.** Latih LBPH dari tiga pose, bandingkan wajah cocok/tidak cocok serta variasi cahaya; catat score dan calon threshold tanpa mengklaim angka final.
- [ ] **T04.4 — Catat keputusan teknis.** Simpan hasil, keterbatasan, kebutuhan verifikasi server untuk challenge blink, dan pilihan yang akan dipakai T15–T16. Jika gagal, laporkan hambatannya; perubahan metode di luar PRD perlu dibahas.

### T05 — Layout tiga role

- [x] **T05.1 — Siapkan gaya dasar.** Terapkan token warna, font, icon, dan aset/build yang dibutuhkan sesuai PRD.
- [x] **T05.2 — Buat shell per role.** Implementasikan navigasi Siswa, Guru mobile/desktop, dan Admin desktop beserta active state yang benar.
- [x] **T05.3 — Buat komponen yang dipakai.** Sediakan form/button/badge dan feedback dasar, lalu terapkan ke login serta halaman role awal; halaman belum tersedia diberi state jelas.
- [x] **T05.4 — Periksa tampilan.** Tinjau viewport target, label input, fokus keyboard, dan navigasi; simpan bukti visual yang relevan tanpa membuat framework komponen baru.

### T06 — Password dan profil

- [x] **T06.1 — Pasang forced change.** Terapkan `must_change_password` pada halaman dan endpoint agar dashboard tidak dapat dilewati melalui URL.
- [x] **T06.2 — Implementasikan perubahan password.** Validasi password saat ini untuk perubahan mandiri, konfirmasi password baru, update hash/flag, dan perilaku session yang aman.
- [x] **T06.3 — Buat profil dasar.** Tampilkan informasi akun sendiri, ubah password, dan logout; informasi kelas dilengkapi setelah T10.
- [x] **T06.4 — Uji alur.** Periksa akun sementara, salah password, perubahan berhasil, password lama ditolak, dan akses profil pengguna lain.

### T07 — Audit dan storage privat

- [x] **T07.1 — Buat audit minimum.** Tentukan field pelaku, waktu, aksi, target, serta perubahan relevan; sediakan satu fungsi pencatatan yang dipakai fitur berikutnya.
- [x] **T07.2 — Siapkan storage privat.** Pisahkan wajah, evidence, dan model dari static; gunakan nama/path yang dikendalikan server.
- [x] **T07.3 — Validasi berkas.** Batasi ukuran, tipe, dan hasil decode sesuai kebutuhan kamera; tolak path traversal dan jangan log konten mentah.
- [x] **T07.4 — Uji proteksi.** Periksa file tidak tersedia lewat URL publik, payload salah ditolak, dan audit contoh mencatat metadata aman. Endpoint baca foto kelas dibuat di T23.

### T08 — Kelola Guru

- [x] **T08.1 — Tambahkan data Guru.** Buat relasi profil-akun dan validasi field; pembuatan akun/profil harus satu transaksi.
- [x] **T08.2 — Buat halaman kelola.** Daftar/cari, tambah, edit, dan detail sederhana dengan feedback input yang jelas.
- [x] **T08.3 — Tambahkan aksi akun.** Nonaktifkan tanpa menghapus histori dan reset password sementara; catat perubahan penting pada audit.
- [x] **T08.4 — Uji operasi Admin.** Periksa duplikat, rollback, reset/forced change, akun nonaktif, serta penolakan akses non-Admin.

### T09 — Kelola Siswa

- [x] **T09.1 — Tambahkan data Siswa.** Buat relasi profil-akun, unique NISN, username NISN, dan `face_registered=false`; simpan identitas seperti NISN sebagai teks agar nol depan tidak hilang.
- [x] **T09.2 — Buat halaman kelola.** Daftar/cari, tambah, edit, dan detail dasar; validasi perubahan NISN agar akun tetap konsisten.
- [x] **T09.3 — Tambahkan aksi akun.** Nonaktifkan, reset password sementara, audit perubahan, dan seed/fixture sintetis untuk pengembangan.
- [x] **T09.4 — Uji konsistensi.** Periksa unique constraint, transaksi akun/profil, reset, scope Admin, dan histori tetap tersedia setelah nonaktif.

### T10 — Tahun ajaran dan kelas

- [x] **T10.1 — Finalkan aturan histori.** Baseline mengikuti constraint PRD satu penempatan per Siswa per tahun ajaran; perubahan intra-tahun tetap menjadi keputusan sekolah sebelum constraint diubah.
- [x] **T10.2 — Kelola tahun ajaran dan kelas.** Buat form/list, status aktif, serta relasi wali kelas; tolak penghapusan yang merusak referensi.
- [x] **T10.3 — Tempatkan siswa.** Implementasikan penempatan dengan validasi tahun ajaran, status aktif, dan benturan penempatan.
- [x] **T10.4 — Uji scope dan histori.** Verifikasi Siswa tidak mempunyai penempatan ganda, Guru hanya memperoleh kelas tanggung jawabnya, dan penempatan tetap tersedia setelah kelas dinonaktifkan.

### T11 — Jadwal reguler

- [x] **T11.1 — Kunci aturan waktu.** Baseline dicatat: `Asia/Jakarta`, mulai/cutoff inklusif, check-in awal ditolak, `late_after` mulai terlambat, dan belum ada batas akhir check-out.
- [x] **T11.2 — Simpan jadwal per hari.** Migration 006, query, form Admin, aktif/nonaktif, unique hari/tahun ajaran, dan validasi urutan waktu tersedia.
- [x] **T11.3 — Buat resolver dasar.** `resolve_schedule` memakai tanggal/tahun ajaran dan jadwal aktif; `application_now` memakai timezone server; perubahan penting diaudit.
- [x] **T11.4 — Uji batas waktu.** Sebelum/tepat/sesudah batas, duplikasi, rollback audit, toggle aktif, Jumat, dan konfigurasi kosong diuji melalui unit/smoke test.

### T12 — Exception jadwal

- [x] **T12.1 — Definisikan exception.** Migration 007 menambahkan tanggal, scope, kelas sesuai scope, jenis PRD, empat field override nullable, status, constraint unik tanggal/scope, dan validasi urutan waktu.
- [x] **T12.2 — Terapkan prioritas.** `resolve_schedule` memakai exception kelas → sekolah → reguler; tiap field yang kosong diwarisi dari prioritas berikutnya. Hari libur menghasilkan `is_holiday` dan tidak membawa jadwal presensi.
- [x] **T12.3 — Buat pengelolaan dan preview.** Admin dapat membuat, mengedit, mengaktif/nonaktifkan exception di `/admin/schedule-exceptions`; preview dan resolver presensi memakai aturan efektif yang sama; mutasi dicatat di audit log.
- [x] **T12.4 — Uji skenario.** 7 unit test T12 lulus, termasuk render layar/preview Admin, resolver yang sama, role guard, validasi, prioritas kelas/sekolah/reguler, dan hari libur. Smoke MySQL `scripts.smoke_t12` lulus untuk scope/pewarisan, konflik duplikat, update, toggle, audit atomik/rollback, dan cleanup. Seluruh 79 unit test lulus; smoke T11 lulus setelah entry point resolver berubah.

### T13 — Geofence

- [x] **T13.1 — Sediakan pengaturan geofence.** Migration 008 dan layar `/admin/geofence` mengelola nama, titik, status, radius default 75 m, dan max accuracy nullable. Data sekolah belum diisi; geofence tetap nonaktif sampai koordinat terverifikasi dan kebijakan accuracy tersedia.
- [x] **T13.2 — Sediakan validasi lokasi di server.** Service memvalidasi rentang koordinat, accuracy, menghitung Haversine, dan menolak lokasi di luar radius atau konfigurasi yang belum aktif. Max accuracy wajib diisi saat aktivasi; nilainya tidak ditebak.
- [x] **T13.3 — Buat feedback lokasi.** Pemeriksa lokasi pada halaman Admin meminta izin hanya setelah tombol ditekan, memberi umpan balik untuk permission ditolak, timeout, layanan lokasi tidak tersedia, accuracy buruk, lokasi di luar area, konfigurasi belum aktif, dan kegagalan jaringan; tersedia retry.
- [x] **T13.4 — Verifikasi perhitungan.** 6 unit test T13 dan smoke MySQL `scripts.smoke_t13` lulus untuk Haversine, dalam/tepat/luar radius, input invalid, accuracy, aktivasi, audit dan rollback atomik; smoke membersihkan data. Uji GPS Android/HTTPS dan titik sekolah sebenarnya tetap di T32 setelah nilai resmi tersedia.

### T14 — Gate enrollment

- [x] **T14.1 — Buat state enrollment.** Migration 009 membuat penyimpanan pose unik per siswa (`front`, `left`, `right`); service hanya membaca status serta nama pose milik akun aktif dan tidak mengekspos storage key. Penulisan pose valid terjadi di T15 setelah capture.
- [x] **T14.2 — Terapkan urutan gate.** Gate request berjalan setelah gate password; akun password sementara tetap di `/change-password`, lalu siswa belum enrollment dialihkan ke `/student/enrollment`. Dashboard, profil, serta endpoint blueprint siswa/presensi/wajah tidak dapat dibuka langsung.
- [x] **T14.3 — Buat halaman awal/progres.** `/student/enrollment` menampilkan urutan tiga pose, progres yang tersimpan, dan arahan persiapan; UI menyatakan enrollment belum selesai sampai model berhasil diproses dan tidak menawarkan tombol sukses.
- [x] **T14.4 — Uji bypass.** 6 unit test T14 dan smoke MySQL `scripts.smoke_t14` lulus untuk dashboard/API langsung, akses lintas siswa, role guard, tiga pose tanpa status selesai, kondisi database tidak tersedia, serta urutan password → enrollment tanpa loop. Smoke memakai data sintetis dan cleanup.

### T15 — Capture enrollment

- [ ] **T15.1 — Integrasikan kamera dan quality check.** Gunakan hasil T04 untuk satu wajah, ukuran/posisi, blur/brightness, serta panduan pose.
- [ ] **T15.2 — Integrasikan challenge blink.** Kaitkan challenge dengan session/siswa dan masa berlaku; validasi bukti sesuai hasil T04, tolak reuse, dan jangan percaya flag client saja.
- [ ] **T15.3 — Simpan tiga pose.** Auto capture setelah valid, suara/feedback, penyimpanan privat, unique pose, serta retry pose gagal tanpa menghapus pose sah lain.
- [ ] **T15.4 — Uji capture menyeluruh.** Periksa permission, multi-face, frame buruk, challenge salah/kedaluwarsa, pengulangan submit, dan akses siswa lain; belum boleh menandai enrollment selesai sebelum T16.

### T16 — Model dan reset wajah

- [ ] **T16.1 — Siapkan training konsisten.** Gunakan crop/grayscale/resize yang sama untuk enrollment dan prediksi; pilih threshold berdasarkan hasil uji yang dicatat.
- [ ] **T16.2 — Publikasikan model dengan aman.** Cegah training bersamaan merusak file dan pastikan request membaca model utuh; tangani kegagalan tanpa status siap palsu.
- [ ] **T16.3 — Finalisasi enrollment.** Tandai terdaftar hanya setelah tiga pose dan model siap, kemudian akhiri session untuk login ulang.
- [ ] **T16.4 — Tambahkan reset Admin.** Tampilkan status/data wajah secara terlindungi, reset enrollment, perbarui model, kembalikan gate siswa, dan tulis audit.
- [ ] **T16.5 — Uji kegagalan.** Periksa model hilang/rusak, training gagal, enrollment bersamaan, dan reset saat ada verifikasi; wajah yang telah direset tidak boleh tetap diterima.

### T17 — State dan CTA presensi

- [ ] **T17.1 — Buat record harian.** Tambahkan sisi masuk/pulang, status/sumber, snapshot kelas, unique siswa/tanggal, serta indeks yang dipakai query.
- [ ] **T17.2 — Buat fungsi penentu aksi.** Petakan jadwal/record menjadi masuk, menunggu, pulang, selesai, libur, atau tertutup sesuai kebijakan.
- [ ] **T17.3 — Hubungkan endpoint dan CTA.** Server mengirim state dan alasan aksi belum tersedia; browser menampilkan hasilnya tanpa menentukan kelayakan sendiri.
- [ ] **T17.4 — Uji transisi.** Gunakan waktu terkontrol untuk semua batas, belum check-in, sudah checkout, manual status, dan pergantian tanggal.

### T18 — Check-in

- [ ] **T18.1 — Rangkai verifikasi.** Periksa session/role/enrollment, jadwal, lokasi, kualitas/blink, lalu identitas LBPH harus sama dengan akun.
- [ ] **T18.2 — Simpan hasil konsisten.** Validasi ulang keadaan saat submit, tentukan Hadir/Terlambat, simpan evidence terkompresi dan record dalam alur yang menangani rollback/pembersihan file gagal.
- [ ] **T18.3 — Hubungkan UI submit.** Tampilkan proses, kegagalan spesifik yang aman, dan sukses hanya setelah konfirmasi server; cegah klik ulang sebagai bantuan UX, bukan pengganti constraint backend.
- [ ] **T18.4 — Uji penerimaan/penolakan.** Jalankan AC-03–05 dan kegagalan penyimpanan; tidak boleh ada successful attendance ketika satu validasi wajib gagal.

### T19 — Check-out dan retry

- [ ] **T19.1 — Tambahkan check-out.** Ulangi validasi wajib, periksa jam pulang, dan isi sisi pulang record check-in yang sama.
- [ ] **T19.2 — Tetapkan retry per aksi.** Ikat request/retry pada aksi dan tanggal yang dimaksud; pengiriman ulang check-in tidak boleh diterjemahkan menjadi check-out.
- [ ] **T19.3 — Tangani respons hilang.** UI mengecek state server atau mengulang request secara aman sebelum menyimpulkan hasil; bedakan belum terkonfirmasi dari gagal pasti.
- [ ] **T19.4 — Uji konkurensi.** Periksa dua submit bersamaan, duplicate check-out, retry melewati jam pulang/pergantian tanggal, exception pulang awal, dan check-out tanpa check-in.

### T20 — Finalisasi Alpa

- [ ] **T20.1 — Tentukan siswa yang wajib hadir.** Gunakan tanggal, penempatan, status akun/kewajiban menurut kebijakan, dan jadwal efektif termasuk exception.
- [ ] **T20.2 — Buat command finalisasi.** Setelah cutoff, isi Alpa hanya jika belum ada auto-presence atau status manual sah; gunakan transaksi dan constraint yang sama.
- [ ] **T20.3 — Buat hasil eksekusi ringkas.** Laporkan jumlah diproses/dilewati/gagal tanpa data sensitif; dokumentasikan pemanggilan untuk scheduler nanti.
- [ ] **T20.4 — Uji pengulangan dan benturan.** Periksa hari libur, cutoff kelas berbeda, command dua kali, benturan dengan submit, dan record manual yang sudah ada. Uji benturan endpoint manual diulang pada T24.

### T21 — Dashboard dan riwayat Siswa

- [ ] **T21.1 — Isi dashboard nyata.** Tampilkan identitas/kelas, tanggal, jadwal efektif, status, jam masuk/pulang, dan CTA hasil T17–T19.
- [ ] **T21.2 — Buat kalender/detail.** Ambil bulan berjalan dan status per tanggal dengan pembedaan libur/belum absen; detail tidak menyertakan foto atau koordinat teknis.
- [ ] **T21.3 — Lengkapi alur mobile.** Hubungkan kamera, success/error/retry, profil dengan kelas, dan navigasi kembali; tampilkan status jaringan secara jujur.
- [ ] **T21.4 — Uji batas akses.** Manipulasi bulan dan student ID harus ditolak backend; periksa ringkasan/kalender terhadap data uji serta pergantian bulan.

### T22 — Monitoring Guru

- [ ] **T22.1 — Buat query berscope.** Semua ringkasan, daftar siswa, dan histori dibatasi kelas tanggung jawab Guru, termasuk aturan akses histori yang disepakati.
- [ ] **T22.2 — Buat dashboard/daftar.** Tampilkan total dan status kelas, siswa perlu ditinjau, pencarian/filter, serta pagination.
- [ ] **T22.3 — Buat detail dan histori.** Hubungkan detail siswa, kalender lintas bulan, dan detail waktu presensi; siapkan tautan evidence hanya bagi scope sah.
- [ ] **T22.4 — Uji cross-class.** Ubah ID/filter/parameter halaman untuk mencoba kelas lain; periksa hasil kosong dan angka ringkasan tidak menghitung ganda.

### T23 — Evidence terlindungi

- [ ] **T23.1 — Buat endpoint file privat.** Cari file dari record yang sah, bukan path dari pengguna; periksa session, role, dan scope pada setiap permintaan.
- [ ] **T23.2 — Buat detail evidence.** Guru terkait/Admin dapat melihat foto masuk/pulang, waktu, dan ringkasan validasi lokasi.
- [ ] **T23.3 — Tangani file dan cache.** Beri respons aman untuk file hilang/tidak berizin dan cegah cache publik untuk konten privat.
- [ ] **T23.4 — Uji akses langsung.** URL foto harus ditolak bagi pengguna belum login, Siswa, dan Guru kelas lain, termasuk setelah logout atau perubahan hak akses.

### T24 — Status manual Guru

- [ ] **T24.1 — Rekam kebijakan perubahan.** Pastikan keterangan, batas waktu/koreksi, serta interaksi manual dengan presensi otomatis sudah diputuskan.
- [ ] **T24.2 — Buat input status.** Form Izin/Sakit/Alpa untuk siswa yang memenuhi syarat; validasi catatan dan scope di backend.
- [ ] **T24.3 — Simpan secara atomik.** Periksa ulang record sebelum update, tolak perubahan Hadir/Terlambat otomatis, dan simpan audit perubahan yang dapat ditelusuri.
- [ ] **T24.4 — Uji race/koreksi.** Jalankan AC-09, perubahan lintas kelas, serta submit bersamaan dengan check-in/job Alpa; pastikan hasil mengikuti kebijakan dan tidak saling menimpa diam-diam.

### T25 — Monitoring Admin

- [ ] **T25.1 — Buat ringkasan global.** Hitung status seluruh kelas sesuai tanggal dan jadwal, tanpa memasukkan hari libur sebagai Alpa.
- [ ] **T25.2 — Buat daftar/filter.** Tanggal, kelas, status, pencarian, pagination, serta state kosong/loading/error yang konsisten.
- [ ] **T25.3 — Hubungkan detail.** Gunakan detail siswa/presensi/evidence yang sudah tersedia dan tautkan konfigurasi/master data terkait.
- [ ] **T25.4 — Verifikasi data.** Bandingkan ringkasan dengan daftar terfilter pada fixture; pastikan hanya Admin mendapatkan scope global.

### T26 — Ekspor dan audit

- [ ] **T26.1 — Samakan dataset ekspor.** Gunakan aturan filter monitoring yang sama, tetapi ekspor seluruh hasil yang sesuai, bukan hanya halaman pagination aktif.
- [ ] **T26.2 — Buat berkas Excel.** Tulis kolom, tipe data, tanggal, dan status yang jelas; lindungi teks input agar tidak dieksekusi sebagai formula.
- [ ] **T26.3 — Buat halaman audit.** Tampilkan pelaku/waktu/aksi/target dengan filter sederhana dan pagination, tanpa konten sensitif.
- [ ] **T26.4 — Uji hasil dan akses.** Cocokkan jumlah/baris ekspor dengan dataset acuan, buka hasilnya, periksa data kosong dan input formula, serta tolak non-Admin.

### T27 — Agregasi fitur K-Means

- [ ] **T27.1 — Tetapkan definisi analisis.** Catat formula, periode yang valid, populasi siswa, histori kelas/jadwal, dan perlakuan data belum final/denominator nol.
- [ ] **T27.2 — Siapkan contoh hitung manual.** Susun dataset kecil mencakup Hadir, Terlambat, Izin, Sakit, Alpa, Libur, dan perpindahan kelas bila berlaku.
- [ ] **T27.3 — Implementasikan agregasi.** Hitung tiga fitur per siswa dengan query/proses sederhana dan validasi nilai tidak lengkap/tidak valid.
- [ ] **T27.4 — Bandingkan hasil.** Cocokkan dengan hitungan manual; pastikan hari tidak wajib hadir tidak masuk denominator dan kasus nol tidak menghasilkan pembagian tak valid.

### T28 — Mesin K-Means

- [ ] **T28.1 — Validasi dataset.** Periksa jumlah siswa, variasi fitur, nilai kosong/tidak valid, dan kelayakan membentuk tiga cluster.
- [ ] **T28.2 — Jalankan pipeline.** Standardisasi, K=3, random state tetap, inverse transform centroid, dan label berdasarkan aturan yang sudah disepakati termasuk hasil seri/tie.
- [ ] **T28.3 — Simpan histori run.** Tambahkan schema dan transaksi untuk metadata/config, fitur, hasil siswa, serta centroid; kegagalan tidak boleh meninggalkan run sukses parsial.
- [ ] **T28.4 — Uji reproduksibilitas.** Dataset/config sama menghasilkan keluaran yang konsisten; run baru tidak menimpa lama dan dataset tidak memadai menghasilkan pesan yang jelas.

### T29 — UI analisis

- [ ] **T29.1 — Buat form run.** Pilih tahun ajaran/periode, jelaskan prasyarat data, validasi backend, dan tampilkan proses/hasil/kegagalan.
- [ ] **T29.2 — Buat detail hasil.** Tampilkan jumlah siswa per cluster, centroid skala asli, chart, daftar siswa, serta penjelasan label.
- [ ] **T29.3 — Buat histori.** Daftar run dan pembukaan kembali detail menggunakan data tersimpan, bukan menghitung ulang hasil lama secara diam-diam.
- [ ] **T29.4 — Uji alur Admin.** Periksa hak akses, double submit, data kosong/tidak layak, serta konsistensi chart/tabel dengan hasil T28.

### T30 — PWA dan jaringan

- [ ] **T30.1 — Siapkan installability.** Tambahkan manifest, icon, nama aplikasi, dan start URL yang bekerja dengan autentikasi.
- [ ] **T30.2 — Batasi cache.** Cache shell/aset yang aman saja; kecualikan API privat, halaman personal, foto, dan request presensi; tentukan pembaruan versi cache sederhana.
- [ ] **T30.3 — Buat pengalaman offline.** Tampilkan pesan kebutuhan koneksi dan akses pemulihan saat online kembali; jangan membuat antrean presensi offline.
- [ ] **T30.4 — Uji di Android.** Install/buka/update/logout, offline/reconnect, dan retry setelah respons hilang; periksa cache tidak menyimpan data privat.

### T31 — Visual dan aksesibilitas

- [ ] **T31.1 — Inventarisasi kekurangan UI.** Periksa seluruh halaman yang telah tersedia terhadap token, navigasi, komponen, dan state PRD.
- [ ] **T31.2 — Lengkapi aset.** Buat/pasang ilustrasi yang diperlukan dengan satu arah visual dan ukuran yang wajar; jangan menambah ilustrasi ke setiap tabel/form.
- [ ] **T31.3 — Perbaiki interaksi.** Tinjau label, fokus, keyboard, kontras, tap target, modal/bottom sheet, serta pesan kamera dan validasi.
- [ ] **T31.4 — Review viewport.** Periksa mobile/tablet/desktop sesuai role; catat dan perbaiki overflow, teks terpotong, state kosong, serta aksi yang tidak memberi feedback.

### T32 — Uji perangkat nyata

- [ ] **T32.1 — Siapkan matriks uji.** Catat perangkat/browser, versi aplikasi, kondisi jaringan/cahaya/lokasi, akun uji berizin, dan hasil yang diharapkan.
- [ ] **T32.2 — Jalankan alur utama.** Akun baru, forced password, tiga pose, login ulang, check-in, check-out, dan pembacaan hasil oleh Guru/Admin.
- [ ] **T32.3 — Jalankan kondisi gagal.** Kamera/GPS ditolak, accuracy buruk, gelap/blur, banyak wajah, mismatch, blink gagal, jaringan lambat/putus, dan retry.
- [ ] **T32.4 — Kalibrasi dan ulangi.** Perbaiki penyebab yang terbukti, dokumentasikan threshold beserta bukti, dan ulangi kasus terdampak; pisahkan temuan belum selesai dari kelulusan uji.

### T33 — Regresi keamanan dan kapasitas

- [ ] **T33.1 — Jalankan acceptance lengkap.** Rekam hasil AC-01–12 dan tes integrasi penting pada versi yang akan dideploy.
- [ ] **T33.2 — Periksa jalur keamanan.** Uji lintas role/kelas, session/logout/nonaktif, CSRF, input SQL, protected file, secrets/log, dan akses setelah reset.
- [ ] **T33.3 — Ukur beban yang relevan.** Gunakan jumlah/pola akses target dan dataset sintetis; ukur waktu respons, kegagalan, resource, query, serta konkurensi pada presensi/training/analisis.
- [ ] **T33.4 — Tutup temuan.** Perbaiki masalah prioritas, jalankan ulang pemeriksaan terdampak, dan catat batas kapasitas; penambahan infrastruktur harus didukung hasil ukur.

### T34 — Deployment dan operasi

- [ ] **T34.1 — Periksa kesiapan.** Pastikan akses VPS/domain, konfigurasi production, kebijakan data, dan permintaan deployment tersedia; simpan secrets di tempat yang sesuai, bukan dokumentasi/repository.
- [ ] **T34.2 — Siapkan service.** Konfigurasikan aplikasi, database private, protected storage, Gunicorn/systemd, Nginx, DNS/TLS, dan permission minimum.
- [ ] **T34.3 — Pasang pekerjaan operasional.** Aktifkan job Alpa, log rotation, pemantauan storage dasar, dan backup database/berkas sesuai jadwal.
- [ ] **T34.4 — Verifikasi deployment.** Periksa HTTPS, restart service, akses tiga role, request kamera/lokasi pada perangkat, dan eksekusi job di timezone yang benar.
- [ ] **T34.5 — Uji pemulihan.** Restore database beserta protected storage ke lingkungan uji dan buktikan aplikasi dapat membaca hasilnya; dokumentasikan rollback versi aplikasi/schema yang relevan tanpa menghapus data produksi.
- [ ] **T34.6 — Lengkapi runbook.** Tulis setup dari kosong, update, backup, restore, dan penanganan kegagalan umum memakai perintah yang sudah diverifikasi; tandai langkah yang belum bisa dijalankan.

### T35 — UAT dan serah terima

- [ ] **T35.1 — Siapkan skenario per role.** Pilih tugas harian nyata untuk Siswa, Guru, dan Admin; tentukan peserta serta bukti penerimaan tanpa menyalin data sensitif ke repository.
- [ ] **T35.2 — Laksanakan UAT.** Jalankan skenario pada deployment, catat hasil/masalah dari pengguna, dan pisahkan bug dari permintaan fitur baru di luar scope.
- [ ] **T35.3 — Tutup penghambat.** Perbaiki bug yang menghalangi penggunaan, uji ulang bersama pihak terkait, dan dokumentasikan keterbatasan GPS/blink/LBPH yang masih berlaku.
- [ ] **T35.4 — Serahkan panduan dan bukti.** Lengkapi panduan singkat per role/operator, status kebijakan biometrik, dan checklist PRD §25; tandai produk selesai hanya bila seluruh Must mempunyai bukti yang memadai.

## Pemeriksaan cakupan

| Cakupan PRD | Task utama |
|---|---|
| FR-AUTH-01–07 | T02, T03, T06, T08, T09 |
| FR-STU-01–06 | T14–T16, T17–T21 |
| FR-TCH-01–08 | T22–T24 |
| FR-ADM-01–02 | T08–T10 |
| FR-ADM-03–05 | T11–T13 |
| FR-ADM-06–07 | T25–T26 |
| FR-ADM-08–09 | T08, T09, T16 |
| FR-ADM-10–11 | T26–T29 |
| AC-01–02 | T14–T16 |
| AC-03–05 | T18 |
| AC-06–07, AC-11 | T12, T19 |
| AC-08–09 | T22, T24 |
| AC-10 | T20 |
| AC-12 | T28 |
| Security, privasi, NFR, deployment, Definition of Done | Diterapkan pada task terkait; verifikasi akhir T30–T35 |

Evaluasi cluster tambahan seperti Silhouette Score atau Davies-Bouldin Index mengikuti kebutuhan penelitian, bukan prasyarat tersembunyi untuk menyelesaikan T28. Fitur Should/rekomendasi tetap dicatat sesuai prioritasnya.

## Catatan progres

Isi hanya ketika pelaksanaan dimulai; tidak perlu membuat dokumen status tambahan untuk setiap task.

| Task | Status | Bukti singkat / pemeriksaan | Sisa pekerjaan atau hambatan |
|---|---|---|---|
| T00 | DONE | Baseline PRD, keputusan terbuka, rekomendasi, kebutuhan eksternal, prioritas, dan gate T01–T35 tercatat di bagian Hasil T00. | Menunggu jawaban pengguna/pihak sekolah pada keputusan yang diberi status terbuka; T01 dapat dimulai. |
| T01 | DONE | Flask 3.1.1, `tzdata` 2026.3, factory, halaman awal, `/healthz`, `.env.example`, `.gitignore`, dan `.venv` dibuat. Factory test, HTTP 200, `pip check`, compile check, dan server smoke test lulus. | `.env` belum diload otomatis; database, autentikasi, dan fitur produk dikerjakan pada T02–T03. |
| T02 | DONE | Schema bootstrap + migration `001_create_users.sql`, PyMySQL helper, transaction commit/rollback, CLI Admin, fixture sintetis, 7 unit test, `pip check`, dan compile check lulus. Koneksi lokal membaca `sistem_absensi`; insert Admin rollback, unique constraint, dan cleanup row uji lulus. Akun Admin lokal `admin` berhasil dibuat melalui CLI. | Untuk production, gunakan kredensial sekolah yang dikelola operator dan jangan memakai password development kembali. |
| T03 | DONE | Login/logout, endpoint ganti password, session cookie, CSRF, role guard, akun nonaktif, dan throttle dasar tersedia. 15 unit test, compile check, `pip check`, serta smoke integration MySQL untuk Admin/Guru dan lintas-role lulus. Hash akun Admin lokal diverifikasi tanpa plaintext. | Throttle masih per-process; ganti dengan limiter terpusat sebelum deployment multi-worker. |
| T04 | BLOCKED · setup siap | `opencv-contrib-python==4.12.0.88` dan `numpy==2.2.6` terpasang; helper preprocessing, quality signal provisional, Haar face/eye seam, blink state machine provisional, dan LBPH synthetic POC tersedia. POC browser HTTPS terisolasi tersedia melalui `scripts.setup_t04_android.py` + `scripts.run_t04_android.py`, dengan sesi in-memory, consent, frame quality, tiga pose berlabel, blink signal, mismatch capture, LBPH distance, dan laporan JSON tanpa foto. 6 test T04, smoke unlock, compile check, CSS build, dan strict UI audit lulus. | Operator masih perlu memasang CA pada Android dan menjalankan skenario perangkat dengan sampel berizin. Threshold quality/LBPH serta kelayakan blink tidak boleh dianggap final sebelum uji lapangan. |
| T05 | DONE | Tailwind CSS v4 lokal, token PRD, `DESIGN.md`, `UX-CONTRACT.md`, base template, login/password form, Admin desktop sidebar delapan tujuan, Guru responsive shell, Siswa mobile frame/bottom nav, disabled states, dan inline icons tersedia. Browser preview landing/login diverifikasi; strict premium audit 0 error; 24 unit test, CSS build, compile check, `pip check`, `npm audit`, dan `git diff --check` lulus. | Uji visual perangkat nyata dan browser matrix lengkap masih perlu diulang saat modul berikutnya mengubah shell. |
| T06 | DONE | Gate `must_change_password` terpasang pada setiap request; form perubahan memvalidasi password lama, panjang minimum, dan konfirmasi sebelum update hash atomik. Profil role-specific Admin/Guru/Siswa, shortcut `/profile`, navigasi Profil, dan logout tersedia. 4 test T06 dan seluruh 28 unit test lulus; compile check, `pip check`, CSS build, audit dependency, dan `git diff --check` diverifikasi. | Data kelas/profil akademik menunggu master data T10; uji perangkat nyata tetap mengikuti T32. |
| T07 | DONE | `audit_logs` dan migration 002 tersedia; perubahan password memakai optimistic hash check, credential stamp session, dan audit atomik tanpa menyimpan password. Storage privat `faces/`, `attendance/`, `models/` memakai nama acak, mode file terbatas, validasi MIME/decode/dimensi/pixel, metadata dibersihkan, serta tidak memiliki route publik. 50 unit test dan smoke MySQL `scripts/smoke_t07.py` lulus; rollback audit, CSRF, batas request, throttling, dan regresi koordinat wajah ikut diuji. | Otorisasi per kelas dan endpoint baca evidence dikerjakan saat T23; storage production masih memerlukan permission OS dan backup operasional T34. |
| T08 | DONE | Tabel `teachers`, service transaksi CRUD, pencarian, edit profil, nonaktifkan, reset password sementara, Admin-only routes, halaman daftar/detail/form, dan audit action tersedia. Password sementara hanya tampil pada respons sukses dan tidak masuk metadata. 5 unit test T08 dan smoke MySQL `scripts/smoke_t08.py` lulus untuk atomic CRUD, duplicate, rollback, reset, forced-change flag, nonaktif, histori, dan cross-role access. | Relasi wali kelas/kelas dan scope Guru dilanjutkan di T10; halaman monitoring kelas dikerjakan T22. |
| T09 | DONE | Tabel `students` dan migration 004 menyimpan NISN sebagai teks, profil wajah awal false, serta relasi unik ke `users`. Admin-only list/search/create/edit/detail, sinkronisasi atomik NISN↔username, nonaktifkan, reset password sementara, dan audit action tersedia. 5 unit test T09 dan smoke MySQL `scripts/smoke_t09.py` lulus untuk leading zero, atomic CRUD, duplicate, rollback, reset, forced-change flag, nonaktif, histori, dan cross-role access. | Penempatan siswa ke kelas dan histori perpindahan dikerjakan di T10; enrollment wajah menunggu T14–T16. |
| T10 | DONE | Migration 005 membuat `academic_years`, `classes`, dan `student_class_enrollments`; Admin dapat membuat/mengaktifkan periode, mengelola kelas dan wali kelas, serta menempatkan Siswa. Constraint `(student_id, academic_year_id)` menolak penempatan ganda; kelas nonaktif tetap mempertahankan relasi; query scope Guru hanya mengembalikan kelas milik `teacher_user_id`. 6 unit test T10 dan smoke MySQL `scripts/smoke_t10.py` lulus untuk master CRUD, audit rollback, scope Guru, duplicate placement, dan histori. | Perpindahan intra-tahun belum diaktifkan; perlu keputusan sekolah dan migrasi histori bila dibutuhkan. |
| T11 | DONE | Migration 006 membuat `attendance_schedules` dengan unique `(academic_year_id, day_of_week)` dan constraint urutan waktu. Admin dapat mengelola jadwal harian; resolver server memakai `Asia/Jakarta`; batas check-in diuji sebelum/tepat/sesudah, status hadir/terlambat, cutoff, toggle aktif, duplikasi, rollback audit, dan audit perubahan. 6 unit test T11 dan smoke MySQL `scripts.smoke_t11.py` lulus. | Baseline timezone/batas waktu perlu dikonfirmasi sebelum presensi produksi; batas akhir check-out belum diterapkan. |
| T12 | DONE | Migration 007 telah diterapkan ke database lokal; service resolver efektif, CRUD/status Admin, preview tanggal/kelas, dan audit atomik tersedia. 7 unit test T12, 79 unit test keseluruhan, smoke MySQL T12, dan smoke regresi T11 lulus. Data sintetis dibersihkan oleh smoke test. | Aturan konflik mengikuti rekomendasi terdahulu dan perlu dikonfirmasi sekolah sebelum produksi. |
| T13 | DONE | Migration 008, layar Admin, diagnostic lokasi browser, validasi Haversine, 6 unit test, smoke MySQL dan rollback audit lulus. Geofence belum diaktifkan; koordinat dan batas accuracy tetap kosong sampai sekolah mengesahkan nilainya. | Uji perangkat/lokasi nyata menunggu koordinat dan kebijakan accuracy; uji Android/HTTPS akhir di T32. |
| T14 | DONE | Migration 009, progres enrollment khusus akun sendiri, urutan gate password → enrollment → dashboard, halaman 3 pose dan 6 unit test serta smoke MySQL lulus. | Capture kamera, blink, penyimpanan foto nyata, dan update model mengikuti T15–T16. |

**Langkah berikutnya:** jalankan uji lapangan T04 melalui setup Android/HTTPS yang sudah tersedia, simpan hasil JSON dan catatan perangkat, lalu tetapkan keputusan kelayakan serta kandidat threshold sebelum lanjut T15. Validasi GPS nyata di T32 tetap menunggu koordinat dan kebijakan accuracy.
