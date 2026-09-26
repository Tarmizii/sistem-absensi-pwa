# Ilustrasi produk v2

Tanggal: 26 September 2026. Generator: **built-in imagegen**, bukan fallback API.
Palet cream/coral/mint mengikuti referensi pengguna; `school-day-v2.png` menjadi
acuan keluarga karakter. Prompt lengkap disimpan dalam `prompts.json`.

## Aset dan penempatan

| Aset | Penempatan | WebP (byte) | Status |
|---|---|---:|---|
| school-day-v2 | Login | 109348 | Terpasang |
| welcome-v2 | Halaman publik | 142310 | Terpasang |
| teacher-welcome-v2 | Sambutan Guru, tablet/desktop | 70940 | Terpasang |
| admin-welcome-v2 | Sambutan Admin | 129488 | Terpasang |
| attendance-v2 | Kartu presensi Siswa | 81870 | Terpasang |
| enrollment-v2 | Pengantar enrollment | 110142 | Terpasang |
| success-v2 | Enrollment setelah konfirmasi server | 104004 | Terpasang |
| location-v2 | Bantuan lokasi | — | Belum dibuat: kuota imagegen habis |
| empty-v2 | State kosong dan offline | — | Belum dibuat: kuota imagegen habis |

Master PNG asli berada di folder ini; versi delivery berada di
`app/static/illustrations/`. Total tujuh WebP: **748102 byte**, masing-masing
di bawah 200000 byte. `sizes.json` mencatat dimensi asli dan ukuran berkas.
WebP dienkode quality 85, method 6 menggunakan Pillow yang sudah tersedia;
tidak ada crop, recolor, resize, atau penghilangan alpha. Semua aset mempunyai
alpha transparan. SVG asli dipertahankan untuk pemulihan.

`location.svg` dan `empty.svg` tetap dipakai sampai kedua master baru tersedia.
Jangan mengganti referensinya dengan nama berkas yang belum ada. Paket sembilan
ilustrasi belum dinyatakan selesai. Lanjutkan kedua prompt tertunda setelah kuota
pulih, optimalkan dan periksa hasil, lalu ganti referensi beserta allowlist dan
naikkan versi cache lagi.

## Integrasi dan pemeriksaan

- Ukuran intrinsik eksplisit, `object-fit: contain`, alt dekoratif kosong.
  Kartu presensi membatasi lebar gambar 128px pada ukuran teks standar;
  gambar Admin memakai sekitar sepertiga area isi panel.
- Area enrollment memiliki rasio 18:11 yang tetap ketika gambar berubah menjadi
  sukses. Pergantian `src` tetap berada dalam cabang `result.enrollment_complete`.
- Cache `presensi-shell-v7`: tujuh WebP baru dan dua SVG sementara. Master PNG
  tidak masuk static/precache. API, halaman privat, evidence dan presensi tetap
  online-only. MIME WebP didaftarkan eksplisit agar konsisten pada Windows.
- Baseline UI/PWA: 12 tes lulus. Setelah integrasi: 272 unit test, enam tes Node
  PWA, skrip recovery transaksi hilang, syntax Service Worker/enrollment, build CSS,
  dan `git diff --check` lulus. Tes UI/PWA diulang setelah penyesuaian porsi terakhir:
  12 tes lulus.
  Suite penuh sempat menemukan MIME Windows `application/octet-stream`; diperbaiki
  dan suite dijalankan ulang hingga lulus.
- Preview memakai fixture sintetis loopback, tanpa data/akun produksi. Bukti lokal:
  `instance/illustrations-v2-review/`. Baseline Siswa 390 dan Guru 1440 tersimpan;
  screenshot baseline Admin gagal ditangkap dan tidak diklaim tersedia.
- Pemeriksaan sesudah pemasangan: Siswa 360/390, Guru 390/768/1440,
  Admin 1024/1440, login 390/1440, publik/enrollment/kosong/offline 390.
  Semua gambar yang dirujuk termuat, tanpa overflow horizontal pada ukuran standar.
- Pembesaran teks 200% disimulasikan dengan root font 32px pada preview saja,
  bukan klaim pengujian browser zoom atau Android. Gambar tetap termuat, tetapi
  layout teks Siswa/Admin menjadi sangat sempit; audit reflow menyeluruh tetap
  pekerjaan T31. Screenshot full-page browser juga dapat memiliki artefak stitching;
  gunakan screenshot viewport dan ukuran DOM sebagai pembanding.
- Tidak mengubah form transaksi, API, database atau otorisasi. Smoke MySQL tidak
  diulang untuk perubahan aset ini. Kamera/GPS Android tetap T32.
