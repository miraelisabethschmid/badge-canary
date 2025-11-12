// Mira Service Worker — stale-while-revalidate
const CACHE = 'mira-v1';
const SHELL = [
  './',
  './index.html',
  './auto_sync.js',
  './data/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL);
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    const fetchPromise = fetch(req).then((networkResp) => {
      if (networkResp && networkResp.status === 200 && req.method === 'GET') {
        cache.put(req, networkResp.clone());
      }
      return networkResp;
    }).catch(() => cached);
    return cached || fetchPromise;
  })());
});
