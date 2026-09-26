(() => {
  const banner = document.getElementById("network-status");
  const message = document.getElementById("network-status-message");
  const reload = document.getElementById("network-reload");

  const installBanner = document.getElementById("pwa-install-banner");
  const installAction = document.getElementById("pwa-install-action");
  const installDismiss = document.getElementById("pwa-install-dismiss");
  const updateToast = document.getElementById("pwa-update-toast");
  const updateAction = document.getElementById("pwa-update-action");

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

  // Camera pages must not have their layout shifted by an extra surface.
  const cameraActive = () => Boolean(
    document.getElementById("enrollment-video") || document.getElementById("attendance-video"),
  );

  // Install and update affordances are reserved for the student mobile shell.
  const isStudentShell = document.body.classList.contains("student-shell");
  if (!isStudentShell) return;

  let deferredInstallPrompt = null;
  const INSTALL_DISMISS_KEY = "presensi:install-dismissed";

  function closeInstallBanner() {
    if (installBanner) installBanner.hidden = true;
  }

  function openInstallBanner() {
    if (!installBanner || cameraActive()) return;
    installBanner.hidden = false;
  }

  if (installDismiss) {
    installDismiss.addEventListener("click", () => {
      try {
        window.localStorage.setItem(INSTALL_DISMISS_KEY, "1");
      } catch (_error) {
        /* private mode: dismissal simply does not persist */
      }
      closeInstallBanner();
    });
  }

  if (installAction) {
    installAction.addEventListener("click", async () => {
      if (!deferredInstallPrompt) {
        closeInstallBanner();
        return;
      }
      installAction.disabled = true;
      deferredInstallPrompt.prompt();
      try {
        await deferredInstallPrompt.userChoice;
      } catch (_error) {
        /* dismissal is a valid outcome */
      }
      deferredInstallPrompt = null;
      closeInstallBanner();
    });
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    let dismissed = false;
    try {
      dismissed = window.localStorage.getItem(INSTALL_DISMISS_KEY) === "1";
    } catch (_error) {
      dismissed = false;
    }
    if (!dismissed) openInstallBanner();
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    closeInstallBanner();
  });

  if (updateAction) {
    updateAction.addEventListener("click", () => window.location.reload());
  }

  function showUpdateToast(registration) {
    if (!updateToast || !registration || cameraActive()) return;
    updateToast.hidden = false;
    updateAction.addEventListener("click", () => {
      if (registration.waiting) registration.waiting.postMessage({ type: "SKIP_WAITING" });
      window.location.reload();
    }, { once: true });
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register("/service-worker.js", { scope: "/" })
      .then((registration) => {
        if (registration.waiting && navigator.serviceWorker.controller) {
          showUpdateToast(registration);
        }
        registration.addEventListener("updatefound", () => {
          const installing = registration.installing;
          if (!installing) return;
          installing.addEventListener("statechange", () => {
            if (installing.state === "installed" && navigator.serviceWorker.controller) {
              showUpdateToast(registration);
            }
          });
        });
      })
      .catch((error) => {
        console.warn("[pwa] service worker registration failed", error);
        if (installBanner && cameraActive()) return;
        if (installBanner && !installBanner.hidden) {
          installAction.disabled = true;
        }
      });
  } else {
    console.warn("[pwa] service workers are not supported in this browser");
  }
})();
