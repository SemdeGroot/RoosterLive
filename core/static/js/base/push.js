// =====================================================
// push.js
// - Native push (Capacitor) + Web push (PWA)
// - NO OS prompts before user accepts modal
// - NO native prompts/registration before login
// - Fix: split "user accepted" vs "token synced"
//   so Android default-granted permissions won't auto-mark enabled.
// =====================================================
(function () {
  // -----------------------
  // Helpers
  // -----------------------
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

  function isAuthenticated() {
    // Hard requirement: template zet data-auth="1" op <html> (of <body>)
    const htmlAuth = document.documentElement?.dataset?.auth;
    const bodyAuth = document.body?.dataset?.auth;
    return htmlAuth === '1' || bodyAuth === '1';
  }

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

  function isSafeInternalUrl(url) {
    return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//');
  }

  // ==========================================================
  // NATIVE PUSH (Capacitor)
  // ==========================================================
  const KEY_ACCEPTED = 'nativePushUserAccepted_v1'; // user clicked "Toestaan" in your modal
  const KEY_SYNCED = 'nativePushTokenSynced_v1'; // token successfully synced to backend
  const LEGACY_ENABLED_KEY = 'nativePushEnabled_v1'; // old key (migration only)

  // One-time migration: if legacy key exists, treat it as both accepted+synced (best-effort)
  try {
    if (localStorage.getItem(LEGACY_ENABLED_KEY) === '1') {
      if (localStorage.getItem(KEY_ACCEPTED) !== '1') localStorage.setItem(KEY_ACCEPTED, '1');
      if (localStorage.getItem(KEY_SYNCED) !== '1') localStorage.setItem(KEY_SYNCED, '1');
      // Optional: remove legacy to avoid future confusion
      // localStorage.removeItem(LEGACY_ENABLED_KEY);
    }
  } catch (_) {}

  let nativeListenersBound = false;

  // Local notifications state (for foreground display)
  let localChannelInitPromise = null;
  let localPermAsked = false;
  let localPermOk = false;

  async function initLocalChannelOnce() {
    if (localChannelInitPromise) return localChannelInitPromise;

    localChannelInitPromise = (async () => {
      const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
      if (!LocalNotifications) return false;

      try {
        const Device = window.Capacitor?.Plugins?.Device;
        const info = Device ? await Device.getInfo().catch(() => null) : null;
        const platform = String(info?.platform || '').toLowerCase();

        if (platform === 'android') {
          await LocalNotifications.createChannel({
            id: 'GENERAL_HIGH',
            name: 'General',
            description: 'Algemene meldingen',
            importance: 5,
            visibility: 1,
            sound: 'default',
          }).catch(() => {});
        }
      } catch (_) {}

      return true;
    })();

    return localChannelInitPromise;
  }

  async function syncLocalPermissionState() {
    const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
    if (!LocalNotifications) {
      localPermOk = false;
      return false;
    }

    try {
      if (typeof LocalNotifications.checkPermissions === 'function') {
        const perm = await LocalNotifications.checkPermissions().catch(() => null);
        localPermOk = !!(perm && (perm.display === 'granted' || perm.granted === true));
        return localPermOk;
      }
    } catch (_) {}

    localPermOk = false;
    return false;
  }

  async function requestLocalNotifPermOnce() {
    if (localPermAsked) return localPermOk;
    localPermAsked = true;

    const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
    if (!LocalNotifications) {
      localPermOk = false;
      return false;
    }

    const perm = await LocalNotifications.requestPermissions().catch(() => null);
    localPermOk = !!(perm && (perm.display === 'granted' || perm.granted === true));
    return localPermOk;
  }

  async function showForegroundLocalNotificationFromPush(notif) {
    const LocalNotifications = window.Capacitor?.Plugins?.LocalNotifications;
    if (!LocalNotifications) return;
    //  Foreground local notification ONLY if user accepted modal
    const accepted = localStorage.getItem(KEY_ACCEPTED) === '1';
    if (!accepted) return;

    await initLocalChannelOnce().catch(() => {});
    await syncLocalPermissionState().catch(() => {}); // safe, no prompt

    if (!localPermOk) return;

    const title = notif?.title || 'Melding';
    const body = notif?.body || '';
    const extra = notif?.data || {};
    const fireAt = new Date(Date.now() + 50);

    try {
      await LocalNotifications.schedule({
        notifications: [
          {
            id: Date.now() % 2147483647,
            title,
            body,
            extra,
            schedule: { at: fireAt },
            channelId: 'GENERAL_HIGH',
            sound: 'default',
            smallIcon: 'ic_stat_notification',
          },
        ],
      });
    } catch (_) {}
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

  function bindNativePushListenersOnce() {
    if (!isCapacitorNative() || nativeListenersBound) return;

    const PushNotifications = window.Capacitor?.Plugins?.PushNotifications;
    if (!PushNotifications) return;

    nativeListenersBound = true;

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

        if (platform === 'ios') {
          const fcmToken = await getFcmTokenIfAvailable();
          if (!fcmToken) {
            LOG.warn('[native-push] iOS: geen FCM token (check plist/pods/plugin)');
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

        // Only mark as "synced" (NOT "accepted")
        localStorage.setItem(KEY_SYNCED, '1');
      } catch (e) {
        LOG.warn('[native-push] token sync faalde:', e);
      }
    });

    PushNotifications.addListener('registrationError', (err) => {
      LOG.warn('[native-push] registrationError:', err);
    });

    // Foreground receive -> local notification (no prompt)
    PushNotifications.addListener('pushNotificationReceived', (notif) => {
      showForegroundLocalNotificationFromPush(notif);
    });

    // Tap on native push notification (tray)
    PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
      try {
        const url = action?.notification?.data?.url;
        if (!isSafeInternalUrl(url)) return;

        queueNativeUrl(url);
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
          scheduleConsumeSoon(150);
        } else {
          window.addEventListener('DOMContentLoaded', () => scheduleConsumeSoon(150), { once: true });
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
            window.addEventListener('DOMContentLoaded', () => scheduleConsumeSoon(150), { once: true });
          }
        } catch (_) {}
      });
    }
  }

  async function syncNativePushIfEligible() {
    // No prompt. But ONLY after user accepted.
    if (!isCapacitorNative() || !isAuthenticated()) return;
    const accepted = localStorage.getItem(KEY_ACCEPTED) === '1';
    const active = localStorage.getItem(KEY_SYNCED) === '1';
    if (!accepted && !active) return;

    const PushNotifications = window.Capacitor?.Plugins?.PushNotifications;
    if (!PushNotifications) return;

    try {
      if (typeof PushNotifications.checkPermissions !== 'function') return;

      const perm = await PushNotifications.checkPermissions().catch(() => null);
      const granted = !!(perm && (perm.receive === 'granted' || perm.granted === true));
      if (!granted) return;

      // Only register if we haven't synced the token yet
      if (localStorage.getItem(KEY_SYNCED) !== '1') {
        bindNativePushListenersOnce();
        await initLocalChannelOnce().catch(() => {});
        await syncLocalPermissionState().catch(() => {});
        await PushNotifications.register().catch(() => {});
      }
    } catch (_) {}
  }

  async function nativePushSubscribeAndSync() {
    // Alleen vanuit user gesture (modal accept)
    if (!isCapacitorNative() || !isAuthenticated()) return;

    const PushNotifications = window.Capacitor?.Plugins?.PushNotifications;
    if (!PushNotifications) {
      LOG.warn('[native-push] PushNotifications plugin ontbreekt.');
      return;
    }

    bindNativePushListenersOnce();

    // 1) OS push prompt (ALLEEN na accept)
    let permRes;
    try {
      permRes = await PushNotifications.requestPermissions();
    } catch (e) {
      LOG.warn('[native-push] requestPermissions faalde:', e);
      return;
    }

    const granted = !!(permRes && (permRes.receive === 'granted' || permRes.granted === true));
    if (!granted) return;

    // 2) safe channel init
    await initLocalChannelOnce().catch(() => {});

    // 3) local notif permission (kan prompt triggeren, maar zit in dezelfde accept-flow)
    await requestLocalNotifPermOnce().catch(() => {});
    await syncLocalPermissionState().catch(() => {});

    // 4) register token
    await PushNotifications.register().catch((e) => {
      LOG.warn('[native-push] register() faalde:', e);
    });
  }

  window.offerNativePushPrompt = function () {
    // NIET vóór login
    if (!isCapacitorNative() || !isAuthenticated()) return;

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
      text: 'Wil je meldingen krijgen over nieuwe roosters en andere updates?',
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
          // Store user consent immediately
          localStorage.setItem(KEY_ACCEPTED, '1');
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

    // Safe: bind listeners + route consume (no prompts)
    bindNativePushListenersOnce();
    consumePendingNativeUrl();

    // Safe: local channel + permission sync (no prompts)
    initLocalChannelOnce().catch(() => {});
    syncLocalPermissionState().catch(() => {});

    // Hard gate: no modal / no registration before login
    if (!isAuthenticated()) return;

    // If user previously accepted and OS permission already granted, silently register/sync token (no prompt)
    syncNativePushIfEligible().catch(() => {});

    // Show modal based on user acceptance (not token synced)
    const accepted = localStorage.getItem(KEY_ACCEPTED) === '1';
    if (!accepted && typeof window.offerNativePushPrompt === 'function') {
      window.offerNativePushPrompt();
    }
  }

  // Start native checks
  if (document.readyState === 'complete' || document.readyState === 'interactive') runNativeCheck();
  else window.addEventListener('DOMContentLoaded', runNativeCheck, { once: true });

  window.addEventListener('pageshow', () => setTimeout(runNativeCheck, 150));

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      setTimeout(runNativeCheck, 500);
    }
  });

  // ==========================================================
  // WEB PUSH (PWA) – unchanged logic, still uses same modal
  // ==========================================================
  const VAPID =
    (window.PWA && window.PWA.VAPID_PUBLIC_KEY) ||
    (document.currentScript && document.currentScript.dataset && document.currentScript.dataset.vapid) ||
    (function () {
      const s = document.querySelector('script[src$="push.js"]');
      return s && s.dataset ? s.dataset.vapid : null;
    })();

  (function webPushInit() {
    if (isCapacitorNative()) return;
    if (!('serviceWorker' in navigator) || !('Notification' in window)) return;

    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true;

    function isProbablyMobile() {
      if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
        return navigator.userAgentData.mobile;
      }
      return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    }

    function isDesktopPwaStandalone() {
      return isStandalone && !isProbablyMobile();
    }

    const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';

    const { modal, btnAllow, btnDecl, btnCloseX, titleEl, textEl } = getModalEls();

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

    function closePushModal() {
      if (!modal) return;
      resetModalUI();
      modal.setAttribute('aria-hidden', 'true');
      modal.hidden = true;
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

    function isAuthenticatedWeb() {
      const htmlAuth = document.documentElement?.dataset?.auth;
      const bodyAuth = document.body?.dataset?.auth;
      return htmlAuth === '1' || bodyAuth === '1';
    }

    window.pushSyncOnLogin = async function () {
      if (!VAPID || !onHttps) return;
      if (Notification.permission !== 'granted') return;

      try {
        const reg = await registerSW();
        if (!reg) return;

        // Alleen lezen: géén subscribe() hier
        const sub = await reg.pushManager.getSubscription();
        if (!sub) return;

        const fp = subFingerprint(sub);

        const lastFpKey = 'lastPushSubFingerprint';
        const lastLoginSyncKey = 'lastPushLoginSyncTimestamp';

        const lastFp = localStorage.getItem(lastFpKey) || '';
        const lastLoginSync = parseInt(localStorage.getItem(lastLoginSyncKey) || '0', 10);

        // Anti-dubbel-run bij login redirects (1 minuut)
        if (Date.now() - lastLoginSync < 60 * 1000 && fp === lastFp) return;

        // Alleen naar backend als fingerprint nieuw/anders is
        if (!lastFp || fp !== lastFp) {
          await saveSubscription(sub);
          localStorage.setItem(lastFpKey, fp);
        }

        localStorage.setItem(lastLoginSyncKey, String(Date.now()));
      } catch (e) {
        console.warn('[push] pushSyncOnLogin faalde:', e);
      }
    };

    async function runLoginPushSyncOncePerSession() {
      if (!isStandalone) return;
      if (!isAuthenticatedWeb()) return;
      if (Notification.permission !== 'granted') return;

      const sessionKey = 'pushLoginSyncDoneThisSession_v1';
      try {
        if (sessionStorage.getItem(sessionKey) === '1') return;
      } catch (_) {}

      try {
        await window.pushSyncOnLogin?.();
        try { sessionStorage.setItem(sessionKey, '1'); } catch (_) {}
      } catch (_) {
        // niet flaggen; dan kan hij later in sessie nog een keer proberen
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

    window.offerPushPrompt = function () {
      if (isDesktopPwaStandalone()) return; 
      if (!modal || Notification.permission !== 'default' || !isStandalone) return;

      resetModalUI();

      btnAllow && (btnAllow.onclick = subscribeFlow);
      btnDecl && (btnDecl.onclick = closePushModal);
      btnCloseX && (btnCloseX.onclick = closePushModal);

      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
    };

    window.offerPushRepairPrompt = function () {
      if (isDesktopPwaStandalone()) return;  
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

    // Orchestrator (PWA only)
    let isChecking = false;

    async function runPushHealthCheck() {
      if (isDesktopPwaStandalone()) return;
      if (!isStandalone || isChecking) return;
      isChecking = true;

      try {
        if (Notification.permission === 'granted') {
          await window.silentPushSync().catch(() => {});
          const needs = localStorage.getItem('pushNeedsUserGestureFix') === '1';
          const snoozeUntil = parseInt(localStorage.getItem('pushRepairSnoozeUntil') || '0', 10);

          if (needs && Date.now() > snoozeUntil) {
            if (typeof window.offerPushRepairPrompt === 'function') window.offerPushRepairPrompt();
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

    if (document.readyState === 'complete') runPushHealthCheck();
    else window.addEventListener('load', runPushHealthCheck);

    let visibilityTimeout;
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        clearTimeout(visibilityTimeout);
        visibilityTimeout = setTimeout(runPushHealthCheck, 1000);
      }
    });
    // Login resync: 1x per sessie (per tab)
    window.addEventListener('load', runLoginPushSyncOncePerSession);

    window.addEventListener('pageshow', () => {
      setTimeout(runLoginPushSyncOncePerSession, 150);
    });

  })();
})();
