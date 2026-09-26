/* Student check-in/check-out submission: location first, liveness, then identity (T18–T19).
 * The server decides eligibility, liveness progress, and identity; this script
 * only captures geolocation/camera frames and renders server responses. */
(() => {
  const cta = document.getElementById("attendance-cta");
  if (!cta) return;

  const root = document.getElementById("attendance-today");
  const status = document.getElementById("attendance-status");
  const panel = document.getElementById("attendance-camera-panel");
  const video = document.getElementById("attendance-video");
  const placeholder = document.getElementById("attendance-placeholder");
  const cancel = document.getElementById("attendance-cancel");
  if (!root || !status || !panel || !video || !placeholder || !cancel) return;

  const csrf = root.dataset.csrf;
  const refreshButton = document.getElementById("attendance-refresh");
  const locationHelp = document.getElementById("attendance-location-help");
  cta.dataset.serverEnabled = cta.disabled ? "false" : "true";
  const canvas = document.createElement("canvas");
  let stream = null, timer = null, busy = false, challenge = null, generation = 0;
  let activeAction = cta.dataset.ctaAction;
  let activeFrameUrl = "";

  // Attendance is online-only by policy: no offline queue exists anywhere, and
  // this guard keeps the device from opening the camera with no way to submit.
  function applyConnectivity() {
    if (navigator.onLine) {
      cta.dataset.offline = "false";
      if (cta.dataset.locked !== "true") setCta(false);
      return;
    }
    cta.dataset.offline = "true";
    cta.disabled = true;
    cta.querySelector("[data-cta-text]").textContent = "Presensi perlu koneksi internet";
    announce("Presensi memerlukan koneksi internet. Sambungkan kembali lalu muat ulang.", "error");
  }

  function announce(message, tone = "info") {
    status.textContent = message;
    status.dataset.tone = tone;
    if (locationHelp) locationHelp.hidden = !(tone !== "info" && /lokasi|location|gps|perangkat/i.test(message));
  }

  function setCta(running, label) {
    cta.disabled = running || cta.dataset.locked === "true" || cta.dataset.serverEnabled !== "true"
      || cta.dataset.offline === "true";
    if (label) cta.querySelector("[data-cta-text]").textContent = label;
  }

  function stopCamera(message, tone = "info") {
    generation += 1;
    clearTimeout(timer);
    timer = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.hidden = true;
    placeholder.hidden = false;
    panel.hidden = true;
    cancel.hidden = true;
    busy = false;
    challenge = null;
    setCta(false);
    if (message) announce(message, tone);
  }

  async function postJSON(url, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(body),
        signal: controller.signal,
        cache: "no-store",
      });
      if (response.redirected) {
        window.location.assign(response.url);
        throw new Error("Sesi berakhir. Masuk kembali untuk melanjutkan.");
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(data.error || "Terjadi kesalahan. Coba lagi.");
        error.retry = !!data.retry;
        throw error;
      }
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function readLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.onLine) {
        reject(new Error("Perangkat sedang offline. Presensi memerlukan koneksi internet."));
        return;
      }
      if (!navigator.geolocation) {
        reject(new Error("Perangkat tidak mendukung pelacakan lokasi."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
        (err) => {
          if (err.code === 1) reject(new Error("Izin lokasi ditolak. Aktifkan izin lokasi di pengaturan perangkat."));
          else if (err.code === 2) reject(new Error("Lokasi tidak dapat dibaca. Aktifkan GPS lalu coba lagi."));
          else reject(new Error("Pengambilan lokasi melewati batas waktu. Coba lagi."));
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
      );
    });
  }

  async function openCamera() {
    try {
      const detected = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      });
      stream = detected;
      video.srcObject = stream;
      video.hidden = false;
      placeholder.hidden = true;
      panel.hidden = false;
      cancel.hidden = false;
      await video.play();
    } catch {
      throw new Error("Kamera tidak dapat diakses. Periksa izin kamera di pengaturan perangkat.");
    }
  }

  function sendFrame() {
    const current = generation;
    timer = setTimeout(async () => {
      if (current !== generation || busy || !stream) return;
      if (video.readyState < 2) { sendFrame(); return; }
      busy = true;
      try {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
        const formData = new FormData();
        formData.append("challenge_id", challenge);
        formData.append("frame", blob, "frame.jpg");
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
          const resp = await fetch(activeFrameUrl, {
            method: "POST",
            headers: { "X-CSRF-Token": csrf },
            body: formData,
            signal: controller.signal,
            cache: "no-store",
          });
          clearTimeout(timeout);
          if (resp.redirected) {
            window.location.assign(resp.url);
            return;
          }
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok) {
            if (data.retry) { stopCamera(data.error || "Terjadi kesalahan. Coba lagi.", "error"); return; }
            announce(data.error || "Terjadi kesalahan. Coba lagi.", "error");
          } else if (data.captured) {
            stopCamera(data.message || "Berhasil.", "success");
            setTimeout(() => window.location.reload(), 1200);
          } else {
            announce(data.message || "Lanjutkan mengikuti instruksi.", "info");
          }
        } catch {
          clearTimeout(timeout);
          stopCamera();
          cta.dataset.locked = "true";
          cta.disabled = true;
          refreshButton.hidden = false;
          announce("Status presensi belum terkonfirmasi. Periksa status yang tersimpan sebelum mencoba lagi.", "warning");
          return;
        }
      } finally {
        busy = false;
        if (current === generation && stream) sendFrame();
      }
    }, 500);
  }

  cta.addEventListener("click", async () => {
    if (cta.disabled) return;
    activeAction = cta.dataset.ctaAction;
    const isCheckout = activeAction === "checkout";
    const startUrl = isCheckout ? root.dataset.checkoutStartUrl : root.dataset.startUrl;
    activeFrameUrl = isCheckout ? root.dataset.checkoutFrameUrl : root.dataset.frameUrl;
    const fallbackLabel = isCheckout ? "Presensi Pulang" : "Presensi Masuk";
    try {
      const position = await readLocation();
      announce("Lokasi diterima. Meminta sesi presensi…", "info");
      const start = await postJSON(startUrl, position);
      challenge = start.challenge_id;
      const current = ++generation;
      announce(`${start.message || "Hadapkan satu wajah ke kamera."}`, "info");
      await openCamera();
      if (current !== generation) return;
      setCta(true, "Mengambil wajah…");
      sendFrame();
    } catch (error) {
      setCta(false, fallbackLabel);
      announce(error.message, "error");
    }
  });

  refreshButton.addEventListener("click", async () => {
    refreshButton.disabled = true;
    try {
      const result = await window.refreshAttendanceState?.({
        uncertainAction: activeAction === "checkout" ? "checkout" : "checkin",
      });
      if (!result?.ok) {
        announce("Status belum dapat diperiksa. Periksa koneksi lalu coba lagi.", "warning");
        return;
      }
      if (result.confirmed) {
        window.location.reload();
        return;
      }
      cta.dataset.locked = "false";
      refreshButton.hidden = true;
      announce("Belum ada hasil presensi untuk aksi tadi. Anda dapat mengulangi aksi jika masih tersedia.", "info");
      setCta(false);
    } finally {
      refreshButton.disabled = false;
    }
  });

  cancel.addEventListener("click", () => stopCamera("Presensi dibatalkan sebelum tersimpan."));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && stream) stopCamera("Kamera dihentikan karena halaman tidak aktif.");
  });
  window.addEventListener("pagehide", () => {
    if (stream) stream.getTracks().forEach((track) => track.stop());
  });
  applyConnectivity();
  window.addEventListener("online", applyConnectivity);
  window.addEventListener("offline", applyConnectivity);
})();
