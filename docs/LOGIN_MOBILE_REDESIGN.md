# Verifikasi redesign login mobile

Tanggal: 26 September 2026.

## Perubahan

Login di viewport <640px menggunakan header coral ringkas dengan identitas sekolah
dan ilustrasi lokal, diikuti kartu putih solid. Kartu memiliki radius 24px,
padding 20px, margin luar 16px, border dekoratif dan bayangan halus. Field memakai
label permanen, font minimal 16px dan tinggi minimal 48px. Kontrol password
tetap memakai JavaScript bersama; pada ruang sempit/pembesaran teks dapat turun
baris tanpa mengambil seluruh area input. Banner jaringan berada dalam alur
dokumen pada login mobile agar tidak menutupi field saat keyboard/scroll.

Seluruh perubahan dibatasi `.login-page`. Halaman ubah password, profil, publik,
dan layout login >=640px tidak memakai varian mobile. Tidak ada perubahan API,
database, dependency, autentikasi, CSRF atau redirect. Cache aset menjadi
`presensi-shell-v8`; aktivasi menghapus v7, tetap dengan allowlist aset publik.

## Hasil pengujian

- Baseline: 20 tes autentikasi/UI/PWA lulus. Setelah perubahan: **273 unit test**
  lulus; tes terarah terakhir **21 lulus**. Satu tes ditambahkan untuk memastikan
  error database tetap menampilkan form dan pesan aman tanpa detail exception.
- Enam tes Node PWA lulus, termasuk penghapusan cache v7 dan larangan cache API,
  evidence, logout serta request presensi. Build CSS dan syntax Service Worker lulus.
- Browser sintetis: 320/360/390/430/639/640/768/1440px. Mobile menampilkan header
  sebelum form; 640px ke atas mempertahankan komposisi sebelumnya. Tidak ditemukan
  overflow horizontal, termasuk ketika dibandingkan dengan clientWidth setelah
  scrollbar vertikal muncul.
- State yang ditinjau: normal, kredensial salah, rate limit, database tidak tersedia,
  logout, offline dan koneksi pulih. State visual menggunakan pesan fixture;
  HTTP/CSRF/session diuji lewat suite Flask, event jaringan lewat tes Node.
- Pembesaran teks 200% diuji melalui root font 32px pada fixture, viewport 320px.
  Nama sekolah membungkus, field tetap dapat digunakan, password toggle turun baris.
  Ini pengujian resize teks, bukan klaim pengujian browser zoom/keyboard Android.
- Layar pendek 390x400: fokus mengikuti Username → Password → Tampilkan → Masuk,
  outline terlihat dan halaman dapat digulir. Toggle diuji dua arah dengan input
  sintetis; tidak ada password akun nyata yang dipakai.
- Rasio warna aktual: putih/tombol **6,15:1**, muted/putih **5,75:1**,
  ink/coral **5,15:1**, border kontrol/putih **4,29:1**.
- Screenshot baseline dan hasil, metrik viewport serta rasio warna tersimpan lokal
  dalam `instance/login-mobile-review/` (diabaikan Git).

Keyboard Android, safe-area perangkat, dan mode PWA standalone nyata tetap T32.
Pekerjaan ini tidak menyelesaikan seluruh audit T31 atau dua ilustrasi v2 tertunda.
