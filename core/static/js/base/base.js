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

  const ua = navigator.userAgent || "";
  const isIOS = /iPad|iPhone|iPod/.test(ua);
  const isAndroid = /Android/.test(ua);
  const isMobileUA = /Android|iPhone|iPad|iPod/i.test(ua);
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';
  const pushSupported = 'PushManager' in window;

  const modal   = document.getElementById('pushPrompt');
  const btnAllow = document.getElementById('pushAllowBtn');
  const btnDecl  = document.getElementById('pushDeclineBtn');
  const btnCloseX= document.getElementById('pushCloseX');
  const textEl   = document.getElementById('pushText');

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
      const reg = await navigator.serviceWorker.register('/service_worker.v18.js');
      return (await navigator.serviceWorker.ready) || reg;
    } catch (e) {
      console.warn('[push] SW registratie faalde:', e);
      return null;
    }
  }

  function getCSRF() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function getDeviceHash() {
    const ua = navigator.userAgent || "";
    const platform = navigator.platform || "";
    const vendor = navigator.vendor || "";
    const lang = navigator.language || "";
    const hw = [screen.width, screen.height, screen.colorDepth, navigator.hardwareConcurrency || 0].join('x');
    const touch = navigator.maxTouchPoints || 0;
    const data = [ua, platform, vendor, lang, hw, touch].join('|');

    const enc = new TextEncoder().encode(data);
    const buf = await crypto.subtle.digest('SHA-256', enc);
    const bytes = Array.from(new Uint8Array(buf));
    return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  async function saveSubscription(sub) {
    try {
      const device_hash = await getDeviceHash();
      const ua = navigator.userAgent || "";
      await fetch('/api/push/subscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        credentials: 'same-origin',
        body: JSON.stringify({
          subscription: sub,
          device_hash,
          user_agent: ua,
          replace: true
        }),
      });
      console.log('[push] Subscription succesvol gesynchroniseerd met server');
    } catch (e) {
      console.warn('[push] opslaan subscription faalde:', e);
    }
  }

  function canOfferPush() {
    if (!modal || !btnAllow || !btnDecl) return false;
    if (!VAPID) return false;
    if (!onHttps) return false;
    if (!pushSupported) return false;
    if (Notification.permission === 'granted') return false;
    if (Notification.permission === 'denied') return false;
    if (!isMobileUA) return false;
    if (isIOS) return isStandalone;
    if (isAndroid) return true;
    return false;
  }

  function openPushModal() {
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => btnAllow && btnAllow.focus());
  }
  function closePushModal() {
    modal.setAttribute('aria-hidden', 'true');
    modal.hidden = true;
  }

  async function subscribeFlow() {
    if (!VAPID) { alert('VAPID sleutel ontbreekt.'); return; }
    if (!onHttps) { alert('Notificaties vereisen HTTPS.'); return; }

    const reg = await registerSW();
    if (!reg) {
      alert('Service worker kon niet worden geregistreerd.');
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      closePushModal();
      return;
    }

    const existing = await reg.pushManager.getSubscription();
    const sub = existing || await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: b64ToUint8Array(VAPID),
    });
    await saveSubscription(sub);
    closePushModal();
  }

  function declineFlow() {
    closePushModal();
  }

  window.silentPushSync = async function() {
    if (!VAPID || !onHttps || Notification.permission !== 'granted') return;

    try {
      const reg = await registerSW();
      if (!reg) return;

      const oldSub = await reg.pushManager.getSubscription();
      if (oldSub) {
        console.log('[push] Oude subscription gevonden, verwijderen voor force refresh...');
        await oldSub.unsubscribe();
      }

      const newSub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: b64ToUint8Array(VAPID),
      });

      await saveSubscription(newSub);
      console.log('[push] Force refresh succesvol uitgevoerd.');
    } catch(e) {
      console.warn('[push] silent sync (force refresh) failed', e);
    }
  };

  window.offerPushPrompt = async function () {
    try { if (!canOfferPush()) return; } catch { return; }
    return new Promise((resolve) => {
      const done = () => { closePushModal(); resolve(); };
      const onAllow = () => { Promise.resolve(subscribeFlow()).finally(done); };
      const onDecl  = () => { declineFlow(); done(); };

      btnAllow && (btnAllow.onclick = onAllow);
      btnDecl  && (btnDecl.onclick  = onDecl);
      btnCloseX&& (btnCloseX.onclick= onDecl);
      const backdrop = modal ? modal.querySelector('.push-backdrop') : null;
      if (backdrop) backdrop.addEventListener('click', onDecl, { once:true });
      const esc = (e)=>{ if (e.key === 'Escape') { onDecl(); window.removeEventListener('keydown', esc); } };
      window.addEventListener('keydown', esc);

      if (!onHttps) {
        textEl && (textEl.textContent = 'Open deze app via HTTPS om notificaties te kunnen inschakelen.');
      } else if (isIOS && !isStandalone) {
        textEl && (textEl.textContent = 'Installeer de app op je beginscherm om notificaties te ontvangen.');
      } else {
        textEl && (textEl.textContent = 'Wil je meldingen ontvangen? Zo blijf je direct op de hoogte bij een nieuw rooster, belangrijke updates of andere nieuwtjes.');
      }

      openPushModal();
    });
  };
})();

// ---------- ONBOARDING ORCHESTRATOR: alleen PUSH ----------
(function () {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;

  const doneKey = 'onboardingPushFixed_v3';
  const done = localStorage.getItem(doneKey) === '1';

  if (!isStandalone || done) return;

  (async () => {
    if (Notification.permission === 'granted' && typeof window.silentPushSync === 'function') {
      console.log('[onboarding] Permission granted, force refresh van keys...');
      await window.silentPushSync();
    } else if (typeof window.offerPushPrompt === 'function') {
      try { await window.offerPushPrompt(); } catch {}
    }

    try { localStorage.setItem(doneKey, '1'); } catch {}
  })();
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