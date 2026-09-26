# Audit visual T31

Bukti render nyata (bukan asumsi) untuk penutupan T31 redesign visual. Audit ini memakai Chrome headless pada fixture sintetis; **bukan** verifikasi perangkat nyata.

## Opsi A — kontras & aksesibilitas (selesai)

Perhitungan rasio riil dari token di `app/static/css/tailwind.input.css`:

| Pasangan | Sebelum | Sesudah | Catatan |
|---|---|---|---|
| Badge danger (teks putih) | `#b54444` 4.51:1 (marginal) | `#9c3232` 6.0:1 | Memperkuat teks status error |
| Badge warning (teks putih) | `#9b6515` 4.54:1 (marginal) | `#8a5610` 5.7:1 | Memperkuat teks status peringatan |
| Dot status mint | 1.7:1 (FAIL 1.4.11) | + ring 1px `rgba(48,48,68,.65)` | Penanda non-teks wajib punya edge |
| Label uppercase | 12px | 13px + `line-height: 1.4` | Minimal 13px |

Semua badge status sudah berpasangan dengan label teks; kalender punya glyph + `aria-label`; tombol ikon berpasangan teks/`aria-label`; form control memakai `--color-control-border` (3.97:1). Regresi dikunci di `tests/test_ui.py`.

## Opsi B — PWA shell & polish

### B1 — budget precache

Prescache sebelum: ±975 KB (CSS 55.8 + font 172.2 + 7 WebP 730.8 + ikon 11.6 + sisanya 3.9).

Prescache sesudah: **< 700 KB** (regresi dikunci di `tests/test_pwa.py::PrecacheBudgetTests`).

Ketujuh WebP di-downscale ke lebar 800px (q=92). Lebar render device adalah 12–25rem, sehingga 800px sudah melebihi kebutuhan 2×. Master PNG di `design/illustrations/v2/` tidak diubah. Atribut `width`/`height` template disinkronkan ke ukuran baru.

### B7 — audit overflow render

Chrome di Windows meng-clamp lebar layout ke ~504px sehingga `--window-size` tidak mengemulasikan lebar ponsel. Solusi: render di dalam iframe berukuran tetap agar media query benar-benar melihat 360/640/720/768/1440px.

Hasil (`SCROLLW == VW` = tanpa overflow halaman):

| Role | Viewport | Status |
|---|---|---|
| Siswa dashboard | 360px | ok |
| Siswa dashboard (zoom 200%) | 640px | ok |
| Guru dashboard/attendance/students | 768px | ok |
| Guru (zoom 200%) | 640px | ok |
| Admin dashboard/attendance/analytics/audit/students | 1440px | ok |
| Admin (zoom 200%) | 720px | ok |
| Login & home publik | 360/768/1440px | ok |

Overflow tabel Admin pada 720px disengaja: `.data-table { min-width: 46rem }` di dalam `.table-wrap { overflow-x: auto }`. Halaman tidak overflow; tabel yang dapat digulir mendatar.

### B2 — ketahanan worker

- Precache `cache.addAll` (gagal atomik) → `Promise.allSettled` per-aset + peringatan console.
- `isPrivatePath` sebagai pertahanan berlapis: route privat tidak pernah dilayani dari cache.

### B4 — install & update

Banner install dan toast update hanya untuk role Siswa (`body.student-shell`); Guru/Admin tidak pernah melihatnya. Banner otomatis disembunyikan saat kamera aktif.

### B5 — penjaga offline

CTA presensi dinonaktifkan + diberi pesan saat offline; kamera/lokasi tidak dibuka. Tidak ada antrean offline.

## Batas verifikasi (tetap T32)

Audit ini hanya render sintetis. Belum terbukti: kamera, GPS, pose, blink, pencahayaan, dan koneksi lambat/putus pada perangkat Android nyata melalui HTTPS. Tidak ada klaim anti-spoofing GPS/blink atau anti-replay.

## Bukti screenshot

Disimpan di `docs/visual-audit/`. Render ulang:

```powershell
.venv\Scripts\python.exe -m scripts.visual_audit
```

Optimasi ilustrasi (idempoten):

```powershell
.venv\Scripts\python.exe scripts/optimize_illustrations.py --dry-run
```
