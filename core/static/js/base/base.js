// ==========================================
// Herstel Focus na service worker notificatie
// ==========================================
if (navigator.serviceWorker) {
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'restoreFocus') {
            // Wacht een kort moment voordat je de focus instelt
            setTimeout(() => {
                // Zoek het eerste invoerveld en geef de focus
                const inputField = document.querySelector('input, textarea, select');
                if (inputField) {
                    inputField.focus();
                }
            }, 100); // Wacht 100ms voor het opnieuw proberen
        }
    });
}

// ---------- WEB PUSH INIT (mobiel + modaal) ----------
const VAPID =
  (window.PWA && window.PWA.VAPID_PUBLIC_KEY) ||
  (document.currentScript && document.currentScript.dataset && document.currentScript.dataset.vapid) ||
  (function () {
    const s = document.querySelector('script[src$="base.js"]');
    return s && s.dataset ? s.dataset.vapid : null;
  })();

(function () {
  if (!('serviceWorker' in navigator) || !('Notification' in window)) return;

  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  const onHttps =
    location.protocol === 'https:' || location.hostname === 'localhost';

  const modal = document.getElementById('pushPrompt');
  const btnAllow = document.getElementById('pushAllowBtn');
  const btnDecl = document.getElementById('pushDeclineBtn');
  const btnCloseX = document.getElementById('pushCloseX');

  const titleEl = document.getElementById('pushTitle');
  const textEl = document.getElementById('pushText');

  // Bewaar originele modal-teksten/labels zodat we repair-modus netjes kunnen terugzetten
  const ORIGINAL_UI = {
    title: titleEl ? titleEl.textContent : '',
    text: textEl ? textEl.textContent : '',
    allow: btnAllow ? btnAllow.textContent : '',
    decline: btnDecl ? btnDecl.textContent : '',
  };

  function setModalUI({ title, text, allowLabel, declineLabel } = {}) {
    if (titleEl && typeof title === 'string') titleEl.textContent = title;
    if (textEl && typeof text === 'string') textEl.textContent = text;
    if (btnAllow && typeof allowLabel === 'string') btnAllow.textContent = allowLabel;
    if (btnDecl && typeof declineLabel === 'string') btnDecl.textContent = declineLabel;
  }

  function resetModalUI() {
    setModalUI({
      title: ORIGINAL_UI.title,
      text: ORIGINAL_UI.text,
      allowLabel: ORIGINAL_UI.allow,
      declineLabel: ORIGINAL_UI.decline,
    });
  }

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
      // register() is idempotent; we keep it here so silentPushSync can always rely on ready()
      await navigator.serviceWorker.register('/service_worker.v20.js');
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
      navigator.maxTouchPoints || 0,
    ].join('|');
    const enc = new TextEncoder().encode(data);
    const buf = await crypto.subtle.digest('SHA-256', enc);
    return Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }

  async function saveSubscription(sub) {
    try {
      const device_hash = await getDeviceHash();
      await fetch('/api/push/subscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRF(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          subscription: sub,
          device_hash,
          user_agent: navigator.userAgent,
          replace: true,
        }),
      });
      console.log('[push] Sync met server geslaagd');
    } catch (e) {
      console.warn('[push] Sync met server faalde:', e);
    }
  }

  // endpoint + keys bepalen of dit "dezelfde" subscription is (detecteert rotatie)
  function subFingerprint(sub) {
    try {
      const j = sub.toJSON();
      return JSON.stringify({ endpoint: j.endpoint, keys: j.keys });
    } catch (_) {
      return sub && sub.endpoint ? String(sub.endpoint) : '';
    }
  }

  // DE MOTOR: Silent Sync met 24-uurs debounce (fingerprint-aware)
  window.silentPushSync = async function (forceNew = false) {
    if (!VAPID || !onHttps || Notification.permission !== 'granted') return;

    try {
      const reg = await registerSW();
      if (!reg) return;

      const lastSyncKey = 'lastPushSyncTimestamp';
      const lastFpKey = 'lastPushSubFingerprint';
      const needsGestureKey = 'pushNeedsUserGestureFix';

      const lastSync = parseInt(localStorage.getItem(lastSyncKey) || '0', 10);
      const lastFp = localStorage.getItem(lastFpKey) || '';
      const nu = Date.now();
      const eenDag = 24 * 60 * 60 * 1000;

      let sub = await reg.pushManager.getSubscription();

      // Als we een bestaande sub hebben, check of die veranderd is (rotatie)
      if (sub && !forceNew) {
        const fp = subFingerprint(sub);

        // Alleen skippen als: recent gesynct + fingerprint identiek
        if (lastSync && nu - lastSync < eenDag && fp === lastFp) {
          console.debug('[push] Sync overgeslagen: recent + fingerprint gelijk.');
          return;
        }
      }

      // (Her)subscribe als token weg is of geforceerd
      if (!sub || forceNew) {
        console.log('[push] Herstel of nieuwe sub aanvraag...');
        try {
          sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: b64ToUint8Array(VAPID),
          });
          // Als dit lukt, is gesture-fix niet nodig
          localStorage.removeItem(needsGestureKey);
        } catch (err) {
          console.warn('[push] subscribe faalde:', err);

          // Op iOS / sommige browsers kan subscribe zonder click soms niet mogen
          if (err && (err.name === 'NotAllowedError' || err.name === 'SecurityError')) {
            localStorage.setItem(needsGestureKey, '1');
          }
          return; // zonder sub kunnen we niet saven
        }
      }

      // Nu altijd saven als we hier zijn (want óf: nieuw, óf: veranderd, óf: >24u)
      await saveSubscription(sub);

      localStorage.setItem(lastSyncKey, String(nu));
      localStorage.setItem(lastFpKey, subFingerprint(sub));
    } catch (e) {
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

  window.offerPushPrompt = function () {
    if (!modal || Notification.permission !== 'default' || !isStandalone) return;

    // Zorg dat onboarding prompt altijd de originele tekst/labels toont
    resetModalUI();

    btnAllow && (btnAllow.onclick = subscribeFlow);
    btnDecl && (btnDecl.onclick = closePushModal);
    btnCloseX && (btnCloseX.onclick = closePushModal);

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
  };

  // Repair prompt: alleen als permission al granted is, maar subscribe/sync ooit faalde door user-gesture
  window.offerPushRepairPrompt = function () {
    if (!modal || Notification.permission !== 'granted' || !isStandalone) return;

    // Pas tekst aan zodat user begrijpt wat er gebeurt
    setModalUI({
      title: 'Meldingen herstellen?',
      text: 'We hebben gedetecteerd dat meldingen opnieuw gekoppeld moeten worden. Tik op “Herstellen” om dit te fixen.',
      allowLabel: 'Herstellen',
      declineLabel: 'Later',
    });

    btnAllow &&
      (btnAllow.onclick = async () => {
        await window.silentPushSync(true); // forceNew
        localStorage.removeItem('pushNeedsUserGestureFix');
        closePushModal();
      });

    const snooze = () => {
      // Niet blijven zeuren: 30 dagen niet meer tonen
      localStorage.setItem(
        'pushRepairSnoozeUntil',
        String(Date.now() + 30 * 24 * 60 * 60 * 1000)
      );
      closePushModal();
    };

    btnDecl && (btnDecl.onclick = snooze);
    btnCloseX && (btnCloseX.onclick = snooze);

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
  };

  function closePushModal() {
    if (!modal) return;

    // Bij sluiten terug naar default UI, zodat volgende keer onboarding niet “repair” tekst heeft
    resetModalUI();

    modal.setAttribute('aria-hidden', 'true');
    modal.hidden = true;
  }
})();

// ---------- DE SLIMME ORCHESTRATOR ----------
(function () {
  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  let isChecking = false;

  async function runPushHealthCheck() {
    if (!isStandalone || isChecking) return;
    isChecking = true;

    try {
      if (Notification.permission === 'granted') {
        // 1) eerst proberen silent te fixen (incl. rotatie-detectie)
        await window.silentPushSync().catch(() => {});

        // 2) als browser user-gesture nodig bleek te hebben: toon max 1x per 30 dagen repair prompt
        const needs = localStorage.getItem('pushNeedsUserGestureFix') === '1';
        const snoozeUntil = parseInt(
          localStorage.getItem('pushRepairSnoozeUntil') || '0',
          10
        );

        if (needs && Date.now() > snoozeUntil) {
          if (typeof window.offerPushRepairPrompt === 'function') {
            window.offerPushRepairPrompt();
          }
        }
      } else if (Notification.permission === 'default') {
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

// ---------- SERVICE WORKER REGISTRATIE + CLEANUP VIA ?sw_cleanup=1 ----------
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    (async () => {
      try {
        // Probeer bestaande registratie te gebruiken; anders registreren
        const reg = await (async () => {
          const r = await navigator.serviceWorker.getRegistration();
          if (r) return r;
          await navigator.serviceWorker.register('/service_worker.v20.js');
          return await navigator.serviceWorker.getRegistration();
        })();

        if (reg) console.log('[sw] Geregistreerd met scope:', reg.scope);

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