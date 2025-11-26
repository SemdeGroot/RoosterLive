// Alleen voor optionele offline fallback + statische assets
const CACHE_NAME = 'apo-jansen-static-v1';
const OFFLINE_URL = '/static/pwa/offline.v2.html'; // of: '/static/pwa/offline.html'

// Niet static en media cachen in dev. irritant met development
const DEV_HOSTNAMES = [
  'localhost',
  '127.0.0.1',
  'treasonably-noncerebral-samir.ngrok-free.dev',
];

const IS_DEV = DEV_HOSTNAMES.includes(self.location.hostname);

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
        console.warn(
          '[sw] kon offline fallback niet cachen, ga verder zonder offline fallback',
          e
        );
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
      console.log(
        '[sw] geactiveerd, oude caches verwijderd (alleen statische cache blijft)'
      );
    })()
  );
});

// Helper: alleen /static en /media van EIGEN origin cachen
function isCachableStaticOrMedia(request) {
  const url = new URL(request.url);

  // Alleen zelfde origin (geen externe CDNs / 3rd-party)
  if (url.origin !== self.location.origin) {
    return false;
  }

  // Alleen paden die met /static/ of /media/ beginnen
  return (
    url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')
  );
}

// Helper: alleen /static en /media van EIGEN origin cachen (alleen in PROD)
function isCachableStaticOrMedia(request) {
  // In dev-omgevingen: nooit static/media cachen
  if (IS_DEV) {
    return false;
  }

  const url = new URL(request.url);

  // Alleen zelfde origin (geen externe CDNs / 3rd-party)
  if (url.origin !== self.location.origin) {
    return false;
  }

  // Alleen paden die met /static/ of /media/ beginnen
  return (
    url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')
  );
}

// Network-first navigatie met offline fallback naar OFFLINE_URL
async function handleNavigationRequest(event) {
  try {
    // Gewoon rechtstreeks netwerk, geen HTML-caching
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
}

// FETCH: VEILIG cachen van /static en /media, plus offline fallback bij navigaties
self.addEventListener('fetch', (event) => {
  // Alleen GET-requests interessant
  if (event.request.method !== 'GET') return;

  const isNavigate = event.request.mode === 'navigate';
  const isStaticOrMedia = isCachableStaticOrMedia(event.request);

  // 1) Statische assets (/static, /media) → cache-first
  if (isStaticOrMedia) {
    event.respondWith(handleStaticOrMediaRequest(event.request));
    return;
  }

  // 2) Navigaties (pagina's) → network-first + offline fallback
  if (isNavigate) {
    event.respondWith(handleNavigationRequest(event));
    return;
  }

  // 3) Alles anders (API-calls, fonts, externe assets) → NIET door ons gemanaged
  // Browser regelt zelf caching; wij blijven er af.
});

// PUSH
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {}

  const title = data.title || 'Apotheek Jansen';
  const body = data.body || 'Er is een update beschikbaar.';
  const url = data.url || '/';

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