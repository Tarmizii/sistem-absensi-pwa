/* T04 diagnostics only. No enrollment or attendance writes. */
(() => {
  const $ = (id) => document.getElementById(id);
  const reveal = $("show-code");
  if (reveal) {
    reveal.disabled = false;
    reveal.addEventListener("click", () => {
      const visible = $("access-code").type === "password";
      $("access-code").type = visible ? "text" : "password";
      reveal.textContent = visible ? "Sembunyikan kode" : "Tampilkan kode";
      reveal.setAttribute("aria-pressed", String(visible));
    });
    return;
  }
  const video = $("camera");
  if (!video) return;
  const csrf = $("poc").dataset.csrf;
  const canvas = document.createElement("canvas");
  let stream = null, timer = null, busy = false, starting = false, generation = 0;
  let savedPoses = [], blinkCount = 0, events = [], lastSignal = "";
  const labels = { front: "depan", left: "kiri", right: "kanan" };
  function record(type, result = {}) {
    events.push({ time: new Date().toISOString(), type, expected: $("expected").value,
      condition: $("condition").value, ...result });
    events = events.slice(-200);
    $("events").textContent = `${events.length} kejadian tercatat pada halaman ini.`;
  }
  function status(message, error = false) {
    $("status").textContent = message;
    $("status").className = `flash mt-4 ${error ? "flash-error" : ""}`;
  }
  function controls() {
    $("start").disabled = busy || starting || !!stream || !$("consent").checked;
    $("stop").disabled = !stream && !starting;
    document.querySelectorAll("[data-pose]").forEach((b) => { b.disabled = !stream || busy; });
    $("predict").disabled = !stream || busy || savedPoses.length !== 3;
    $("reset").disabled = busy || starting;
    $("end").disabled = busy || starting;
  }
  function stop(message = "Kamera dimatikan. Tekan Nyalakan kamera untuk mencoba lagi.") {
    generation += 1;
    clearTimeout(timer);
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    status(message);
    controls();
  }
  async function api(path, form) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, { method: "POST", headers: { "X-CSRF-Token": csrf },
        body: form, signal: controller.signal, cache: "no-store" });
      const result = await response.json();
      if (response.status === 401) stop(result.error);
      if (!response.ok) throw Object.assign(new Error(result.error || "Pengujian gagal. Coba lagi."), { result });
      return result;
    } finally { clearTimeout(timeout); }
  }
  async function sendFrame(mode = "inspect", pose = "") {
    if (!stream || busy || !video.videoWidth) return;
    busy = true;
    controls();
    const current = generation;
    const ratio = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * ratio);
    canvas.height = Math.round(video.videoHeight * ratio);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    try {
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
      if (!blob) throw new Error("Frame tidak tersedia. Nyalakan ulang kamera.");
      if (current !== generation) return;
      const form = new FormData();
      form.append("frame", blob, "frame.jpg"); form.append("mode", mode); form.append("pose", pose);
      const result = await api("/api/frame", form);
      if (current !== generation) return;
      savedPoses = result.poses;
      $("poses").textContent = `Sampel sementara ${savedPoses.length}/3: ${savedPoses.map((p) => labels[p]).join(", ") || "belum ada"}.`;
      $("metrics").textContent = `Kecerahan ${result.brightness} · Ketajaman ${result.sharpness} · Mata terdeteksi ${result.eye_count}`;
      if (result.blink_signal) {
        blinkCount += 1;
        $("blink").textContent = `${blinkCount} sinyal kedipan sementara teramati. Periksa apakah sesuai kedipan nyata.`;
        record("blink_signal", result);
      }
      if (mode === "predict") $("score").textContent = `Distance LBPH: ${result.distance}. Catat sebagai ${$("expected").selectedOptions[0].text.toLowerCase()}; belum ada keputusan otomatis.`;
      status(result.message || (result.quality_ok ? "Satu wajah terlihat; kualitas melewati batas percobaan." : "Kualitas belum cukup. Tambah cahaya dan tahan kamera stabil."), !result.quality_ok);
      const signal = `${result.quality_ok}/${result.eye_count}`;
      if (mode !== "inspect" || signal !== lastSignal) record(mode, { pose, ...result });
      lastSignal = signal;
    } catch (error) {
      if (current !== generation) return;
      const message = error.name === "AbortError" ? "Server terlalu lama merespons. Periksa Wi-Fi lalu nyalakan ulang kamera." : error.message;
      if (error.name === "AbortError" || error instanceof TypeError) stop(message);
      status(message, true);
      if (mode !== "inspect" || lastSignal !== message) record(`${mode}_error`, { error: message, ...(error.result || {}) });
      lastSignal = message;
    } finally { busy = false; controls(); }
  }
  async function loop() {
    await sendFrame();
    if (stream) timer = setTimeout(loop, 350);
  }
  $("start").addEventListener("click", async () => {
    if (!$("consent").checked) { status("Centang persetujuan peserta sebelum menyalakan kamera.", true); $("consent").focus(); return; }
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) { status("Kamera membutuhkan HTTPS yang dipercaya. Pasang sertifikat CA dari halaman setup.", true); return; }
    starting = true; controls(); status("Menunggu izin kamera dari browser…");
    const current = ++generation;
    try {
      const opened = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      if (current !== generation) { opened.getTracks().forEach((t) => t.stop()); return; }
      stream = opened; video.srcObject = opened;
      await video.play();
      record("camera_started", { secure_context: window.isSecureContext, width: video.videoWidth, height: video.videoHeight });
      status("Kamera aktif. Hadapkan satu wajah ke kamera.");
      loop();
    } catch (error) {
      const messages = { NotAllowedError: "Izin kamera ditolak. Izinkan kamera pada setelan situs Chrome, lalu coba lagi.", NotFoundError: "Kamera tidak ditemukan pada perangkat.", NotReadableError: "Kamera sedang dipakai aplikasi lain. Tutup aplikasi tersebut lalu coba lagi." };
      const message = messages[error.name] || "Kamera gagal dibuka. Periksa izin dan coba lagi.";
      stop(message); status(message, true); record("camera_error", { error: message });
    } finally { starting = false; controls(); }
  });
  $("stop").addEventListener("click", () => { stop(); record("camera_stopped"); });
  $("consent").addEventListener("change", () => { if (!$("consent").checked) stop("Persetujuan dilepas. Kamera dimatikan."); controls(); });
  document.querySelectorAll("[data-pose]").forEach((button) => button.addEventListener("click", () => sendFrame("capture", button.dataset.pose)));
  $("predict").addEventListener("click", () => sendFrame("predict"));
  $("reset").addEventListener("click", async () => {
    stop(); busy = true; controls();
    try {
      await api("/api/reset"); savedPoses = []; blinkCount = 0;
      $("poses").textContent = "Sampel sementara 0/3: belum ada.";
      $("score").textContent = "Ambil tiga pose baru sebelum mengukur pencocokan.";
      $("blink").textContent = "Sinyal kedipan belum teramati.";
      status("Sampel dan model sudah dihapus. Catatan hasil tetap dapat diunduh."); record("samples_reset");
    } catch (error) { status(error.message, true); } finally { busy = false; controls(); }
  });
  $("end").addEventListener("click", async () => {
    stop(); busy = true; controls();
    try { await api("/api/end"); window.location.reload(); }
    catch (error) { status(error.message, true); busy = false; controls(); }
  });
  $("download").addEventListener("click", () => {
    const report = { task: "T04", created_at: new Date().toISOString(), browser: navigator.userAgent,
      secure_context: window.isSecureContext, viewport: { width: innerWidth, height: innerHeight },
      limitations: "Pose berlabel operator; blink provisional; threshold LBPH belum ditetapkan; bukan bukti siap produksi.", events };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "hasil-t04.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop("Kamera dihentikan saat meninggalkan halaman. Nyalakan kembali untuk melanjutkan."); });
  window.addEventListener("pagehide", () => stop());
  record("page_opened");
  $("download").disabled = false;
  $("reset").disabled = false;
  $("end").disabled = false;
  controls();
})();
