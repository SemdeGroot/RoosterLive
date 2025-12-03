// === BASIS-CONFIG ===
const CACHE_NAME = 'apo-jansen-static-v7';
const OFFLINE_URL = '/static/pwa/offline.v6.html'; 
const APP_ICON = '/static/img/app_icon_trans-512x512.png';
const NOTIF_ICON = '/static/pwa/icons/android-chrome-192x192.png';
const NOTIF_BADGE = '/static/pwa/icons/android-chrome-192x192.png';

// === DEV-OMGEVINGEN ===
const DEV_HOSTNAMES = [
  'localhost',
  '127.0.0.1',
  'treasonably-noncerebral-samir.ngrok-free.dev',
];

const IS_DEV = DEV_HOSTNAMES.includes(self.location.hostname);

// === FULL CLEANUP HELPER ===
async function fullServiceWorkerCleanup() {
  const cacheKeys = await caches.keys();
  await Promise.all(cacheKeys.map((key) => caches.delete(key)));

  const unregistered = await self.registration.unregister();
  const clientList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });

  for (const client of clientList) {
    client.navigate(client.url);
  }
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'FULL_SW_CLEANUP') {
    event.waitUntil(fullServiceWorkerCleanup());
  }
});

// === INSTALL: offline-pagina + icon cachen ===
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      try {
        const cache = await caches.open(CACHE_NAME);
        await cache.addAll([OFFLINE_URL, APP_ICON]);
      } catch (e) {
        console.warn('[sw] kon offline fallback niet cachen', e);
      }
      self.skipWaiting();
    })()
  );
});

// === ACTIVATE: oude caches opruimen ===
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => {
        if (key !== CACHE_NAME) return caches.delete(key);
      }));
      await self.clients.claim();
    })()
  );
});

// === HELPER: bepalen of request static/media is ===
function isCachableStaticOrMedia(request) {
  if (IS_DEV) return false;

  const url = new URL(request.url);
  return url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/');
}

// === STATIC/MEDIA: cache-first strategie ===
async function handleStaticOrMediaRequest(request) {
  if (IS_DEV) {
    return fetch(request);
  }

  const cache = await caches.open(CACHE_NAME);

  const cached = await cache.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (e) {
    console.warn('[sw] static/media fetch faalde', request.url, e);
    throw e;
  }
}

// === NAVIGATIES: network-first + offline fallback ===
async function handleNavigationRequest(event) {
  try {
    return await fetch(event.request);
  } catch (e) {
    const cache = await caches.open(CACHE_NAME);
    const offlineResponse = await cache.match(OFFLINE_URL);
    if (offlineResponse) {
      return offlineResponse;
    }
    throw e;
  }
}

// === FETCH-LISTENER ===
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const isNavigate = event.request.mode === 'navigate';
  const isStaticOrMedia = isCachableStaticOrMedia(event.request);

  if (isStaticOrMedia) {
    event.respondWith(handleStaticOrMediaRequest(event.request));
    return;
  }

  if (isNavigate) {
    event.respondWith(handleNavigationRequest(event));
    return;
  }
});

// === PUSH-NOTIFICATIES ===
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    console.warn('[sw] push data geen geldige JSON', e);
  }

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

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url ? event.notification.data.url : '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    })
  );
});