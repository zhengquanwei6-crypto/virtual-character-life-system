const CACHE_NAME = "virtual-character-life-system-v0.2.0";
const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./admin.html",
  "./src/styles.css",
  "./src/api.js",
  "./src/app.js",
  "./src/admin.js",
  "./manifest.webmanifest",
  "./assets/icon.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/generated/")) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});

