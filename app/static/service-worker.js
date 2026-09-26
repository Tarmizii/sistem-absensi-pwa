/* Cache only public static shell files. Private navigation, APIs, images, and attendance POSTs stay online-only. */
const CACHE_PREFIX = "presensi-shell-";
const CACHE_NAME = `${CACHE_PREFIX}v8`;
const OFFLINE_URL = "/static/offline.html";
const PRECACHE_URLS = [
  "/static/css/app.css",
  "/static/js/pwa-register.js",
  "/static/manifest.webmanifest",
  "/static/fonts/plus-jakarta-sans-variable.ttf",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/illustrations/welcome-v2.webp",
  "/static/illustrations/school-day-v2.webp",
  "/static/illustrations/teacher-welcome-v2.webp",
  "/static/illustrations/admin-welcome-v2.webp",
  "/static/illustrations/attendance-v2.webp",
  "/static/illustrations/enrollment-v2.webp",
  "/static/illustrations/success-v2.webp",
  "/static/illustrations/location.svg",
  "/static/illustrations/empty.svg",
  OFFLINE_URL,
];
const CACHEABLE_ASSETS = new Set(PRECACHE_URLS);

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(PRECACHE_URLS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.map((name) => (
      name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME ? caches.delete(name) : undefined
    )));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        return await fetch(request);
      } catch (_error) {
        return await caches.match(OFFLINE_URL) || new Response(
          "Anda sedang offline. Sambungkan kembali internet lalu muat ulang.",
          { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } },
        );
      }
    })());
    return;
  }

  if (!CACHEABLE_ASSETS.has(url.pathname) || url.search) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok && response.type === "basic" && !response.headers.has("set-cookie")) {
      await cache.put(request, response.clone());
    }
    return response;
  })());
});
