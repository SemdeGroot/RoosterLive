// ==========================================
// Herstel Focus na service worker notificatie
// ==========================================
if (navigator.serviceWorker) {
  navigator.serviceWorker.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'restoreFocus') {
      setTimeout(() => {
        const inputField = document.querySelector('input, textarea, select');
        if (inputField) inputField.focus();
      }, 100);
    }
  });
}

// ==========================================
// CAPACITOR NATIVE PUSH (PROMPT + REGISTER + SYNC + ROUTING + SINGLE NOTIF)
// - Native push via FCM (Capacitor PushNotifications plugin)
// - Foreground: toon 1 LocalNotification (anders ziet user niks)
// - Background/Closed: OS toont push (geen extra local => geen duplicates)
// - Tap: navigeer naar notification.data.url (alleen interne routes)
// ==========================================
(function () {
  function isCapacitorNative() {
    try {
      return !!(
        window.Capacitor &&
        typeof window.Capacitor.isNativePlatform === 'function' &&
        window.Capacitor.isNativePlatform()
      );
    } catch (_) {
      return false;
    }
  }

  // Minimal logging helper (prod-safe)
  const LOG = {
    warn: (...a) => console.warn(...a),
    error: (...a) => console.error(...a),
    info: () => {},
    debug: () => {},
  };

  function getCSRF() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function getModalEls() {
    const modal = document.getElementById('pushPrompt');
    const btnAllow = document.getElementById('pushAllowBtn');
    const btnDecl = document.getElementById('pushDeclineBtn');
    const btnCloseX = document.getElementById('pushCloseX');
    const titleEl = document.getElementById('pushTitle');
    const textEl = document.getElementById('pushText');
    return { modal, btnAllow, btnDecl, btnCloseX, titleEl, textEl };
  }

  // ---------- ROUTING HELPERS (native) ----------
  function isSafeInternalUrl(url) {
    return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//');
  }

  function queueNativeUrl(url) {
    if (!isSafeInternalUrl(url)) return;
    localStorage.setItem('nativePushPendingUrl_v1', url);
  }

  function consumePendingNativeUrl() {
    try {
      const pending = localStorage.getItem('nativePushPendingUrl_v1');
      if (!isSafeInternalUrl(pending)) {
        localStorage.removeItem('nativePushPendingUrl_v1');
        return;
      }
      localStorage.removeItem('nativePushPendingUrl_v1');

      const current = window.location.pathname + window.location.search;
      if (current !== pending) window.location.assign(pending);
    } catch (_) {}
  }

  function scheduleConsumeSoon(delayMs = 150) {
    setTimeout(consumePendingNativeUrl, delayMs);
  }

  // ---------- SINGLE NOTIF IN FOREGROUND ----------
  // We only show LocalNotification when app is open (foreground receive event).
  // When app is background/closed, OS shows the push itself => no duplicates.
  let localPermChecked = false;
  let localPermOk = false;

  async function ensureLocalNotifPermOnce() {
    if (localPermChecked) return localPermOk;
    localPermChecked = true;

    const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
    if (!LocalNotifications) return (localPermOk = false);

    const perm = await LocalNotifications.requestPermissions().catch(() => null);
    localPermOk = !!(perm && (perm.display === 'granted' || perm.granted === true));
    return localPermOk;
  }

  async function showForegroundLocalNotificationFromPush(notif) {
    try {
      const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
      if (!LocalNotifications) return;

      const ok = await ensureLocalNotifPermOnce();
      if (!ok) return;

      // Push payload komt in notif: { title, body, data: { url, tag, ... } }
      const title = notif?.title || 'Melding';
      const body = notif?.body || '';
      const extra = notif?.data || {};

      await LocalNotifications.schedule({
        notifications: [
          {
            id: Date.now() % 2147483647,
            title,
            body,
            extra,
            schedule: { at: new Date(Date.now() + 50) },
            channelId: 'GENERAL_HIGH',
            sound: 'default',   
          },
        ],
      });
    } catch (_) {}
  }

  async function getFcmTokenIfAvailable() {
  const FCM = window.Capacitor?.Plugins?.FCM; // @capacitor-community/fcm
  if (!FCM) return '';
  try {
    const res = await FCM.getToken();
    return res?.token || '';
  } catch (_) {
    return '';
  }
}

  // ---- FIX: bind listeners ALWAYS at app load (not only after subscribe click) ----
  let nativeListenersBound = false;

  function bindNativePushListenersOnce() {
    if (!isCapacitorNative() || nativeListenersBound) return;

    const PushNotifications = window.Capacitor?.Plugins?.PushNotifications;
    if (!PushNotifications) return;

    nativeListenersBound = true;

    // Token registration -> sync to server
  PushNotifications.addListener('registration', async (token) => {
    try {
      let tokenValue = token?.value || '';
      if (!tokenValue) return;

      const Device = window.Capacitor?.Plugins?.Device;

      let deviceId = '';
      let platform = '';
      try {
        if (Device) {
          const id = await Device.getId().catch(() => null);
          const info = await Device.getInfo().catch(() => null);
          deviceId = id?.identifier ? String(id.identifier) : '';
          platform = info?.platform ? String(info.platform) : '';
        }
      } catch (_) {}

      // iOS: vervang (vaak) APNs token door FCM token
      if (platform === 'ios') {
        const fcmToken = await getFcmTokenIfAvailable();

        if (!fcmToken) {
          LOG.warn('[native-push] iOS: geen FCM token (check GoogleService-Info.plist + pods + plugin)');
          return;
        }

        tokenValue = fcmToken;
      }

      await fetch('/api/push/native/subscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRF(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          token: tokenValue,
          platform,
          device_id: deviceId,
          user_agent: navigator.userAgent,
          replace: true,
        }),
      });

      localStorage.setItem('nativePushEnabled_v1', '1');
    } catch (e) {
      LOG.warn('[native-push] token sync faalde:', e);
    }
  });


    PushNotifications.addListener('registrationError', (err) => {
      LOG.warn('[native-push] registrationError:', err);
    });

    // Foreground receive => show one local notification so user sees it
    PushNotifications.addListener('pushNotificationReceived', async (notif) => {
      // In foreground Android does NOT show OS notification automatically.
      // So we show a LocalNotification (single).
      await showForegroundLocalNotificationFromPush(notif);
    });

    // Tap on native push notification (from tray)
    PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
      try {
        const url = action?.notification?.data?.url;
        if (!isSafeInternalUrl(url)) return;

        // queue and consume after resume
        queueNativeUrl(url);

        if (document.readyState === 'complete' || document.readyState === 'interactive') {
          scheduleConsumeSoon(150);
        } else {
          window.addEventListener(
            'DOMContentLoaded',
            () => scheduleConsumeSoon(150),
            { once: true }
          );
        }
      } catch (_) {}
    });

    // Tap on LocalNotification (foreground-generated)
    const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
    if (LocalNotifications) {
      LocalNotifications.addListener('localNotificationActionPerformed', (event) => {
        try {
          const url = event?.notification?.extra?.url;
          if (!isSafeInternalUrl(url)) return;

          queueNativeUrl(url);
          if (document.readyState === 'complete' || document.readyState === 'interactive') {
            scheduleConsumeSoon(150);
          } else {
            window.addEventListener(
              'DOMContentLoaded',
              () => scheduleConsumeSoon(150),
              { once: true }
            );
          }
        } catch (_) {}
      });
    }
  }

  async function nativePushSubscribeAndSync() {
    if (!isCapacitorNative()) return;

    const PushNotifications = window.Capacitor?.Plugins?.PushNotifications;
    if (!PushNotifications) {
      LOG.warn('[native-push] PushNotifications plugin ontbreekt.');
      return;
    }

    // Ensure listeners are bound BEFORE requesting permission/registering
    bindNativePushListenersOnce();

    let permRes;
    try {
      permRes = await PushNotifications.requestPermissions();
    } catch (e) {
      LOG.warn('[native-push] requestPermissions faalde:', e);
      return;
    }

    const granted = !!(permRes && (permRes.receive === 'granted' || permRes.granted === true));
    if (!granted) return;

    // (Optional) ask LocalNotifications permission once (so foreground can show 1 notif)
    // This is NOT required for background pushes.
    try {
      await ensureLocalNotifPermOnce();
    } catch (_) {}

    try {
      await PushNotifications.register();
    } catch (e) {
      LOG.warn('[native-push] register() faalde:', e);
    }
  }

  // Native prompt (zelfde modal UI, andere handler)
  window.offerNativePushPrompt = function () {
    if (!isCapacitorNative()) return;

    const { modal, btnAllow, btnDecl, btnCloseX, titleEl, textEl } = getModalEls();
    if (!modal) return;

    const doneKey = 'onboardingNativePush_v1';
    if (localStorage.getItem(doneKey) === '1') return;

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

    setModalUI({
      title: 'Meldingen aanzetten?',
      text: 'Zet pushmeldingen aan zodat je updates direct ontvangt, ook als de app gesloten is.',
      allowLabel: 'Toestaan',
      declineLabel: 'Niet nu',
    });

    const close = () => {
      resetModalUI();
      modal.setAttribute('aria-hidden', 'true');
      modal.hidden = true;
    };

    btnAllow &&
      (btnAllow.onclick = async () => {
        try {
          await nativePushSubscribeAndSync();
        } finally {
          localStorage.setItem(doneKey, '1');
          close();
        }
      });

    const decline = () => {
      localStorage.setItem(doneKey, '1');
      close();
    };

    btnDecl && (btnDecl.onclick = decline);
    btnCloseX && (btnCloseX.onclick = decline);

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
  };

  function runNativeCheck() {
    if (!isCapacitorNative()) return;

    // Always bind listeners early so we never miss received/tap events
    bindNativePushListenersOnce();

    // If a pending url exists (tap opened app), consume it
    consumePendingNativeUrl();

    // Prompt once if not enabled
    const enabled = localStorage.getItem('nativePushEnabled_v1') === '1';
    if (!enabled && typeof window.offerNativePushPrompt === 'function') {
      window.offerNativePushPrompt();
    }
  }

  if (document.readyState === 'complete') {
    runNativeCheck();
  } else {
    window.addEventListener('load', runNativeCheck);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      setTimeout(runNativeCheck, 500);
    }
  });
})();

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
    } catch (e) {
      console.warn('[push] Sync met server faalde:', e);
    }
  }

  function subFingerprint(sub) {
    try {
      const j = sub.toJSON();
      return JSON.stringify({ endpoint: j.endpoint, keys: j.keys });
    } catch (_) {
      return sub && sub.endpoint ? String(sub.endpoint) : '';
    }
  }

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

      if (sub && !forceNew) {
        const fp = subFingerprint(sub);
        if (lastSync && nu - lastSync < eenDag && fp === lastFp) return;
      }

      if (!sub || forceNew) {
        try {
          sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: b64ToUint8Array(VAPID),
          });
          localStorage.removeItem(needsGestureKey);
        } catch (err) {
          if (err && (err.name === 'NotAllowedError' || err.name === 'SecurityError')) {
            localStorage.setItem(needsGestureKey, '1');
          }
          return;
        }
      }

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

  // ---- In Capacitor géén webpush prompt/orchestrator (native doet dit) ----
  function isCapacitorNative() {
    try {
      return !!(
        window.Capacitor &&
        typeof window.Capacitor.isNativePlatform === 'function' &&
        window.Capacitor.isNativePlatform()
      );
    } catch (_) {
      return false;
    }
  }

  window.offerPushPrompt = function () {
    if (isCapacitorNative()) return;
    if (!modal || Notification.permission !== 'default' || !isStandalone) return;

    resetModalUI();

    btnAllow && (btnAllow.onclick = subscribeFlow);
    btnDecl && (btnDecl.onclick = closePushModal);
    btnCloseX && (btnCloseX.onclick = closePushModal);

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
  };

  window.offerPushRepairPrompt = function () {
    if (isCapacitorNative()) return;
    if (!modal || Notification.permission !== 'granted' || !isStandalone) return;

    setModalUI({
      title: 'Meldingen herstellen?',
      text: 'We hebben gedetecteerd dat meldingen opnieuw gekoppeld moeten worden. Tik op “Herstellen” om dit te fixen.',
      allowLabel: 'Herstellen',
      declineLabel: 'Later',
    });

    btnAllow &&
      (btnAllow.onclick = async () => {
        await window.silentPushSync(true);
        localStorage.removeItem('pushNeedsUserGestureFix');
        closePushModal();
      });

    const snooze = () => {
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
    resetModalUI();
    modal.setAttribute('aria-hidden', 'true');
    modal.hidden = true;
  }
})();

// ---------- DE SLIMME ORCHESTRATOR (PWA ONLY) ----------
(function () {
  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  const isCapacitorNative = (() => {
    try {
      return !!(
        window.Capacitor &&
        typeof window.Capacitor.isNativePlatform === 'function' &&
        window.Capacitor.isNativePlatform()
      );
    } catch (_) {
      return false;
    }
  })();

  let isChecking = false;

  async function runPushHealthCheck() {
    if (isCapacitorNative) return;
    if (!isStandalone || isChecking) return;
    isChecking = true;

    try {
      if (Notification.permission === 'granted') {
        await window.silentPushSync().catch(() => {});

        const needs = localStorage.getItem('pushNeedsUserGestureFix') === '1';
        const snoozeUntil = parseInt(localStorage.getItem('pushRepairSnoozeUntil') || '0', 10);

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

  if (document.readyState === 'complete') {
    runPushHealthCheck();
  } else {
    window.addEventListener('load', runPushHealthCheck);
  }

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
        const reg = await (async () => {
          const r = await navigator.serviceWorker.getRegistration();
          if (r) return r;
          await navigator.serviceWorker.register('/service_worker.v20.js');
          return await navigator.serviceWorker.getRegistration();
        })();

        const url = new URL(window.location.href);
        const shouldCleanup = url.searchParams.get('sw_cleanup') === '1';

        if (shouldCleanup) {
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