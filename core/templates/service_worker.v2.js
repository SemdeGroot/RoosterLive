// Alleen voor optionele offline fallback
const CACHE_NAME = 'apo-jansen-offline-v1';
const OFFLINE_URL = '/static/pwa/offline.html';

// (Optioneel) volledige cleanup van SW + alle caches via message
async function fullServiceWorkerCleanup() {
  // Alle caches voor deze origin weggooien
  const cacheKeys = await caches.keys();
  await Promise.all(cacheKeys.map((key) => caches.delete(key)));

  // Service worker zelf unregisteren
  const unregistered = await self.registration.unregister();
  console.log('[sw] unregister resultaat:', unregistered);

  // Alle open tabs opnieuw laden zodat de oude controller verdwijnt
  const clientList = await self.clients.matchAll({
    type: 'window',
    includeUncontrolled: true,
  });

  for (const client of clientList) {
    client.navigate(client.url);
  }
}

// Luister naar message vanaf de pagina (voor handmatige cleanup)
self.addEventListener('message', (event) => {
  if (!event.data || !event.data.type) return;
  if (event.data.type === 'FULL_SW_CLEANUP') {
    console.log('[sw] FULL_SW_CLEANUP ontvangen');
    event.waitUntil(fullServiceWorkerCleanup());
  }
});

// INSTALL: direct activeren en alleen offline.html cachen (indien gewenst)
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      try {
        const cache = await caches.open(CACHE_NAME);
        await cache.addAll([OFFLINE_URL]);
        console.log('[sw] offline pagina gecachet');
      } catch (e) {
        // Als offline.html niet bestaat, is dat ook prima
        console.warn('[sw] kon offline.html niet cachen, ga verder zonder offline fallback', e);
      }
      self.skipWaiting();
    })()
  );
});

// ACTIVATE: oude caches opruimen + clients claimen
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
      console.log('[sw] geactiveerd, oude caches verwijderd (alleen offline cache blijft)');
    })()
  );
});

// FETCH: GEEN caching meer, alleen optionele offline fallback bij navigatie
self.addEventListener('fetch', (event) => {
  // Alleen GET-requests interessant
  if (event.request.method !== 'GET') return;

  // Laat alle niet-navigatie requests gewoon door de browser afhandelen
  if (event.request.mode !== 'navigate') {
    return;
  }

  // Voor navigaties: probeer netwerk, zo niet → offline.html als fallback
  event.respondWith(
    (async () => {
      try {
        // Gewoon rechtstreeks netwerk, geen cache
        return await fetch(event.request);
      } catch (e) {
        // Netwerk faalt (offline?): probeer offline.html
        const cache = await caches.open(CACHE_NAME);
        const offlineResponse = await cache.match(OFFLINE_URL);
        if (offlineResponse) {
          return offlineResponse;
        }
        // Als er geen offline.html is, gooi de originele fout door
        throw e;
      }
    })()
  );
});

// PUSH
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
