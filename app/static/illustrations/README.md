# Inventaris Ilustrasi

Matriks status aset ilustrasi. Status `superseded` **tidak dihapus** — disimpan sebagai fallback/referensi desain. Master PNG sumber ada di `design/illustrations/v2/`.

## Aktif (dirender di template)

| Aset | Ukuran (display) | Dipakai di | Peran |
|---|---|---|---|
| `welcome-v2.webp` | 800×490 | `home.html` | Sambutan halaman awal publik |
| `school-day-v2.webp` | 800×640 | `auth/login.html` | Hero panel login |
| `teacher-welcome-v2.webp` | 800×489 | `teacher/dashboard.html` | Sambutan dashboard Guru |
| `admin-welcome-v2.webp` | 800×640 | `auth/role_dashboard.html` | Sambutan dashboard Admin |
| `attendance-v2.webp` | 800×489 | `student/dashboard.html` | Kartu CTA presensi Siswa |
| `enrollment-v2.webp` | 800×464 | `student/enrollment.html` | Frame enrollment wajah |
| `success-v2.webp` | 800×489 | `student/enrollment.html` (via JS, `data-success-illustration-url`) | State sukses enrollment |
| `location.svg` | vektor | `student/dashboard.html` | Panel lokasi / geofence |
| `empty.svg` | vektor | `teacher/attendance`, `teacher/dashboard`, `teacher/students`, `admin/student_list` | Empty state generik |

## Superseded (disimpan, tidak dipakai)

Versi v1 digantikan v2 (v2 sudah terpasang dan dirender). File v1 **dipertahankan** di direktori ini, tidak direferensikan template/CSS mana pun.

| Aset | Digantikan oleh |
|---|---|
| `welcome.svg` | `welcome-v2.webp` |
| `school-day.svg` | `school-day-v2.webp` |
| `attendance.svg` | `attendance-v2.webp` |
| `enrollment.svg` | `enrollment-v2.webp` |
| `success.svg` | `success-v2.webp` |

## Pending v2 (masih pakai v1/SVG lama)

Kuota imagegen belum memungkinkan v2 untuk dua aset ini. SVG lama tetap dipakai sampai tersedia.

| Aset (aktif) | v2 yang tertunda |
|---|---|
| `location.svg` | `location-v2` |
| `empty.svg` | `empty-v2` |

##-optimasi

Ketujuh `*-v2.webp` di-downscale ke lebar maks 800px (resolusi render device 2× sudah tercukupi) dengan kualitas dipertahankan (WebP q=92). Master PNG di `design/illustrations/v2/` tidak diubah. Script: `scripts/optimize_illustrations.py` (idempoten — file yang sudah ≤800px dilewati).
