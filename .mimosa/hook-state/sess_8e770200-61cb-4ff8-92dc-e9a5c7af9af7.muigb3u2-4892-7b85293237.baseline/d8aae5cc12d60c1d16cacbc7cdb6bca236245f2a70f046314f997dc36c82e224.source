/* Student face enrollment: one manual capture per pose, validated by the server. */
(() => {
  const root = document.getElementById("face-enrollment");
  if (!root) return;

  const $ = (id) => document.getElementById(id);
  const video = $("enrollment-video");
  const canvas = $("enrollment-canvas");
  const status = $("enrollment-status");
  const startButton = $("enrollment-start");
  const captureButton = $("enrollment-capture");
  const stopButton = $("enrollment-stop");
  const noticeCheckbox = $("enrollment-notice-read");
  const placeholder = $("camera-placeholder");
  const enrollmentIllustration = $("enrollment-illustration");
  const progressMessage = $("enrollment-progress-message");
  const csrf = root.dataset.csrf;
  const captureUrl = root.dataset.captureUrl;
  const successIllustrationUrl = root.dataset.successIllustrationUrl;
  const poses = ["front", "left", "right"];
  const poseLabels = { front: "Depan", left: "Kiri", right: "Kanan" };
  const posePrompts = {
    front: "Hadap lurus ke kamera dengan mata terbuka lebar.",
    left: "Putar wajah ke kiri perlahan dengan mata terbuka lebar.",
    right: "Putar wajah ke kanan perlahan dengan mata terbuka lebar.",
  };
  const state = {
    stream: null,
    pose: null,
    busy: false,
    saved: new Set((root.dataset.savedPoses || "").split(",").filter(Boolean)),
  };

  function announce(message, tone = "info") {
    if (!message) return;
    status.textContent = message;
    status.dataset.tone = tone;
  }

  function nextPose() {
    return poses.find((pose) => !state.saved.has(pose)) || null;
  }

  function promptFor(pose) {
    const position = poses.indexOf(pose) + 1;
    return `Pose ${position}/3 — ${poseLabels[pose]}: ${posePrompts[pose]} Lalu tekan Ambil foto.`;
  }

  function renderProgress(savedPoses) {
    state.saved = new Set(savedPoses);
    const count = document.getElementById("enrollment-saved-count");
    if (count) count.textContent = String(state.saved.size);
    poses.forEach((pose) => {
      const badge = document.querySelector(`[data-pose-status="${pose}"]`);
      if (!badge) return;
      const isSaved = state.saved.has(pose);
      badge.textContent = isSaved ? "Tersimpan" : "Belum diambil";
      badge.classList.toggle("status-success", isSaved);
      badge.classList.toggle("status-warning", !isSaved);
      const retake = document.querySelector(`[data-recapture-pose="${pose}"]`);
      if (retake) retake.hidden = !isSaved;
    });
  }

  function setCameraControls(active, starting = false) {
    startButton.hidden = active;
    startButton.disabled = !noticeCheckbox.checked || starting;
    startButton.textContent = starting ? "Mengaktifkan kamera…" : "Aktifkan kamera";
    captureButton.hidden = !active;
    captureButton.disabled = !active || state.busy;
    stopButton.hidden = !active;
    stopButton.disabled = !active;
    noticeCheckbox.disabled = active || starting;
    document.querySelectorAll("[data-recapture-pose]").forEach((button) => {
      button.disabled = active || starting;
    });
  }

  async function requestJSON(url, options) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal, cache: "no-store" });
      if (response.redirected) {
        window.location.assign(response.url);
        throw new Error("Sesi berakhir. Masuk kembali untuk melanjutkan.");
      }
      const type = response.headers.get("content-type") || "";
      if (!type.includes("application/json")) throw new Error("Respons server tidak dapat dibaca.");
      const data = await response.json();
      if (!response.ok) {
        const error = new Error(data.error || "Pengambilan belum berhasil. Coba lagi.");
        error.status = response.status;
        error.retry = Boolean(data.retry);
        throw error;
      }
      return data;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function stopCamera(message = "Kamera dihentikan.", tone = "info") {
    if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
    state.pose = null;
    state.busy = false;
    video.srcObject = null;
    video.hidden = true;
    placeholder.hidden = false;
    setCameraControls(false);
    announce(message, tone);
  }

  function playShutter() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    try {
      const context = new AudioContextClass();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.11);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.12);
      oscillator.addEventListener("ended", () => context.close(), { once: true });
    } catch (_error) {
      // Visual and status feedback remain available if sound is unavailable.
    }
  }

  function frameBlob() {
    return new Promise((resolve, reject) => {
      if (!video.videoWidth || !video.videoHeight) {
        reject(new Error("Kamera belum menghasilkan frame. Tunggu sebentar."));
        return;
      }
      const maxSide = 720;
      const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      const context = canvas.getContext("2d", { alpha: false });
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Frame kamera gagal disiapkan.")), "image/jpeg", 0.82);
    });
  }

  async function capturePose() {
    if (!state.stream || state.busy) return;
    const pose = state.pose || nextPose();
    if (!pose) {
      announce("Tiga pose sudah tersimpan. Enrollment menunggu pemrosesan model.", "success");
      return;
    }
    state.pose = pose;
    state.busy = true;
    setCameraControls(true);
    announce(`Memeriksa foto pose ${poseLabels[pose].toLowerCase()}…`, "info");
    try {
      const blob = await frameBlob();
      const form = new FormData();
      form.append("pose", pose);
      form.append("frame", blob, "camera.jpg");
      const result = await requestJSON(captureUrl, {
        method: "POST", headers: { "X-CSRF-Token": csrf }, body: form,
      });
      renderProgress(result.saved_poses || []);
      playShutter();
      const frame = document.querySelector(".enrollment-camera-frame");
      if (frame) {
        frame.dataset.captured = "true";
        window.setTimeout(() => { delete frame.dataset.captured; }, 300);
      }
      if (result.enrollment_complete) {
        if (enrollmentIllustration && successIllustrationUrl) {
          enrollmentIllustration.src = successIllustrationUrl;
        }
        if (progressMessage) {
          progressMessage.textContent = "Tiga pose berhasil diproses dan model wajah telah diperbarui. Silakan masuk kembali.";
        }
        stopCamera(result.message || "Pendaftaran wajah berhasil!", "success");
        const redirect = result.redirect || "/login";
        let countdown = 3;
        const countEl = document.getElementById("enrollment-countdown");
        if (countEl) {
          countEl.textContent = String(countdown);
          countEl.parentElement.hidden = false;
        }
        const tick = window.setInterval(() => {
          countdown -= 1;
          if (countEl) countEl.textContent = String(countdown);
          if (countdown <= 0) {
            window.clearInterval(tick);
            window.location.assign(redirect);
          }
        }, 1000);
        return;
      }
      const next = nextPose();
      state.pose = next;
      announce(`${result.message || "Foto tersimpan."}${next ? ` ${promptFor(next)}` : ""}`, "success");
    } catch (error) {
      const uncertain = error.name === "AbortError" || error instanceof TypeError;
      if (!state.stream) return;
      if (uncertain) {
        stopCamera("Koneksi terputus saat menyimpan. Foto belum tersimpan; nyalakan kamera untuk mencoba lagi.");
        window.setTimeout(() => window.location.reload(), 1500);
      } else {
        // Keep the camera running so the student can adjust and retry immediately.
        announce(error.message || "Foto belum tersimpan. Sesuaikan posisi lalu coba lagi.",
          error.status >= 500 ? "error" : "warning");
      }
    } finally {
      state.busy = false;
      if (state.stream) setCameraControls(true);
    }
  }

  async function startCamera(requestedPose = null) {
    if (!noticeCheckbox.checked) {
      announce("Baca dan centang informasi sebelum mengaktifkan kamera.", "warning");
      noticeCheckbox.focus();
      return;
    }
    if (state.busy) return;
    const pose = requestedPose || nextPose();
    if (!pose) {
      announce("Tiga pose sudah tersimpan. Enrollment menunggu pemrosesan model.", "success");
      return;
    }
    setCameraControls(false, true);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setCameraControls(false);
      announce("Kamera memerlukan halaman HTTPS yang aman. Buka kembali melalui tautan HTTPS.", "error");
      return;
    }
    try {
      if (!state.stream) {
        state.stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: "user" }, width: { ideal: 640 }, height: { ideal: 480 } },
        });
        video.srcObject = state.stream;
        video.hidden = false;
        placeholder.hidden = true;
        await video.play();
      }
      state.pose = pose;
      setCameraControls(true);
      announce(promptFor(pose), "info");
    } catch (error) {
      stopCamera(error.name === "NotAllowedError"
        ? "Izin kamera belum diberikan. Izinkan kamera di pengaturan browser lalu coba lagi."
        : "Kamera tidak dapat dinyalakan. Pastikan kamera tidak sedang dipakai aplikasi lain, lalu coba lagi.", "warning");
    }
  }

  noticeCheckbox.addEventListener("change", () => {
    startButton.disabled = !noticeCheckbox.checked;
    if (noticeCheckbox.checked) announce("Informasi dibaca. Nyalakan kamera saat siap.");
  });
  startButton.addEventListener("click", () => startCamera());
  captureButton.addEventListener("click", () => capturePose());
  stopButton.addEventListener("click", () => stopCamera());
  document.querySelectorAll("[data-recapture-pose]").forEach((button) => {
    button.addEventListener("click", () => startCamera(button.dataset.recapturePose));
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state.stream) stopCamera("Kamera dihentikan karena halaman tidak aktif.");
  });
  window.addEventListener("pagehide", () => {
    if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
  });
})();
