(() => {
  const form = document.querySelector("#geofence-location-form");
  const button = document.querySelector("#geofence-location-check");
  const feedback = document.querySelector("#geofence-location-feedback");
  const csrf = document.querySelector('input[name="csrf_token"]')?.value;
  if (!form || !button || !feedback) return;
  const geofenceActive = button.dataset.geofenceActive === "true";

  const explainBrowserError = (error) => {
    if (error.code === 1) return "Izin lokasi ditolak. Izinkan lokasi di pengaturan browser, lalu coba lagi.";
    if (error.code === 2) return "Lokasi belum tersedia. Aktifkan layanan lokasi perangkat dan coba lagi.";
    if (error.code === 3) return "Permintaan lokasi melewati batas waktu. Coba lagi di area dengan sinyal GPS lebih baik.";
    return "Lokasi belum dapat dibaca. Coba lagi.";
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!geofenceActive) {
      feedback.textContent = "Geofence belum aktif. Lengkapi koordinat dan batas accuracy sekolah sebelum menguji lokasi.";
      return;
    }
    if (!window.isSecureContext) {
      feedback.textContent = "Lokasi hanya dapat diperiksa melalui HTTPS atau localhost.";
      return;
    }
    if (!navigator.geolocation) {
      feedback.textContent = "Browser ini tidak menyediakan layanan lokasi.";
      return;
    }
    button.disabled = true;
    feedback.textContent = "Meminta izin dan membaca lokasi perangkat…";
    navigator.geolocation.getCurrentPosition(async (position) => {
      const coords = position.coords;
      try {
        const response = await fetch("/admin/geofence/check", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf ?? "" },
          body: JSON.stringify({ latitude: coords.latitude, longitude: coords.longitude,
            accuracy: coords.accuracy }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error("Pemeriksaan server gagal. Coba lagi.");
        if (result.reason === "inside") {
          feedback.textContent = `Lokasi berada di dalam radius (sekitar ${result.distance_meters} meter).`;
        } else if (result.reason === "outside") {
          feedback.textContent = `Lokasi berada di luar radius (sekitar ${result.distance_meters} meter).`;
        } else if (result.reason === "accuracy_unreliable") {
          feedback.textContent = "Lokasi belum cukup akurat. Aktifkan GPS dan coba lagi.";
        } else if (result.reason === "not_configured") {
          feedback.textContent = "Geofence belum aktif atau konfigurasi sekolah belum lengkap.";
        } else {
          feedback.textContent = result.message ?? "Lokasi tidak dapat digunakan. Periksa izin atau coba lagi.";
        }
      } catch (error) {
        feedback.textContent = error instanceof Error ? error.message : "Koneksi pemeriksaan gagal. Coba lagi.";
      } finally {
        button.disabled = false;
      }
    }, (error) => {
      feedback.textContent = explainBrowserError(error);
      button.disabled = false;
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });
})();
