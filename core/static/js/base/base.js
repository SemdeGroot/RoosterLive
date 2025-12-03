// ---------- NAV / MOBIEL PANEEL ----------
const toggleBtn = document.getElementById('navToggle');
const panel = document.getElementById('navPanel');
const overlay = document.getElementById('navOverlay');
const closeBtn = document.getElementById('navClose');

if (toggleBtn && panel && overlay) {
  const preventScroll = () => { document.body.style.overflow = 'hidden'; };
  const allowScroll = () => { document.body.style.overflow = ''; };

  const open = () => {
    panel.hidden = false;
    overlay.classList.add('active');
    requestAnimationFrame(() => { panel.classList.add('open'); });
    toggleBtn.setAttribute('aria-expanded', 'true');
    toggleBtn.setAttribute('aria-label', 'Sluit navigatie');
    preventScroll();
  };

  const close = () => {
    panel.classList.remove('open');
    overlay.classList.remove('active');
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.setAttribute('aria-label', 'Open navigatie');
    allowScroll();
    setTimeout(() => { panel.hidden = true; }, 250);
  };

  const isOpen = () => toggleBtn.getAttribute('aria-expanded') === 'true';

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    isOpen() ? close() : open();
  });

  if (closeBtn) closeBtn.addEventListener('click', close);

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen()) {
      close();
      toggleBtn.focus();
    }
  });

  overlay.addEventListener('click', close);

  document.addEventListener('click', (e) => {
    if (!isOpen()) return;
    if (!panel.contains(e.target) && !toggleBtn.contains(e.target)) close();
  });

  panel.querySelectorAll('.nav-link').forEach(el => {
    el.addEventListener('click', () => { if (isOpen()) close(); });
  });

  const mq = window.matchMedia('(min-width: 901px)');
  mq.addEventListener('change', (e) => { if (e.matches && isOpen()) close(); });

  // Focus trap
  panel.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab' || !isOpen()) return;
    const focusableElements = panel.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    if (!firstElement || !lastElement) return;

    if (e.shiftKey) {
      if (document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
  });
}

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
      const reg = await navigator.serviceWorker.register('/service_worker.v12.js');
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

  // Stabiel device-ID voor server-side dedupe
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

    // Zorg dat de SW écht geregistreerd is
    const reg = await registerSW();
    if (!reg) {
      alert('Service worker kon niet worden geregistreerd. Probeer het later opnieuw.');
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

  // ---- Promise-achtige prompt voor serial use ----
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

      // Contextuele tekst
      const ua = navigator.userAgent || "";
      const isIOS = /iPad|iPhone|iPod/.test(ua);
      const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                        || window.navigator.standalone === true;
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

  // Debug
  window.__pushDebug = {
    onHttps,
    pushSupported,
    perm: Notification.permission
  };
})();

// ---------- ONBOARDING ORCHESTRATOR: alleen PUSH ----------
(function () {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;

  // Toon push-prompt precies één keer bij eerste PWA-open
  const done = localStorage.getItem('onboardingPushDone') === '1';
  if (!isStandalone || done) return;

  (async () => {
    if (typeof window.offerPushPrompt === 'function') {
      try { await window.offerPushPrompt(); } catch {}
    }
    try { localStorage.setItem('onboardingPushDone', '1'); } catch {}
  })();
})();

// ---------- SERVICE WORKER REGISTRATIE + CLEANUP VIA ?cleanup=1 ----------

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    (async () => {
      try {
        // 1) Normaal gewoon registreren
        const reg = await navigator.serviceWorker.register('/service_worker.v12.js');
        console.log('[sw] Geregistreerd met scope:', reg.scope);

        // 2) Optioneel: cleanup-truc via ?cleanup=1
        const url = new URL(window.location.href);
        const shouldCleanup = url.searchParams.get('sw_cleanup') === '1';

        if (shouldCleanup) {
          console.log('[sw] cleanup=1 in URL → FULL_SW_CLEANUP message sturen');

          const readyReg = await navigator.serviceWorker.ready;
          if (readyReg.active) {
            readyReg.active.postMessage({ type: 'FULL_SW_CLEANUP' });
          }

          // query-param uit de URL halen en pagina opnieuw laden
          url.searchParams.delete('sw_cleanup');
          window.location.replace(url.toString());
        }
      } catch (err) {
        console.warn('[sw] Fout bij registratie / cleanup flow:', err);
      }
    })();
  });
}