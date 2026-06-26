/* DropList service worker (Task C — PWA install).
 *
 * Offline-shell, cache-first for the two HTML shells + icons + manifest;
 * network-only for /api/* (live engine state must never be served stale).
 * Hand-rolled rather than Workbox: this is a no-build pure-Python service, so a
 * ~40-line static-precache SW is the right tool — Workbox would drag in an npm
 * build step without making a 2-page precache any better.
 * See ~/.claude/rules/common/assemble-first.md (worse-vs-later discriminator).
 */
// Bump this on any shell change. The activate handler purges every cache whose name
// != CACHE, so a version bump evicts the stale v1 shell from already-installed PWAs.
const CACHE = 'droplist-shell-v2';
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

// An HTML shell request: a navigation, a document destination, or the two known shell routes.
// These must be network-first so an installed PWA always picks up a fresh build.
function isShell(req, url) {
  return req.mode === 'navigate'
    || req.destination === 'document'
    || url.pathname === '/'
    || url.pathname === '/chain';
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never cache writes
  const url = new URL(req.url);
  // Live data is never served from cache.
  if (url.pathname.startsWith('/api/')) return;
  if (url.origin !== self.location.origin) return;

  // Network-first for HTML shells: try the network, warm the cache, fall back to cache only
  // when offline. Fixes the stale-shell trap where a cache-first HTML never updated.
  // See ~/.claude/rules/common/code-as-furniture.md -- stale-shell fixed, not documented-and-left.
  if (isShell(req, url)) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match('/'))),
    );
    return;
  }

  // Cache-first for immutable assets (icons/manifest); warm the cache on miss.
  event.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match('/'))),
  );
});
