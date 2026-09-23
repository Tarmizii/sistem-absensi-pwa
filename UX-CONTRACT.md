# UX Contract — Shell, Password, Profil, dan Enrollment

Dokumen ini mencatat perilaku UI yang dapat dilihat pengguna. Aturan domain presensi tetap berasal dari PRD dan service backend.

## Navigasi

| Role | Mobile | Desktop | Aturan |
|---|---|---|---|
| Siswa | Beranda, Riwayat, Profil | Frame mobile maksimal 480px | Beranda aktif pada dashboard; tujuan yang belum tersedia diberi disabled state. |
| Guru/Wali Kelas | Dashboard, Presensi, Siswa | Dashboard, Presensi Kelas, Data Siswa, Profil | Bottom navigation hanya tiga tujuan utama; profil tetap tersedia melalui shell desktop pada tahap berikutnya. |
| Admin | Pesan perangkat tidak didukung pada viewport kecil | Dashboard, Data Siswa, Data Guru, Kelas, Jadwal, Monitoring Presensi, Analitik, Pengaturan | Data Guru tersedia pada T08, Data Siswa pada T09, Kelas pada T10, dan Jadwal reguler serta exception tersedia pada T11–T12; tujuan lain tetap disabled sampai route backend tersedia. |

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

## Enrollment Siswa T14

- Siswa `face_registered=false` wajib mengganti password sementara terlebih dahulu. Sesudahnya semua akses ke dashboard, profil, dan endpoint Siswa/presensi/wajah diarahkan ke `/student/enrollment`; halaman enrollment dan logout tetap tersedia. Pemeriksaan dilakukan server-side pada setiap request.
- Halaman enrollment memakai frame Siswa maksimal 480px dan hanya menyediakan logout selama gate aktif. Halaman menampilkan progres pose depan, kiri, kanan milik akun yang sedang login; tidak menampilkan storage key atau data siswa lain.
- Progres pose menandai pose yang sudah tersimpan valid. Status 3/3 tidak menyatakan enrollment selesai selama model belum diproses dan `face_registered` belum benar. Capture kamera, kualitas, blink, dan auto-capture masuk T15; status final dan login ulang masuk T16.
- Jika progres tidak dapat dibaca, tampilkan error dan aksi **Coba lagi**. Siswa dengan role lain yang membuka route enrollment langsung menerima akses ditolak dari server.

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
- T06 menyediakan profil role-specific dan logout; informasi kelas tetap placeholder sampai master data T10 tersedia.
