// ---------- WEB PUSH INIT (mobiel + modaal) ----------
const VAPID =
  (window.PWA && window.PWA.VAPID_PUBLIC_KEY) ||
  (document.currentScript && document.currentScript.dataset && document.currentScript.dataset.vapid) ||
  (function(){
    const s = document.querySelector('script[src$="base.js"]');
    return s && s.dataset ? s.dataset.vapid : null;
  })();

(function(){
  if (!('serviceWorker' in navigator) || !('Notification' in window)) return;

  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';

  const modal   = document.getElementById('pushPrompt');
  const btnAllow = document.getElementById('pushAllowBtn');
  const btnDecl  = document.getElementById('pushDeclineBtn');
  const btnCloseX= document.getElementById('pushCloseX');

  function b64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    const arr = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) arr[i] = rawData.charCodeAt(i);
    return arr;
  }

  async function registerSW() {
    try {
      await navigator.serviceWorker.register('/service_worker.v18.js');
      return await navigator.serviceWorker.ready;
    } catch (e) {
      console.warn('[push] SW ready-check faalde:', e);
      return null;
    }
  }

  function getCSRF() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function getDeviceHash() {
    const data = [
      navigator.userAgent,
      navigator.platform,
      navigator.language,
      [screen.width, screen.height, screen.colorDepth].join('x'),
      navigator.maxTouchPoints || 0
    ].join('|');
    const enc = new TextEncoder().encode(data);
    const buf = await crypto.subtle.digest('SHA-256', enc);
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  async function saveSubscription(sub) {
    try {
      const device_hash = await getDeviceHash();
      await fetch('/api/push/subscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        credentials: 'same-origin',
        body: JSON.stringify({
          subscription: sub,
          device_hash,
          user_agent: navigator.userAgent,
          replace: true
        }),
      });
      console.log('[push] Sync met server geslaagd');
    } catch (e) {
      console.warn('[push] Sync met server faalde:', e);
    }
  }

  // DE MOTOR: Silent Sync met 24-uurs debounce
  window.silentPushSync = async function(forceNew = false) {
    if (!VAPID || !onHttps || Notification.permission !== 'granted') return;

    try {
      const reg = await registerSW();
      if (!reg) return;

      let sub = await reg.pushManager.getSubscription();
      
      const lastSyncKey = 'lastPushSyncTimestamp';
      const lastSync = localStorage.getItem(lastSyncKey);
      const nu = Date.now();
      const eenDag = 24 * 60 * 60 * 1000;

      // Skip POST als alles up-to-date is en recent gesynct
      if (sub && !forceNew && lastSync && (nu - parseInt(lastSync) < eenDag)) {
        console.debug('[push] Sync overgeslagen: recent nog uitgevoerd.');
        return; 
      }

      // Hersubscribe als token weg is (data gewist) of geforceerd
      if (!sub || forceNew) {
        console.log('[push] Herstel of nieuwe sub aanvraag...');
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: b64ToUint8Array(VAPID),
        });
      }
      
      await saveSubscription(sub);
      localStorage.setItem(lastSyncKey, nu.toString());

    } catch(e) {
      console.warn('[push] silentPushSync faalde:', e);
    }
  };

  async function subscribeFlow() {
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      await window.silentPushSync(true);
    }
    closePushModal();
  }

  window.offerPushPrompt = function() {
    if (!modal || Notification.permission !== 'default' || !isStandalone) return;
    btnAllow && (btnAllow.onclick = subscribeFlow);
    btnDecl && (btnDecl.onclick = closePushModal);
    btnCloseX && (btnCloseX.onclick = closePushModal);
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
  };

  function closePushModal() {
    if (!modal) return;
    modal.setAttribute('aria-hidden', 'true');
    modal.hidden = true;
  }
})();

// ---------- DE SLIMME ORCHESTRATOR ----------
(function () {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;

  let isChecking = false;

  async function runPushHealthCheck() {
    if (!isStandalone || isChecking) return;
    isChecking = true;
    try {
      if (Notification.permission === 'granted') {
        // Probeert te syncen; de 24-uurs timer in de functie beslist of het echt nodig is
        await window.silentPushSync().catch(() => {}); 
      } 
      else if (Notification.permission === 'default') {
        const doneKey = 'onboardingPush_v4';
        if (localStorage.getItem(doneKey) !== '1') {
          if (typeof window.offerPushPrompt === 'function') {
            window.offerPushPrompt();
            localStorage.setItem(doneKey, '1');
          }
        }
      }
    } finally {
      isChecking = false;
    }
  }

  // Uitvoeren bij laden
  if (document.readyState === 'complete') {
    runPushHealthCheck();
  } else {
    window.addEventListener('load', runPushHealthCheck);
  }

  // Herstel-check bij app-switch (iOS vriendelijk)
  let visibilityTimeout;
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      clearTimeout(visibilityTimeout);
      visibilityTimeout = setTimeout(runPushHealthCheck, 1000);
    }
  });
})();

// ---------- SERVICE WORKER REGISTRATIE + CLEANUP VIA ?cleanup=1 ----------
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    (async () => {
      try {
        const reg = await navigator.serviceWorker.register('/service_worker.v18.js');
        console.log('[sw] Geregistreerd met scope:', reg.scope);

        const url = new URL(window.location.href);
        const shouldCleanup = url.searchParams.get('sw_cleanup') === '1';

        if (shouldCleanup) {
          console.log('[sw] cleanup=1 in URL → FULL_SW_CLEANUP message sturen');

          const readyReg = await navigator.serviceWorker.ready;
          if (readyReg.active) {
            readyReg.active.postMessage({ type: 'FULL_SW_CLEANUP' });
          }

          url.searchParams.delete('sw_cleanup');
          window.location.replace(url.toString());
        }
      } catch (err) {
        console.warn('[sw] Fout bij registratie / cleanup flow:', err);
      }
    })();
  });
}