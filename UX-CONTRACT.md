# UX Contract — Shell, Password, Profil, dan Enrollment

Dokumen ini mencatat perilaku UI yang dapat dilihat pengguna. Aturan domain presensi tetap berasal dari PRD dan service backend.

## Navigasi

| Role | Mobile | Desktop | Aturan |
|---|---|---|---|
| Siswa | Beranda, Riwayat, Profil | Frame mobile maksimal 480px | Riwayat aktif untuk kalender bulan berjalan; profil dan state dashboard hanya membaca akun sesi. |
| Guru/Wali Kelas | Dashboard, Presensi, Siswa | Dashboard, Presensi Kelas, Data Siswa, Profil | Dashboard, Presensi, dan Siswa aktif serta memakai kelas yang ditugaskan saat request; profil melalui avatar. |
| Admin | Pesan perangkat tidak didukung pada viewport kecil | Dashboard, Data Siswa, Data Guru, Kelas, Jadwal, Monitoring Presensi, Analitik, Pengaturan | Data Guru tersedia pada T08, Data Siswa pada T09, Kelas pada T10, Jadwal reguler serta exception pada T11–T12, Monitoring Presensi pada T25, dan ekspor/audit pada T26; tujuan lain aktif setelah route terkait tersedia. |

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native browser select | `premium-ui.json` and PRD admin forms | Native platform popup | Keyboard and server-validation tests |
| Date | Native browser date input | `premium-ui.json` and `academic_years` contract | Native platform picker | Server date parsing and form tests |
| Form | Server-owned validation with `novalidate` | Flask routes and service validators | Flash error/success state | Unit and smoke tests |

## Exception jadwal

- Admin mengelola exception dari tujuan turunan **Exception jadwal** di bawah Jadwal.
- Preview meminta tanggal, tahun ajaran aktif atau pilihan eksplisit, dan kelas opsional; hasil berasal dari `resolve_schedule` yang juga menjadi entry point resolver presensi.
- Prioritas adalah kelas → sekolah → reguler. Field waktu kosong diwarisi dari sumber prioritas berikutnya. Benturan pada scope/tanggal/kelas yang sama ditolak oleh constraint database.

## Check-in tervalidasi T18

- Tekan CTA `Presensi Masuk` meminta lokasi perangkat terlebih dahulu; kamera hanya dibuka setelah `POST /attendance/checkin/start` mengembalikan challenge (lokasi di dalam radius dengan accuracy andal).
- Panel kamera (`#attendance-camera-panel`) muncul di bawah CTA dengan pratinjau, status live region (`#attendance-status`), dan tombol `Batalkan presensi`. Instruksi izin lokasi/kamera mengikuti tabel skenario PRD §20: izin ditolak → tampilkan cara mengaktifkan, kamera tidak dibuka.
- Frame dikirim tiap ±500 ms ke `POST /attendance/checkin/frame`; server memandu blink (buka → kedip → buka) dan mengumumkan progres. Klik ganda dicegah di UI; backend tetap otoritas penuh (validasi ulang dijadwalkan pada setiap submit).
- Sukses hanya dinyatakan setelah konfirmasi commit server; halaman dimuat ulang untuk menampilkan status baru dari server, bukan dari klaim client. Koneksi putus → halaman dimuat ulang agar status tidak salah diklaim; halaman tidak pernah menyatakan sukses sebelum server commit.
- Pesan kegagalan aman dan spesifik per sebab (di luar area, accuracy buruk, jendela tertutup, wajah tidak cocok, tantangan kedaluwarsa) dengan arahan coba ulang; tanpa detail teknis (tanpa koordinat, distance mentah, atau score).
- Sumber: PRD §8.2, §10.2, §20; API `app/attendance/routes.py`; state dari `attendance_state_service.py` (T17).

## Check-out T19

- CTA `Presensi Pulang` hanya muncul setelah state server `checkout` (sudah check-in dan waktu ≥ `checkout_start`); sebelum itu tombol disabled dengan label `Pulang mulai HH:MM`.
- Alur identik check-in (lokasi → challenge → kamera/blink → sukses) tetapi memakai endpoint dan sesi terpisah; pesan ditulis ulang untuk konteks “pulang”.
- Sukses → halaman dimuat ulang dan state server menampilkan `Presensi Selesai`; duplikat check-out menampilkan pesan “sudah tercatat sebelumnya” tanpa error merah; respons hilang/timeout diperlakukan sebagai belum terkonfirmasi dan diselesaikan dengan memuat ulang, bukan mengklaim sukses/gagal.
- Check-out terlalu awal ditolak server (409) dengan alasan waktu; check-out tanpa check-in ditolak server (409).

## Dashboard dan CTA presensi T17

- `/student/dashboard` menampilkan tanggal hari ini, jam server, kelas, jadwal efektif, status hari ini, dan satu CTA presensi.
- `cta_label` dan `cta_enabled` selalu datang dari server (`attendance_state_service`). Browser tidak menghitung kelayakan, jam, atau status sendiri.
- CTA aktif memakai label FR-STU-03: `Presensi Masuk`, `Pulang mulai HH:MM`, `Presensi Pulang`, `Presensi Selesai`.
- CTA nonaktif tetap terlihat dengan `aria-disabled` dan `reason` yang menjelaskan kapan aksi tersedia (misalnya "Presensi dibuka pukul 06:30."), sesuai aturan tombol disabled memiliki label alasan.
- Status hari ini memakai label PRD §12 (`Hadir`, `Terlambat`, `Izin`, `Sakit`, `Alpa`, `Libur`) dan `Belum Absen` sebagai derived state. Sumber teknis `finalization_job` hanya ditampilkan sebagai `Sistem`.
- Record tersimpan lebih utama daripada jadwal terkini. Jika jadwal berubah menjadi libur/tidak tersedia setelah check-in, status Hadir/Terlambat tetap terlihat dan CTA berikutnya dinonaktifkan.
- Submit presensi (kamera, lokasi, blink, LBPH) tersedia pada T18–T19: CTA tetap menampilkan state dan alasan dari server; alur submit mengikuti seksi Check-in tervalidasi T18 dan Check-out T19.
- Dashboard tetap terlindungi enrollment gate: siswa `face_registered=false` diarahkan ke `/student/enrollment`, bukan ke dashboard.

## Riwayat dan pemulihan Siswa T21

- `/student/history` hanya menerima bulan berjalan pada zona waktu aplikasi. Tanggal tanpa record ditentukan oleh penempatan tanggal tersebut dan jadwal efektif; tanggal mendatang adalah `Belum berlangsung`, dan record kosong tidak disimpulkan sebagai Alpa.
- Identitas selalu berasal dari session. Endpoint menolak `student_id`/`user_id`; respons memakai `no-store` dan tidak memuat foto, key storage, koordinat, accuracy, score wajah, atau metadata liveness.
- Detail tanggal memperlihatkan status, waktu masuk/pulang, sumber/keterangan yang aman, serta kelas/tahun ajaran bila ada.
- State dashboard diperbarui setiap 30 detik saat halaman terlihat dan kamera tidak berjalan, serta saat `pageshow`, kembali online, atau tab terlihat lagi. CTA tetap dikontrol server.
- Respons submit yang terputus menghentikan kamera dan frame stream, mengunci CTA, lalu memeriksa aksi semula melalui endpoint state. Check-in yang ditemukan memuat ulang halaman; status belum terkonfirmasi tidak otomatis berubah menjadi check-out.
- Profil Siswa menampilkan nama, NISN, kelas/tahun ajaran, perubahan password, dan logout.

## Monitoring Guru T22

- Dashboard memilih kelas aktif pada tahun ajaran berjalan; jika tidak ada, memilih penugasan terbaru. Guru tanpa kelas melihat empty state. Ringkasan harian memakai roster akun aktif dan status record untuk snapshot kelas terpilih.
- Daftar tindak lanjut memuat Alpa tersimpan, belum check-in setelah cutoff, dan check-in tanpa checkout setelah jadwal pulang. Alasan bersifat informatif dan tidak mengubah status. Hari libur tidak menghasilkan tindak lanjut berbasis cutoff.
- `/teacher/attendance` menampilkan satu baris per record dengan filter bulan, status, nama/NISN, serta pagination server-side 25 baris. Siswa tanpa record hari ini hanya terlihat sebagai Belum Absen pada ringkasan.
- `/teacher/students` mencakup roster aktif maupun nonaktif pada kelas. Detail `/teacher/students/<id>` menampilkan kalender lintas bulan dan rincian record yang tersimpan; navigasi kembali mempertahankan kelas serta filter sumber.
- Scope dihitung ulang pada setiap request berdasarkan penugasan Guru saat ini dan snapshot `attendance_records.class_id`. Kelas historis hanya dapat dibaca selama masih ditugaskan; record tanpa snapshot kelas tidak ditampilkan. ID/kelas di luar scope menghasilkan 404.
- Layar monitoring Guru baca-saja; dari detail histori Guru yang saat ini ditugaskan dapat membuka evidence presensi. Admin membuka evidence terbaru melalui detail Siswa.
- Halaman evidence hanya menampilkan foto jika tersedia, waktu WIB, dan keterangan lokasi/accuracy yang tercatat. Koordinat, score wajah, dan storage key tidak dirender. Jangan hitung ulang validasi historis memakai geofence terbaru.
- Otorisasi role/scope dibaca ulang untuk halaman dan setiap gambar dari row record; Guru memakai snapshot `attendance_records.class_id` dan penugasan saat request. Record tanpa snapshot tidak dapat dibaca Guru. Respons file privat memakai `no-store`; key rusak atau file hilang dijawab sebagai bukti tidak tersedia.

## Status manual Guru T24

- Form status hanya tampil untuk tanggal hari ini menurut waktu server WIB dan siswa di kelas aktif yang saat ini ditugaskan kepada Guru; hari libur tidak menyediakan aksi.
- Guru dapat menetapkan Izin/Sakit dengan keterangan wajib atau Alpa setelah cutoff efektif. Alpa hasil job dapat dikoreksi hari itu. Hadir/Terlambat otomatis serta record yang sudah memiliki check-in tetap terkunci.
- Status buatan Guru dapat dibatalkan sampai cutoff jika belum ada check-in. Server memeriksa ulang aturan ini saat menyimpan; pesan sukses/error berasal dari hasil operasi server.
- Transisi status dicatat pada audit tanpa menyalin keterangan bebas. Permintaan tanpa CSRF atau dengan siswa/kelas di luar scope ditolak.

## Monitoring Admin T25

- `/admin/attendance` dapat dibuka Admin melalui navigasi Monitoring Presensi. Filter tanggal dan kelas membatasi ringkasan serta jurnal; status dan nama/NISN membatasi jurnal. Ringkasan dihitung penuh di server dan tidak bergantung pada halaman jurnal yang sedang ditampilkan.
- Untuk hari ini, seluruh status dihitung hanya untuk roster akun aktif pada kelas/tahun ajaran aktif. Status berasal dari record tersimpan; anggota roster tanpa status tersimpan adalah Belum Absen, termasuk ketika jadwal hari itu libur. Jangan menyimpulkan Alpa dari record kosong. Untuk tanggal lampau tampilkan status tersimpan saja; jangan mengasumsikan roster lama atau menampilkan record kosong sebagai Belum Absen.
- Jurnal berisi satu record tersimpan per baris dengan pagination stabil 25 baris. Detail Siswa Admin mempertahankan histori per bulan dan menyediakan tautan ke evidence yang dilindungi T23. Kelas historis tetap bisa difilter untuk membaca recordnya.
- Filter invalid ditolak server, pengguna selain Admin ditolak termasuk melalui URL langsung, dan respons memakai `no-store`. Empty state dan kegagalan database memiliki keterangan serta aksi yang jelas.

## Ekspor dan audit Admin T26

- Tautan Unduh Excel mempertahankan filter jurnal; endpoint ekspor semua baris cocok tanpa batas halaman dan hanya berisi data presensi operasional yang aman. Teks formula-like disimpan sebagai teks, bukan formula.
- `/admin/audit-logs` menampilkan pelaku, waktu WIB, aksi, dan target dengan filter dan pagination 25. Metadata mentah, secrets, serta payload biometrik tidak dirender.
- Kedua fitur hanya dapat dibuka Admin melalui route terlindungi dan URL langsung; respons privat memakai `no-store`.

## Data analisis T27

- Fitur analisis hanya berasal dari periode yang berada dalam satu tahun ajaran yang sudah berakhir dan lengkap. Kalender wajib hadir dibaca dari snapshot per kelas/tanggal; edit jadwal sesudah snapshot tidak mengubah hari historis.
- Jika asal snapshot merupakan rekonstruksi, hasil menampilkan penanda tersebut. Data historis tanpa status pada hari wajib hadir ditolak sebagai belum lengkap; status Alpa tidak pernah ditebak dari record kosong.
- Akun siswa nonaktif tetap dianalisis dari penempatan tahun ajarannya. Siswa dengan `effective_days=0` tidak diberi persentase dan ditandai tidak layak.

## Analisis K-Means T28–T29

- Admin dapat menjalankan analisis sekali untuk periode dalam satu tahun ajaran yang sudah berakhir. Periode belum lengkap dan dataset yang tidak dapat membentuk tiga cluster ditolak dengan pesan yang dapat ditindaklanjuti.
- Run berhasil menyimpan metadata versi formula/aturan label, fitur siswa, centroid, parameter model, dan tanda snapshot rekonstruksi. Kegagalan transaksi tidak boleh meninggalkan run parsial; detail histori membaca hasil tersimpan.
- Label tinggi/sedang/rendah mengikuti arah kualitas fitur, bukan nomor cluster dari model. Grafik menampilkan tiga metrik sebagai grafik terpisah karena satuannya berbeda; tabel memakai centroid asli yang sama.
- Chart.js dimuat dari asset lokal. Form submit memiliki nonce sekali pakai dan constraint database; tombol submit langsung dinonaktifkan saat dikirim. Run ganda diarahkan ke hasil yang sama atau ditolak jika token form sudah kedaluwarsa.
- Sumber: PRD §13–14; `kmeans_clustering_service.py`, `kmeans_run_service.py`, halaman Admin `/admin/analytics` dan detail `/admin/analytics/runs/<id>`.

## PWA dan kondisi jaringan T30

- Start URL PWA menuju `/login?source=pwa`. Session yang masih aktif mengikuti redirect autentikasi ke dashboard sesuai role.
- Service Worker root-scope hanya menyimpan allowlist asset publik dan offline page generik. Navigasi selalu mencoba jaringan terlebih dahulu; API, halaman profil/dashboard, evidence, foto, logout, dan request presensi tidak disimpan atau diantrikan.
- Halaman offline tidak menyatakan presensi tersedia. Banner pada halaman aplikasi menjelaskan kebutuhan koneksi; ketika jaringan pulih, pengguna dapat memuat ulang agar state server diperbarui.
- Kenaikan versi cache dilakukan eksplisit pada `CACHE_NAME` ketika konten asset offline berubah. Aktivasi hanya menghapus cache milik aplikasi dengan prefix `presensi-shell-`.
- Tes kode memverifikasi aturan cache dan banner. Instalasi, browser Android, kamera/GPS, serta kondisi jaringan nyata tetap perlu dibuktikan pada T32.

## Enrollment Siswa T14

- Siswa `face_registered=false` wajib mengganti password sementara terlebih dahulu. Sesudahnya semua akses ke dashboard, profil, dan endpoint Siswa/presensi/wajah diarahkan ke `/student/enrollment`; halaman enrollment dan logout tetap tersedia. Pemeriksaan dilakukan server-side pada setiap request.
- Halaman enrollment memakai frame Siswa maksimal 480px dan hanya menyediakan logout selama gate aktif. Halaman menampilkan progres pose depan, kiri, kanan milik akun yang sedang login; tidak menampilkan storage key atau data siswa lain.
- Progres pose menandai pose yang sudah tersimpan valid. Status 3/3 tidak menyatakan enrollment selesai selama model belum diproses dan `face_registered` belum benar. Capture kamera, kualitas, blink, dan auto-capture masuk T15; status final dan login ulang masuk T16.
- Jika progres tidak dapat dibaca, tampilkan error dan aksi **Coba lagi**. Siswa dengan role lain yang membuka route enrollment langsung menerima akses ditolak dari server.

## Capture enrollment T15

- Kamera hanya diminta setelah Siswa membaca pemberitahuan penyimpanan dan menekan aksi kamera; pratinjau hanya berada di halaman sendiri. Halaman mengungkap bahwa frame dikirim melalui HTTPS dan capture valid disimpan pada storage privat. Pemberitahuan UI bukan pengganti kebijakan sekolah tentang persetujuan, retensi, atau penghapusan biometrik.
- Satu kamera mengerjakan pose depan → kiri → kanan. Instruksi, status kamera, quality, dan langkah blink diumumkan melalui status live region. Server mengamati urutan mata terbuka → tertutup → terbuka dan menentukan auto capture; browser tidak mengirim boolean keberhasilan blink.
- Pose tersimpan ditandai dengan teks. Pengguna dapat mengambil ulang pose tersimpan; sampel sebelumnya hanya diganti jika capture baru berhasil. Kegagalan kamera, frame, jaringan, atau challenge memberi arahan coba ulang tanpa membuang pose lain. Kamera dihentikan saat halaman tersembunyi atau ditinggalkan.
- Detektor pose kiri/kanan masih berupa panduan operator; jangan tampilkan seolah sudut kepala sudah diverifikasi otomatis. Setelah 3/3, tampilkan bahwa model masih menunggu proses T16; jangan arahkan ke dashboard dan jangan menyatakan enrollment selesai.
- Sumber: PRD §10.1 dan §10.3; API `app/face/routes.py`; batas state enrollment berasal dari service T15 dan finalisasi model dari T16.

## Status dan pemulihan

- Flash message berada di dekat form dan memakai live region.
- Empty state menyebutkan data yang belum tersedia dan tidak menampilkan angka nol seolah data sudah ada.
- Error login tetap generik; CSRF dan session tetap menjadi keputusan backend.
- Akun dengan password sementara selalu diarahkan ke halaman ganti password sebelum dashboard atau profil; profil hanya memuat akun aktif yang sedang login.
- Tombol disabled memiliki label alasan dan tidak mengubah URL.

## Form

- Semua field memiliki label eksplisit dan autocomplete yang sesuai.
- Form memakai `novalidate`; validasi server tetap menjadi sumber kebenaran.
- Password masked dan tidak pernah ditaruh di URL atau copy UI.
- Fokus keyboard terlihat dengan ring primary.

## Sumber dan batasan

- Token visual: `DESIGN.md` → `app/static/css/tailwind.input.css` → `app/static/css/app.css`.
- Role dan tujuan navigasi: PRD §16 serta `AGENTS.md`.
- T05 menyediakan role shell dasar; alur enrollment T14 menambahkan route khusus tanpa membuka akses ke dashboard normal sebelum wajah terdaftar.
- T22 mengaktifkan navigasi Guru ke Dashboard, Presensi, dan Siswa; T23 menautkan evidence dari detail histori Guru serta detail Siswa Admin.
- T06 menyediakan profil role-specific dan logout; informasi kelas tetap placeholder sampai master data T10 tersedia.

## Visual dan interaksi T31

- Arah tampilan mengikuti referensi yang disetujui: cream `#FFF5E3`, surface putih, coral `#ED896F`, mint `#7CD3AA`, kuning hangat `#F2C879`, ink `#303044`, muted `#686472`, serta tombol primary `#A6412D` dengan teks putih. Coral terang tidak memakai teks putih dan warna coral tidak berarti error.
- Plus Jakarta Sans variable dibundel di `app/static/fonts/plus-jakarta-sans-variable.ttf`; lisensi SIL OFL disertakan di folder yang sama. Fallback menggunakan Segoe UI/system sans. Font dimuat dari aset proyek, bukan dari layanan eksternal. POC T04 mempertahankan font sistem.
- Token dijaga satu sumber di `app/static/css/tailwind.input.css`; `DESIGN.md`, `app/static/css/app.css`, manifest, metadata browser, ikon, dan Chart.js mengikuti pilihan tersebut. Radius kartu 24px, input 14px, tombol/pill membulat, Admin sidebar 256px, dan shell Siswa tetap maksimal 480px.
- Tujuh ilustrasi SVG lokal digunakan sesuai konteks: sambutan publik/Admin, aksen kecil sambutan Guru, presensi, panduan enrollment, keberhasilan enrollment setelah server mengonfirmasi pembaruan model, bantuan lokasi, serta keadaan tanpa data/offline. Gambar dekoratif memakai alt kosong karena judul/keterangan menyampaikan makna; rasio SVG dipertahankan dan ukurannya dideklarasikan agar layout stabil. Ilustrasi data kosong hanya muncul pada keadaan tanpa data yang dipilih, bukan pada error atau tabel berisi.
- Halaman T04 POC tidak ikut redesign: body POC mempertahankan token warna lama dan theme-color lamanya. JS password bersama melewati halaman POC.
- State jaringan tampil di alur dokumen agar tidak menutupi field atau tombol. Nav Siswa/Guru mempertahankan tujuan lama dan memakai safe-area; Admin menampilkan pemberitahuan di lebar kurang dari 1024px. Status tetap memiliki label teks.
- Aksi tampil/sembunyikan password ditambahkan ke field password Siswa/Guru/Admin; label dan `aria-pressed` berubah bersama visibilitas. Fokus keyboard terlihat, input/select/tanggal native dipertahankan, dan `prefers-reduced-motion` tetap aktif.
- PWA menggunakan background/theme cream, ikon coral/mint, serta cache `presensi-shell-v9`. Worker tetap membatasi cache pada aset publik yang terdaftar, termasuk font dan ilustrasi; halaman/API privat/foto/logout/presensi tetap online-only.

### Kontras dan keterbacaan tiga role

- Teks biasa menggunakan rasio minimal 4.5:1; border kontrol dan indikator penting minimal 3:1. CTA, link, dan navigasi aktif memakai coral gelap `#A6412D` dengan teks putih. Coral terang `#ED896F`, mint, dan kuning dipakai sebagai bidang dengan teks ink `#303044`.
- Teks sekunder memakai muted `#686472`; status memakai warna gelap dengan label teks. Kalender mempertahankan huruf status dan legenda sehingga warna bukan satu-satunya pembawa makna.
- Body dan tabel minimal 14px; metadata, badge, dan navigasi minimal 12px; field mobile tetap minimal 16px. Target sentuh minimal 44px. Field memakai border kontrol yang lebih tegas dan outline fokus ink yang terlihat.
- Preview sintetis 26 September menemukan teks putih pada coral lama, muted lama, dan badge lama di bawah target. Sesudah perbaikan, contoh rasio terhitung adalah 6.15:1 (teks putih/CTA), 5.31:1 (muted/cream), 5.15:1 (ink/coral), dan 4.51–4.88:1 (badge status); seluruh bidang aksen diuji dengan teks ink minimal 4.5:1 dan border kontrol minimal 3:1. Pemeriksaan screenshot semua route/state, zoom 200%, serta perangkat nyata tetap memerlukan bukti khusus sebelum T31/T32 ditutup.

### Kontrak DOM yang dipertahankan

- Presensi Siswa: `#attendance-today` dan atribut `data-csrf`, `data-state-url`, `data-start-url`, `data-frame-url`, `data-checkout-start-url`, `data-checkout-frame-url`; `#attendance-cta[data-cta-action]`, `[data-cta-text]`, `#attendance-status`, `#attendance-camera-panel`, `#attendance-video`, `#attendance-placeholder`, `#attendance-cancel`, `#attendance-refresh`, serta `[data-schedule-time]` tetap menjadi kontrak JS. Panel bantuan lokasi baru hanya bereaksi pada pesan lokasi error/warning.
- Enrollment: `#face-enrollment` dengan `data-csrf`, `data-challenge-url`, `data-frame-url`, `data-saved-poses`; ID kamera/canvas/status/start/stop, `data-pose-row`, `data-pose-status`, `data-recapture-pose` tetap dipertahankan.
- Teacher monitoring: URL dan query `class_id`, `month`, `status`, `q`, `page`, navigasi bottom, serta tautan detail yang membawa filter asal tidak diubah.
- Chart analitik masih membaca satu sumber run tersimpan yang sama untuk grafik dan tabel. Tidak ada route, role guard, schema, query bisnis, atau payload/API yang diubah oleh T31.

### Hasil review visual T31

Pada 26 September 2026, screenshot preview menggunakan fixture sintetis setelah perbaikan kontras ditinjau pada dashboard Siswa 360px, dashboard Guru 768px, dashboard Admin 1024px, serta Guru desktop. Review sebelumnya juga mencakup kalender Siswa 390px dan tabel Admin 1440px. Form login 360px sebelumnya telah diperiksa setelah font lokal dipasang; font ter-load dan tombol password berfungsi dengan Enter serta focus ring. Baseline sebelum redesign tidak tersimpan; audit visual seluruh route/state, pembesaran teks 200%, dan keyboard lintas halaman masih belum selesai.


### Ilustrasi v2 — 26 September 2026

Tujuh ilustrasi original sudah dibuat melalui built-in imagegen dan dipasang, termasuk sambutan khusus Guru dan Admin. Master PNG dan prompt: `design/illustrations/v2/`; WebP: `app/static/illustrations/`. Dua aset (`location-v2`, `empty-v2`) **masih tertunda karena kuota imagegen**; SVG lama (`location.svg`, `empty.svg`) tetap digunakan. Pada tahap B1 (Opsi B) ketujuh WebP di-downscale ke lebar 800px dengan kualitas dipertahankan (q=92) sehingga precache turun dari ±975 KB ke bawah 700 KB; master PNG tidak diubah dan skrip `scripts/optimize_illustrations.py` bersifat idempoten. Matriks aset aktif/superseded/pending ada di `app/static/illustrations/README.md`. Rincian penempatan, verifikasi, batas pembesaran teks, dan bukti screenshot lokal: [catatan ilustrasi v2](design/illustrations/v2/README.md).


### Login mobile — 26 September 2026

Varian `.login-page` pada viewport <640px memakai header coral ringkas dan kartu form putih solid, radius 24px, padding 20px, margin luar 16px. Form dan kontrol tetap sama; judul mobile menjadi “Masuk ke Presensi”. Desktop tidak memakai varian ini. Password toggle dapat membungkus saat teks diperbesar, banner jaringan mengikuti alur dokumen. Cache aset terkini **v8**, menggantikan v7 dari tahap ilustrasi. Verifikasi: 273 unit test, enam tes Node PWA, build CSS, syntax Service Worker, serta pemeriksaan browser ukuran 320–1440px dan teks 200% lulus. [Bukti dan batas verifikasi](docs/LOGIN_MOBILE_REDESIGN.md). T31 keseluruhan dan T32 tetap terpisah.
