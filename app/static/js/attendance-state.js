/* Refresh the server-owned daily state; never calculate attendance eligibility here. */
(() => {
  const root = document.getElementById("attendance-today");
  const cta = document.getElementById("attendance-cta");
  if (!root || !cta) return;

  const panel = document.getElementById("attendance-camera-panel");
  const feedback = document.getElementById("attendance-status");
  function updateText(id, value, fallback = "—") {
    const node = document.getElementById(id);
    if (node) node.textContent = value || fallback;
  }

  function applyState(data) {
    updateText("attendance-today-date", data.today);
    const dateNode = document.getElementById("attendance-today-date");
    if (dateNode && data.today) dateNode.dateTime = data.today;
    updateText("attendance-server-time", data.server_time);
    updateText("attendance-class-name", data.class_name, "Kelas belum ditetapkan");
    updateText("attendance-status-label", data.status_today, "Belum Absen");
    updateText("attendance-checkin-time", data.checkin_time);
    updateText("attendance-checkout-time", data.checkout_time);
    updateText("attendance-status-source", data.status_source_label ? `Sumber: ${data.status_source_label}` : "Belum ada presensi tersimpan untuk hari ini.");
    updateText("attendance-predicted-status", data.predicted_status);

    cta.dataset.ctaAction = data.state;
    cta.dataset.serverEnabled = data.cta_enabled ? "true" : "false";
    cta.disabled = !data.cta_enabled || cta.dataset.locked === "true";
    const label = cta.querySelector("[data-cta-text]");
    if (label) label.textContent = data.cta_label || "Presensi";

    if (feedback && !cta.dataset.locked) {
      feedback.textContent = data.reason || "";
      feedback.dataset.tone = "";
    }
    const prediction = document.getElementById("attendance-prediction");
    if (prediction) {
      prediction.hidden = !data.predicted_status;
      if (!data.predicted_status) prediction.textContent = "";
    }

    const schedule = data.schedule;
    const scheduleMessage = document.getElementById("attendance-schedule-message");
    const scheduleTimes = document.getElementById("attendance-schedule-times");
    if (schedule) {
      document.querySelectorAll("[data-schedule-time]").forEach((node) => {
        node.textContent = schedule[node.dataset.scheduleTime] || "—";
      });
      if (schedule.is_holiday) {
        if (scheduleMessage) {
          scheduleMessage.hidden = false;
          scheduleMessage.textContent = "Hari libur — tidak ada jadwal presensi.";
        }
        if (scheduleTimes) scheduleTimes.hidden = true;
      } else {
        if (scheduleMessage) scheduleMessage.hidden = true;
        if (scheduleTimes) scheduleTimes.hidden = false;
      }
    } else {
      document.querySelectorAll("[data-schedule-time]").forEach((node) => { node.textContent = "—"; });
      if (scheduleTimes) scheduleTimes.hidden = true;
      if (scheduleMessage) {
        scheduleMessage.hidden = false;
        scheduleMessage.textContent = "Tidak ada jadwal untuk hari ini.";
      }
    }
  }

  async function refreshAttendanceState({ uncertainAction = null } = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(root.dataset.stateUrl, {
        method: "GET", headers: { Accept: "application/json" },
        cache: "no-store", credentials: "same-origin", signal: controller.signal,
      });
      if (response.redirected) {
        window.location.assign(response.url);
        return { ok: false, confirmed: false };
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) return { ok: false, confirmed: false };
      if (uncertainAction === "checkin" && data.checkin_time) {
        return { ok: true, confirmed: true, state: data };
      }
      if (uncertainAction === "checkout" && data.checkout_time) {
        return { ok: true, confirmed: true, state: data };
      }
      applyState(data);
      return { ok: true, confirmed: false, state: data };
    } catch {
      return { ok: false, confirmed: false };
    } finally {
      clearTimeout(timeout);
    }
  }

  window.refreshAttendanceState = refreshAttendanceState;
  async function refreshIfIdle() {
    if (document.hidden || !navigator.onLine || (panel && !panel.hidden)
        || cta.dataset.locked === "true") return;
    const result = await refreshAttendanceState();
    if (!result.ok && feedback) {
      feedback.textContent = "Status jaringan belum terkonfirmasi. Gunakan Cek status presensi sebelum memulai tindakan baru.";
      feedback.dataset.tone = "warning";
    }
  }

  const interval = window.setInterval(refreshIfIdle, 30000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshIfIdle();
  });
  window.addEventListener("pageshow", refreshIfIdle);
  window.addEventListener("online", refreshIfIdle);
})();
