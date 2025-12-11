// === BASIS-CONFIG ===
const CACHE_NAME = 'apo-jansen-static-v12';
const OFFLINE_URL = '/static/pwa/offline.v7.html';
const APP_ICON = '/static/img/app_icon_trans-512x512.png';
const NOTIF_ICON = '/static/pwa/icons/android-chrome-192x192.png';
const NOTIF_BADGE = '/static/pwa/icons/android-chrome-192x192.png';

// === CONFIGURATIE VOOR VERVALDATUM ===
const MAX_AGE_DAYS = 30;
const PURGE_INTERVAL_HOURS = 24; // Hoe vaak checken we op oude bestanden?
const MAX_AGE_MS = MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
const PURGE_INTERVAL_MS = PURGE_INTERVAL_HOURS * 60 * 60 * 1000;

// === DEV-OMGEVINGEN ===
// (Exact overgenomen van jouw origineel)
const DEV_HOSTNAMES = [
  'localhost',
  '127.0.0.1',
  'treasonably-noncerebral-samir.ngrok-free.dev',
];

const IS_DEV = DEV_HOSTNAMES.includes(self.location.hostname);

// ==========================================
// === INDEXEDDB LOGICA (Nieuw: Metadata + Periodic Task) ===
// ==========================================
const DB_NAME = 'sw-metadata-db';
const STORE_NAME = 'access-timestamps';
const META_KEY_LAST_PRUNE = '__SYS_LAST_PRUNE__'; // Speciale key voor laatste check

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 2);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// 1. Update timestamp bij gebruik
async function markUrlAsUsed(url) {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put(Date.now(), url);
  } catch (e) {
    /* Fail silently, niet kritiek */
  }
}

// 2. De daadwerkelijke opruimfunctie
// 2. De daadwerkelijke opruimfunctie (GEREPAREERD)
async function pruneOldCacheEntries() {
  try {
    const db = await openDB();
    
    // FASE 1: LEZEN (Snel, in één keer)
    // We gebruiken een readonly transactie om data op te halen
    const txRead = db.transaction(STORE_NAME, 'readonly');
    const storeRead = txRead.objectStore(STORE_NAME);

    // We halen keys en values op via Promises
    const keys = await new Promise((resolve) => { 
        storeRead.getAllKeys().onsuccess = (e) => resolve(e.target.result); 
    });
    const values = await new Promise((resolve) => { 
        storeRead.getAll().onsuccess = (e) => resolve(e.target.result); 
    });

    // FASE 2: FILTEREN & CACHE VERWIJDEREN (Traag, async)
    // De vorige transactie is nu al gesloten door de browser, dat is prima.
    
    const now = Date.now();
    const urlsToDelete = [];
    
    // Bepaal eerst wat weg moet
    for (let i = 0; i < keys.length; i++) {
      const url = keys[i];
      if (url === META_KEY_LAST_PRUNE) continue; // Sla config over

      const timestamp = values[i];
      if (now - timestamp > MAX_AGE_MS) {
        urlsToDelete.push(url);
      }
    }

    // Update nu de 'Last Prune' tijd (Dit heeft een KORTE nieuwe transactie nodig)
    const txMeta = db.transaction(STORE_NAME, 'readwrite');
    txMeta.objectStore(STORE_NAME).put(Date.now(), META_KEY_LAST_PRUNE);
    // We wachten niet per se op deze, mag fire-and-forget zijn, 
    // of await new Promise(r => txMeta.oncomplete = r); voor netheid.

    if (urlsToDelete.length === 0) return; // Niets te doen

    // Nu pas de trage Cache API aanroepen
    const cache = await caches.open(CACHE_NAME);
    const cacheDeletionPromises = urlsToDelete.map(url => cache.delete(url));
    await Promise.all(cacheDeletionPromises);

    // FASE 3: DATABASE BIJWERKEN (Nieuwe transactie)
    // Nu de bestanden echt weg zijn, schonen we de DB op.
    const txWrite = db.transaction(STORE_NAME, 'readwrite');
    const storeWrite = txWrite.objectStore(STORE_NAME);
    
    urlsToDelete.forEach(url => {
        storeWrite.delete(url);
    });

    await new Promise((resolve) => { txWrite.oncomplete = resolve; });
    
    console.log(`[sw] Cleanup voltooid: ${urlsToDelete.length} bestanden verwijderd.`);

  } catch (e) {
    console.warn('[sw] pruneOldCacheEntries failed', e);
  }
}

// 3. De "Throttle" functie: Draai alleen periodiek
async function checkAndPrunePeriodically() {
  if (IS_DEV) return; // Niet in dev doen
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readonly');
    const req = tx.objectStore(STORE_NAME).get(META_KEY_LAST_PRUNE);
    const lastPrune = await new Promise((res) => { req.onsuccess = () => res(req.result); });

    // Als nooit gedraaid (undefined) of langer geleden dan interval -> Prune
    if (!lastPrune || (Date.now() - lastPrune > PURGE_INTERVAL_MS)) {
      // Roep de cleanup aan (in een nieuwe transactie want deze is readonly)
      await pruneOldCacheEntries();
    }
  } catch (e) {
    console.warn('[sw] Periodic check failed', e);
  }
}

// ==========================================
// === SERVICE WORKER LOGICA ===
// ==========================================

// === FULL CLEANUP HELPER (Jouw originele logica) ===
async function fullServiceWorkerCleanup() {
  const cacheKeys = await caches.keys();
  await Promise.all(cacheKeys.map((key) => caches.delete(key)));
  
  // EXTRA: Ook IDB weggooien bij full cleanup zodat we schoon beginnen
  const req = indexedDB.deleteDatabase(DB_NAME);

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

// === INSTALL ===
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

// === ACTIVATE ===
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => {
        if (key !== CACHE_NAME) return caches.delete(key);
      }));
      // Bij activate doen we altijd één keer een prune check
      await pruneOldCacheEntries();
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

// === STATIC/MEDIA: cache-first strategie (Aangepast met Tracking) ===
async function handleStaticOrMediaRequest(request) {
  if (IS_DEV) {
    return fetch(request);
  }

  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  
  if (cached) {
    // TRACKING: We hebben het bestand gebruikt, update de datum "fire & forget"
    markUrlAsUsed(request.url);
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      cache.put(request, response.clone());
      // TRACKING: Nieuw bestand opgeslagen, datum zetten
      markUrlAsUsed(request.url);
    }
    return response;
  } catch (e) {
    console.warn('[sw] static/media fetch faalde', request.url, e);
    throw e;
  }
}

// === NAVIGATIES (Jouw originele logica) ===
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

// === FETCH-LISTENER (Aangepast met Periodic Trigger) ===
self.addEventListener('fetch', (event) => {
  // PERIODIEKE CHECK AANPASSING:
  // Alleen checken bij navigatie (nieuwe pagina), NIET bij elke API call.
  // Dit voorkomt vertraging tijdens het login-request.
  const isNavigate = event.request.mode === 'navigate';

  if (!IS_DEV && isNavigate) {
    event.waitUntil(checkAndPrunePeriodically());
  }

  if (event.request.method !== 'GET') return;

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

// === PUSH-NOTIFICATIES (Jouw originele logica) ===
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