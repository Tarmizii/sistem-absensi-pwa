(() => {
  const banner = document.getElementById("network-status");
  const message = document.getElementById("network-status-message");
  const reload = document.getElementById("network-reload");

  function showOffline() {
    if (!banner || !message || !reload) return;
    banner.hidden = false;
    message.textContent = "Anda sedang offline. Presensi dan data terbaru memerlukan koneksi internet.";
    reload.hidden = true;
  }

  function showOnline() {
    if (!banner || !message || !reload) return;
    banner.hidden = false;
    message.textContent = "Koneksi kembali. Muat ulang untuk memperbarui data.";
    reload.hidden = false;
  }

  if (!navigator.onLine) showOffline();
  window.addEventListener("offline", showOffline);
  window.addEventListener("online", showOnline);
  if (reload) reload.addEventListener("click", () => window.location.reload());

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => {});
  }
})();
