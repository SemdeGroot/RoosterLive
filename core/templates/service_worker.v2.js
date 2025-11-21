/* {% load static %} */

// Bewust: geen APP_SHELL en geen echte caching meer.
const CACHE_NAME = 'app-no-cache-v1';

// Install: direct activeren, geen cache-opbouw
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

// Activate: alle oude caches opruimen (ook eerdere versies)
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: ALTIJD direct naar het netwerk, geen cache-first / network-first gedoe
self.addEventListener('fetch', (event) => {
  // Alleen GET-requests behandelen; POST/PUT/etc. gewoon laten lopen
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .catch(() => {
        // Optioneel: als je een echte offline.html wilt, kun je hier nog
        // een fallback doen, maar dan moet je die wél eerst cachen.
        // Voor nu: bij offline gewoon de browser z’n eigen foutpagina laten zien.
        return fetch(event.request);
      })
  );
});

// Push event – ongewijzigd, alleen geen invloed op caching
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {}

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
  const targetUrl =
    event.notification.data && event.notification.data.url
      ? event.notification.data.url
      : '/';

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if ('focus' in client) return client.focus();
        }
        if (clients.openWindow) return clients.openWindow(targetUrl);
      })
  );
});