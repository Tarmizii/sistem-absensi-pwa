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

Halaman kamera memerlukan persetujuan peserta sebelum `getUserMedia`, mengirim frame JPEG sementara untuk deteksi satu wajah, brightness, sharpness, jumlah mata, dan sinyal blink provisional. Operator memberi label `front`, `left`, dan `right`; arah kepala belum divalidasi otomatis. Setelah tiga sampel, tombol predict mengembalikan LBPH distance tanpa mengubahnya menjadi persentase atau keputusan cocok otomatis. Tombol unduh menghasilkan JSON tanpa foto.

## Hambatan uji lapangan

T04 belum boleh ditandai selesai sebelum uji Android/browser aktual menggunakan sampel berizin. Uji harus merekam perangkat/browser, permission, tiga pose, satu wajah, frame blur/brightness, contoh blink berhasil/gagal, kecocokan/mismatch, dan distance tanpa menyebut distance sebagai akurasi. Setup ini menghilangkan hambatan akses kamera/HTTPS; hasil perangkat dan kalibrasi tetap harus dicatat oleh operator.
