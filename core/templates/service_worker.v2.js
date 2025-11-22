// Eenvoudige cache-naam
const CACHE_NAME = 'apo-jansen-v1';

// Volledige cleanup van deze service worker + alle caches
async function fullServiceWorkerCleanup() {
  // 1) Alle caches voor deze origin weggooien
  const cacheKeys = await caches.keys();
  await Promise.all(cacheKeys.map((key) => caches.delete(key)));

  // 2) Service worker zelf unregisteren
  const unregistered = await self.registration.unregister();
  console.log('[sw] unregister resultaat:', unregistered);

  // 3) Alle open tabs opnieuw laden zodat de oude controller verdwijnt
  const clientList = await self.clients.matchAll({
    type: 'window',
    includeUncontrolled: true,
  });

  for (const client of clientList) {
    client.navigate(client.url);
  }
}

// Luister naar message vanaf de pagina
self.addEventListener('message', (event) => {
  if (!event.data || !event.data.type) return;
  if (event.data.type === 'FULL_SW_CLEANUP') {
    console.log('[sw] FULL_SW_CLEANUP ontvangen');
    event.waitUntil(fullServiceWorkerCleanup());
  }
});

// Install: direct activeren
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

// Activate: oude caches opruimen + clients claimen
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
      await self.clients.claim();
      console.log('[sw] Geactiveerd met cache:', CACHE_NAME);
    })()
  );
});

// Fetch: simpel cache-first met network-fallback
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // SPECIAL: ?cleanup=1 in de URL → eerst cleanup, dan gewoon doorladen
  if (url.searchParams.get('sw_cleanup') === '1') {
    event.respondWith(
      (async () => {
        console.log('[sw] sw_cleanup=1 gedetecteerd, full cleanup uitvoeren');
        await fullServiceWorkerCleanup();

        // zelfde URL zonder cleanup=1 ophalen
        url.searchParams.delete('sw_cleanup');
        const cleanedRequest = new Request(url.toString(), {
          method: event.request.method,
          headers: event.request.headers,
          mode: event.request.mode,
          credentials: event.request.credentials,
          cache: 'reload',
          redirect: event.request.redirect,
          referrer: event.request.referrer,
          referrerPolicy: event.request.referrerPolicy,
        });

        return fetch(cleanedRequest);
      })()
    );
    return;
  }

  // Normale caching-strategie
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE_NAME);

      // Eerst kijken of hij al in de cache zit
      const cached = await cache.match(event.request);
      if (cached) {
        // Optioneel: stilletjes op de achtergrond updaten
        event.waitUntil(
          fetch(event.request)
            .then((response) => {
              cache.put(event.request, response.clone());
            })
            .catch(() => {})
        );
        return cached;
      }

      // Niet in cache → netwerk proberen en dan cachen
      try {
        const response = await fetch(event.request);
        if (response && response.status === 200 && response.type === 'basic') {
          cache.put(event.request, response.clone());
        }
        return response;
      } catch (e) {
        // Geen netwerk en geen cache → browser fallback (offline error)
        throw e;
      }
    })()
  );
});

// Push
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {}

  const title = data.title || 'Apotheek Jansen';
  const body  = data.body || 'Er is een update beschikbaar.';
  const url   = data.url  || '/';

  const options = {
    body,
    icon: NOTIF_ICON,
    badge: NOTIF_BADGE,
    data: { url },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Klik op notificatie
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