---
version: alpha
name: "Sistem Presensi SMA Negeri 4 Lhokseumawe"
description: "School attendance app dengan tampilan hangat, ilustrasi editorial 2D, dan alur yang jelas."
colors:
  background: "#FFF5E3"
  surface: "#FFFFFF"
  primary: "#A6412D"
  primary-soft: "#FCE5DC"
  coral: "#ED896F"
  mint: "#7CD3AA"
  warm-yellow: "#F2C879"
  text: "#303044"
  muted: "#686472"
  border: "#E8DDCB"
  control-border: "#81796E"
  mint-soft: "#E6F5EC"
  success: "#207A56"
  warning: "#9B6515"
  danger: "#B54444"
typography:
  sans:
    fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
    fontSize: "1rem"
    lineHeight: "1.5"
  utility:
    fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
    fontSize: "0.75rem"
    lineHeight: "1.4"
rounded:
  DEFAULT: "0.875rem"
  sm: "0.75rem"
  md: "1.25rem"
  lg: "1.5rem"
spacing:
  page-gutter: "clamp(1.25rem, 4vw, 3rem)"
  section-gap: "1rem"
  student-max: "480px"
  admin-sidebar: "16rem"
components:
  button:
    backgroundColor: "#A6412D"
    textColor: "#FFFFFF"
    rounded: "0.875rem"
    height: "3rem"
  card:
    backgroundColor: "#FFFFFF"
    rounded: "1.5rem"
    padding: "1.5rem"
  input:
    backgroundColor: "#FFFFFF"
    textColor: "#303044"
    rounded: "0.875rem"
    height: "3rem"
  navigation:
    backgroundColor: "#FCE5DC"
    textColor: "#303044"
    rounded: "1.25rem"
  status-success:
    textColor: "#207A56"
  status-warning:
    textColor: "#9B6515"
  status-danger:
    textColor: "#B54444"
  muted-copy:
    textColor: "#686472"
  canvas:
    backgroundColor: "#FFF5E3"
    textColor: "#303044"
  divider:
    backgroundColor: "#E8DDCB"
  accent:
    backgroundColor: "#7CD3AA"
---

# Sistem Presensi SMA Negeri 4 Lhokseumawe Design System

## Overview

### Creative North Star

Ruang kerja sekolah yang terasa seperti meja administrasi yang dirapikan sebelum hari belajar dimulai: cream sebagai kertas, coral untuk aksi, mint untuk penanda positif, serta kuning hangat sebagai aksen. Ilustrasi pelajar 2D memberi ekspresi; navigasi dan form tetap tenang agar pekerjaan harian cepat dipahami.

### Product context and register

- **Audience and primary job:** Siswa melakukan presensi, Guru/Wali Kelas memantau kelas, dan Admin menyiapkan data serta konfigurasi.
- **Target market(s) and evidence:** SMA Negeri 4 Lhokseumawe; kebutuhan, role, dan breakpoint mengikuti PRD versi 1.0.
- **Locale(s) and language policy:** Bahasa Indonesia untuk label, status, bantuan, dan pesan error. Identifier teknis tetap berbahasa Inggris.
- **Usage scene:** Siswa memakai layar mobile; Guru memakai mobile atau desktop; Admin memakai desktop. Layar sentuh memakai target minimal 3rem.
- **Register:** Product utility dengan sentuhan editorial 2D yang ringan; bukan dashboard korporat yang padat.
- **Memorable signature:** Bidang coral dan mint membingkai ilustrasi pelajar di atas latar cream.
- **Restraint:** Tabel, form, status, dan pesan error mengutamakan keterbacaan. Tidak ada dekorasi yang mengalahkan tindakan utama.
- **Anti-references:** Jangan menyerupai template admin neon, glassmorphism berlebihan, atau kartu statistik yang semuanya sama penting.
- **Token ownership/runtime mapping:** Nilai di frontmatter adalah kontrak visual; implementasinya berada di `app/static/css/tailwind.input.css` dan hasil build `app/static/css/app.css`, dengan Tailwind CLI lokal sebagai adapter.

## Colors

Gunakan `background` untuk kanvas, `surface` untuk panel, `primary` untuk tombol utama dan tautan, `primary-soft` untuk state aktif, serta `coral`, `mint`, dan `warm-yellow` untuk bidang beraksen dengan teks ink gelap. Teks biasa harus mencapai kontras minimal 4.5:1; batas kontrol dan indikator fokus minimal 3:1. Border `border` hanya untuk pemisah dekoratif, sedangkan field memakai `control-border`. Status success, warning, danger dan seluruh status presensi selalu disertai label; coral merepresentasikan merek, bukan error. T04/T15 tidak boleh menjadikan warna sebagai pengganti hasil biometrik.

## Typography

Plus Jakarta Sans variable dibundel lokal di `app/static/fonts/plus-jakarta-sans-variable.ttf` dari [repositori Google Fonts](https://github.com/google/fonts/tree/main/ofl/plusjakartasans), dengan lisensi di `app/static/fonts/OFL.txt`; tidak ada font eksternal yang dimuat. Segoe UI/system sans menjadi fallback. POC T04 secara eksplisit mempertahankan font sistem sebelumnya. Judul memakai weight 800 dan tracking rapat; body memakai ukuran sekitar 1rem dengan line-height 1.5; tabel dan teks utama minimal 0.875rem, label sekunder minimal 0.75rem. Label dan status memakai weight 700–800. Casing kalimat digunakan untuk copy UI. Angka statistik boleh memakai ukuran besar, tetapi tidak boleh menghilangkan label dan konteksnya.

## Layout

Breakpoint mengikuti PRD: mobile di bawah 640px, tablet 640–1023px, desktop mulai 1024px. Admin memakai sidebar 16rem dan delapan tujuan; Guru memakai sidebar di desktop serta tiga tujuan pada bottom navigation mobile; Siswa mempertahankan frame mobile maksimal 480px dengan tiga tujuan bottom navigation. Grid dashboard memakai panel bento 12 kolom pada desktop dan satu kolom pada layar kecil. Konten utama tidak dikunci ke tinggi viewport agar keyboard dan zoom tetap dapat mencapai semua kontrol.

## Elevation & Depth

Hierarchy terutama berasal dari tonal surface, border tipis, dan ruang kosong. Shadow hanya dipakai pada auth card dan bottom navigation agar terpisah dari kanvas. Panel dashboard tidak memakai shadow berat. Backdrop blur bottom navigation boleh gagal tanpa menghilangkan kontras solid surface.

## Shapes

Panel memakai radius 1.5rem; control dan button memakai radius 0.875rem; badge memakai pill. Border panel menggunakan `border`; field memakai `control-border`. Fokus keyboard memakai outline ink 3px dengan offset yang terlihat. Disabled state memakai cursor not-allowed dan tetap memberi label alasan tanpa meredupkan teks sampai sulit dibaca.

## Components

### Foundational visual states

Setiap link/button memiliki hover, active, dan focus-visible yang terlihat. Disabled destinations ditampilkan sebagai teks dan ikon yang redup dengan `aria-disabled` serta alasan “belum tersedia”. Flash message memakai live region; error menggunakan tone merah dengan teks yang dapat ditindaklanjuti.

### Buttons and actions

Primary button dark-coral dengan teks putih untuk tindakan utama. Coral terang, mint, dan kuning hangat memakai teks ink gelap; ketiganya bukan warna status otomatis. Logout tetap berupa form POST dengan CSRF. Tombol disabled tidak menjanjikan fitur yang belum ada.

### Navigation and data display

Label navigasi selalu tampil bersama ikon. Active state menggunakan background soft coral dan warna primary. Admin desktop menampilkan tujuan PRD; shortcut dashboard menuju fitur yang tersedia.

### Forms and overlays

Form memakai label eksplisit, autocomplete yang sesuai, `novalidate`, pesan flash live, dan focus ring. Password selalu masked. Modal/overlay belum diperlukan pada T05; jangan menambahkannya sebelum ada workflow yang membutuhkannya.

### Iconography

Icon inline mengikuti bentuk Phosphor yang ringan, stroke rounded, ukuran sekitar 18px. Ikon tidak berdiri sendiri pada navigasi; label teks tetap menjadi nama aksesibel.

### Motion

Transisi 160ms hanya menguatkan hover/focus. `prefers-reduced-motion: reduce` mematikan gerakan. Tidak ada animasi dekoratif pada dashboard awal.

### Content and data visualization

Copy singkat, aktif, dan berbahasa Indonesia. Empty state menjelaskan data yang belum tersedia dan langkah berikutnya. Angka kosong ditampilkan sebagai em dash dengan label, bukan angka nol yang mengesankan data sudah ada.

## Do's and Don'ts

- **Do:** Pertahankan cream/coral/mint/kuning hangat dan hierarchy yang tenang di semua role.
- **Do:** Uji shell pada mobile sempit, tablet, dan desktop sebelum menambah modul baru.
- **Don't:** Menyembunyikan tujuan yang belum tersedia seolah-olah sudah berfungsi; gunakan disabled state yang jelas.
- **Don't:** Menjadikan warna, ikon, atau kartu statistik sebagai satu-satunya penjelas status.


### Ilustrasi v2 — 26 September 2026

Tujuh ilustrasi original sudah dibuat melalui built-in imagegen dan dipasang, termasuk sambutan khusus Guru dan Admin. Master PNG dan prompt: `design/illustrations/v2/`; WebP: `app/static/illustrations/`, total 748102 byte. Dua aset (`location-v2`, `empty-v2`) **masih tertunda karena kuota imagegen**; SVG lama tetap digunakan. Cache aktif v7, hanya aset publik. Paket sembilan ilustrasi dan T31 belum ditandai selesai. Rincian penempatan, verifikasi, batas pembesaran teks, dan bukti screenshot lokal: [catatan ilustrasi v2](design/illustrations/v2/README.md).


### Login mobile — 26 September 2026

Varian `.login-page` pada viewport <640px memakai header coral ringkas dan kartu form putih solid, radius 24px, padding 20px, margin luar 16px. Form dan kontrol tetap sama; judul mobile menjadi “Masuk ke Presensi”. Desktop tidak memakai varian ini. Password toggle dapat membungkus saat teks diperbesar, banner jaringan mengikuti alur dokumen. Cache aset terkini **v8**, menggantikan v7 dari tahap ilustrasi. Verifikasi: 273 unit test, enam tes Node PWA, build CSS, syntax Service Worker, serta pemeriksaan browser ukuran 320–1440px dan teks 200% lulus. [Bukti dan batas verifikasi](docs/LOGIN_MOBILE_REDESIGN.md). T31 keseluruhan dan T32 tetap terpisah.
