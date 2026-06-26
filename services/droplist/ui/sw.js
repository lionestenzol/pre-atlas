/* DropList service worker (Task C — PWA install).
 *
 * Offline-shell, cache-first for the two HTML shells + icons + manifest;
 * network-only for /api/* (live engine state must never be served stale).
 * Hand-rolled rather than Workbox: this is a no-build pure-Python service, so a
 * ~40-line static-precache SW is the right tool — Workbox would drag in an npm
 * build step without making a 2-page precache any better.
 * See ~/.claude/rules/common/assemble-first.md (worse-vs-later discriminator).
 */
const CACHE = 'droplist-shell-v1';
const SHELL = [
  '/',
  '/chain',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never cache writes
  const url = new URL(req.url);
  // Live data is never served from cache.
  if (url.pathname.startsWith('/api/')) return;
  // Cache-first for same-origin shell; fall back to network and warm the cache.
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match('/'))),
    );
  }
});
