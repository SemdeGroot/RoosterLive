/* {% load static %} */
const CACHE_NAME = 'app-static-v3';

const APP_SHELL = [
  '/',  // homepage / shell
  "{% static 'css/base/base.css' %}",
  "{% static 'js/base/base.js' %}",
  "{% static 'pwa/offline.html' %}",
];

// Install: cache basisbestanden
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// Activate: oude caches opruimen
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : null)))
    )
  );
  self.clients.claim();
});

// Fetch strategie
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const accept = req.headers.get('accept') || '';
  const isHTML = accept.includes('text/html');

  if (isHTML) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      }).catch(() =>
        caches.match(req).then((cached) => cached || caches.match("{% static 'pwa/offline.html' %}"))
      )
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((cached) =>
      cached ||
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      })
    )
  );
});

// Push event
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch(e) {}
  const title = data.title || 'Update';
  const body  = data.body || 'Er is een update beschikbaar.';
  const url   = data.url  || '/';
  const tag   = data.tag  || 'update';

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      badge: "{% static 'pwa/icons/android-chrome-192x192.png' %}",
      icon: "{% static 'pwa/icons/android-chrome-192x192.png' %}",
      data: { url },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url ? event.notification.data.url : '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if ('focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(targetUrl);
    })
  );
});