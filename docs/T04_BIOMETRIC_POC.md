# T04 — Catatan POC Biometrik

T04 menyiapkan percobaan terisolasi untuk kamera, kualitas frame, eye-state/blink, dan LBPH. POC ini belum menjadi alur enrollment atau presensi dan tidak menerima foto nyata ke repository.

## Keputusan sementara

- `opencv-contrib-python==4.12.0.88` menyediakan `cv2.face.LBPHFaceRecognizer_create`; `numpy==2.2.6` dipakai untuk array gambar.
- Frame diubah ke grayscale, histogramnya diequalize, lalu diubah ukurannya menjadi `200x200` sebelum Haar atau LBPH. LBPH menerima grayscale dan mengembalikan label serta distance; distance bukan probabilitas akurasi.
- Deteksi awal memakai `haarcascade_frontalface_default.xml` dan `haarcascade_eye_tree_eyeglasses.xml` yang disediakan OpenCV.
- `ProvisionalBlinkTracker` hanya mendeteksi urutan mata terlihat lalu tidak terlihat. Ini bukan anti-spoofing dan belum mengikat challenge ke session server.
- Batas brightness dan blur di `face_poc.py` adalah sinyal awal untuk percobaan, bukan threshold produksi.

## Verifikasi offline

```powershell
.venv\Scripts\python.exe -m scripts.run_face_poc
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

POC sintetis hanya membuktikan import, preprocessing, dan API LBPH. Ia tidak membuktikan kamera Android, permission, HTTPS, pose, blink pada wajah nyata, ketahanan cahaya, atau threshold recognition.

## Setup uji Android

POC browser terisolasi tersedia melalui `scripts.setup_t04_android` dan `scripts.run_t04_android`. Setup ini tidak memakai login, database, route enrollment, atau storage produksi. Sampel wajah dan model hanya hidup di memori proses dan sesi berakhir setelah 30 menit atau server dihentikan.

```powershell
.venv\Scripts\python.exe -m scripts.setup_t04_android --ip 10.160.102.172
.venv\Scripts\python.exe -m scripts.run_t04_android
```

Alamat IP harus merupakan alamat Wi-Fi laptop yang dapat dijangkau Android. Terminal mencetak halaman setup HTTP pada port `8084`, halaman kamera HTTPS pada port `8443`, dan kode akses acak. Halaman setup hanya menyajikan sertifikat CA publik. Pasang sertifikat pada Android sebagai **Sertifikat CA**, cocokkan fingerprint SHA-256, lalu buka halaman kamera HTTPS. Setelah pengujian, hapus CA `SMA4 T04 Local Test CA` dari perangkat.

### Akses tautan HTTPS publik sementara

Untuk perangkat yang memakai data seluler atau tidak dapat memasang CA lokal, jalankan server loopback melalui Cloudflare Quick Tunnel:

```powershell
.venv\Scripts\python.exe -m scripts.setup_t04_android
.venv\Scripts\python.exe -m scripts.run_t04_public start
```

Launcher memakai `cloudflared` melalui HTTP/2, memverifikasi sertifikat origin dengan CA lokal, memeriksa URL `trycloudflare.com` sebelum menampilkannya, dan menyediakan `status`/`stop`. Perintah `stop` hanya menghentikan PID serta executable yang tercatat oleh launcher dan cocok dengan waktu mulai proses. Kode akses dirotasi setiap start; proses aplikasi hanya bind pada 127.0.0.1:8443. Quick Tunnel bersifat sementara, maka URL berubah pada start berikutnya dan laptop harus tetap online.

Saat memakai tautan publik, browser mengirim frame kamera lewat layanan jaringan Cloudflare menuju laptop. Beri tahu peserta dan dapatkan persetujuan sebelum mengaktifkan kamera. Pakai hanya sampel berizin. JSON hasil tidak memuat foto; foto serta model sementara disimpan di memori proses aplikasi laptop dan dibuang ketika sesi/umur 30 menit berakhir atau server dihentikan. Jangan menganggap uji ini sebagai persetujuan kebijakan biometrik sekolah.

Halaman kamera memerlukan persetujuan peserta sebelum `getUserMedia`, mengirim frame JPEG sementara untuk deteksi satu wajah, brightness, sharpness, jumlah mata, dan sinyal blink provisional. Operator memberi label `front`, `left`, dan `right`; arah kepala belum divalidasi otomatis. Setelah tiga sampel, tombol predict mengembalikan LBPH distance tanpa mengubahnya menjadi persentase atau keputusan cocok otomatis. Tombol unduh menghasilkan JSON tanpa foto. Browser dibatasi 1 MiB per request; kualitas frame dan parser multipart tetap memvalidasi payload.

## Hasil uji lapangan dan batasan

Atas keputusan pengguna pada 24 September 2026, hasil uji awal Android di bawah diterima untuk menutup gate eksplorasi T04 dan melanjutkan T15. Penerimaan ini bukan bukti threshold terkalibrasi atau kesiapan biometrik production. Uji lanjutan tetap perlu merekam tiga pose, satu wajah, frame blur/brightness, blink disengaja, kecocokan/mismatch, dan distance tanpa menyebut distance sebagai akurasi.

### Hasil Android parsial — 24 September 2026

Laporan `hasil-t04.json` membuktikan halaman berjalan dalam secure context pada Chrome 153 di Android 10 dan kamera dapat dimulai pada 480×640. Dari 33 inspeksi, 32 lolos sinyal kualitas awal dan satu gagal; dua capture tersimpan (`front`, `right`). Empat sinyal blink provisional tercatat, salah satunya pada frame yang tidak lolos kualitas. Deteksi satu wajah belum stabil: 10 inspeksi ditolak karena mendeteksi 0 wajah (2 kali), 2 wajah (6 kali), atau 3 wajah (2 kali).

Laporan ini tidak memuat capture `left` atau event `predict`, sehingga belum ada uji pencocokan orang yang sama/berbeda maupun distance LBPH. Model telepon, kondisi jaringan, dan catatan hasil blink yang disengaja juga tidak dicatat. Pengguna menerima keterbatasan ini agar T15 dapat berjalan; ulangi dengan satu wajah dan latar yang tidak ramai jika kendala deteksi mengganggu. Jangan menyimpulkan kelayakan production atau threshold final dari laporan parsial ini.
