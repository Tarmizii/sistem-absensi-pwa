---
version: alpha
name: "Sistem Presensi SMA Negeri 4 Lhokseumawe"
description: "Soft Bento School App untuk presensi sekolah yang hangat, jelas, dan tenang digunakan."
colors:
  background: "#F6F4EE"
  surface: "#FFFFFF"
  primary: "#725CF6"
  primary-soft: "#EEE9FF"
  lime: "#DDF68A"
  text: "#191919"
  muted: "#707070"
  border: "#E7E4DD"
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
  student-max: "30rem"
  admin-sidebar: "16rem"
components:
  button:
    backgroundColor: "#725CF6"
    textColor: "#FFFFFF"
    rounded: "0.875rem"
    height: "3rem"
  card:
    backgroundColor: "#FFFFFF"
    rounded: "1.5rem"
    padding: "1.5rem"
  input:
    backgroundColor: "#FFFFFF"
    textColor: "#191919"
    rounded: "0.875rem"
    height: "3rem"
  navigation:
    backgroundColor: "#EEE9FF"
    textColor: "#191919"
    rounded: "1.25rem"
  status-success:
    textColor: "#207A56"
  status-warning:
    textColor: "#9B6515"
  status-danger:
    textColor: "#B54444"
  muted-copy:
    textColor: "#707070"
  canvas:
    backgroundColor: "#F6F4EE"
    textColor: "#191919"
  divider:
    backgroundColor: "#E7E4DD"
  accent:
    backgroundColor: "#DDF68A"
---

# Sistem Presensi SMA Negeri 4 Lhokseumawe Design System

## Overview

### Creative North Star

Ruang kerja sekolah yang terasa seperti meja administrasi yang dirapikan sebelum hari belajar dimulai: cream sebagai kertas, purple sebagai penanda tindakan, dan lime sebagai catatan penting yang mudah ditemukan. Satu panel utama boleh membawa ekspresi; navigasi dan form tetap tenang agar pekerjaan harian cepat dipahami.

### Product context and register

- **Audience and primary job:** Siswa melakukan presensi, Guru/Wali Kelas memantau kelas, dan Admin menyiapkan data serta konfigurasi.
- **Target market(s) and evidence:** SMA Negeri 4 Lhokseumawe; kebutuhan, role, dan breakpoint mengikuti PRD versi 1.0.
- **Locale(s) and language policy:** Bahasa Indonesia untuk label, status, bantuan, dan pesan error. Identifier teknis tetap berbahasa Inggris.
- **Usage scene:** Siswa memakai layar mobile; Guru memakai mobile atau desktop; Admin memakai desktop. Layar sentuh memakai target minimal 3rem.
- **Register:** Product utility dengan sentuhan editorial 2D yang ringan; bukan dashboard korporat yang padat.
- **Memorable signature:** Aksen lime dipakai sebagai penanda langkah penting di atas bidang cream/purple.
- **Restraint:** Tabel, form, status, dan pesan error mengutamakan keterbacaan. Tidak ada dekorasi yang mengalahkan tindakan utama.
- **Anti-references:** Jangan menyerupai template admin neon, glassmorphism berlebihan, atau kartu statistik yang semuanya sama penting.
- **Token ownership/runtime mapping:** Nilai di frontmatter adalah kontrak visual; implementasinya berada di `app/static/css/tailwind.input.css` dan hasil build `app/static/css/app.css`, dengan Tailwind CLI lokal sebagai adapter.

## Colors

Gunakan `background` untuk kanvas, `surface` untuk panel, `primary` untuk tindakan dan fokus, `primary-soft` untuk state aktif, dan `lime` hanya untuk aksen/prompt penting. `text`, `muted`, serta `border` menjaga hierarchy pada layar cream. Status success, warning, dan danger selalu disertai label teks; warna bukan satu-satunya pembawa arti. T04/T15 tidak boleh menjadikan warna sebagai pengganti hasil biometrik.

## Typography

Plus Jakarta Sans menjadi pilihan utama dengan fallback Segoe UI. Judul memakai weight 800 dan tracking rapat; body memakai ukuran sekitar 1rem dengan line-height 1.5; label dan status memakai weight 700–800. Casing kalimat digunakan untuk copy UI. Angka statistik boleh memakai ukuran besar, tetapi tidak boleh menghilangkan label dan konteksnya.

## Layout

Breakpoint mengikuti PRD: mobile di bawah 640px, tablet 640–1023px, desktop mulai 1024px. Admin memakai sidebar 16rem dan delapan tujuan; Guru memakai sidebar di desktop serta tiga tujuan pada bottom navigation mobile; Siswa mempertahankan frame mobile maksimal 480px dengan tiga tujuan bottom navigation. Grid dashboard memakai panel bento 12 kolom pada desktop dan satu kolom pada layar kecil. Konten utama tidak dikunci ke tinggi viewport agar keyboard dan zoom tetap dapat mencapai semua kontrol.

## Elevation & Depth

Hierarchy terutama berasal dari tonal surface, border tipis, dan ruang kosong. Shadow hanya dipakai pada auth card dan bottom navigation agar terpisah dari kanvas. Panel dashboard tidak memakai shadow berat. Backdrop blur bottom navigation boleh gagal tanpa menghilangkan kontras solid surface.

## Shapes

Panel memakai radius 1.5rem; control dan button memakai radius 0.875rem; badge memakai pill. Border menggunakan `border`. Fokus keyboard memakai outline purple 3px dengan offset yang terlihat. Disabled state mengurangi opacity dan menggunakan cursor not-allowed, tetapi tetap memberi label alasan.

## Components

### Foundational visual states

Setiap link/button memiliki hover, active, dan focus-visible yang terlihat. Disabled destinations ditampilkan sebagai teks dan ikon yang redup dengan `aria-disabled` serta alasan “belum tersedia”. Flash message memakai live region; error menggunakan tone merah dengan teks yang dapat ditindaklanjuti.

### Buttons and actions

Primary button purple untuk tindakan utama. Lime dipakai sebagai aksen pada konteks yang aman, bukan untuk destructive action. Logout tetap berupa form POST dengan CSRF. Tombol disabled tidak menjanjikan fitur yang belum ada.

### Navigation and data display

Label navigasi selalu tampil bersama ikon. Active state menggunakan background soft purple dan warna primary. Admin desktop menampilkan delapan tujuan PRD; destination yang belum mempunyai route tetap disabled sampai backend tersedia.

### Forms and overlays

Form memakai label eksplisit, autocomplete yang sesuai, `novalidate`, pesan flash live, dan focus ring. Password selalu masked. Modal/overlay belum diperlukan pada T05; jangan menambahkannya sebelum ada workflow yang membutuhkannya.

### Iconography

Icon inline mengikuti bentuk Phosphor yang ringan, stroke rounded, ukuran sekitar 18px. Ikon tidak berdiri sendiri pada navigasi; label teks tetap menjadi nama aksesibel.

### Motion

Transisi 160ms hanya menguatkan hover/focus. `prefers-reduced-motion: reduce` mematikan gerakan. Tidak ada animasi dekoratif pada dashboard awal.

### Content and data visualization

Copy singkat, aktif, dan berbahasa Indonesia. Empty state menjelaskan data yang belum tersedia dan langkah berikutnya. Angka kosong ditampilkan sebagai em dash dengan label, bukan angka nol yang mengesankan data sudah ada.

## Do's and Don'ts

- **Do:** Pertahankan cream/purple/lime dan hierarchy yang tenang di semua role.
- **Do:** Uji shell pada mobile sempit, tablet, dan desktop sebelum menambah modul baru.
- **Don't:** Menyembunyikan tujuan yang belum tersedia seolah-olah sudah berfungsi; gunakan disabled state yang jelas.
- **Don't:** Menjadikan warna, ikon, atau kartu statistik sebagai satu-satunya penjelas status.
