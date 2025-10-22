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
      const reg = await navigator.serviceWorker.register('/service-worker.js');
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

  async function saveSubscription(sub) {
    try {
      await fetch('/api/push/subscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        credentials: 'same-origin',
        body: JSON.stringify({ subscription: sub }),
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
    const reg = await registerSW();
    if (!reg) return;

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
      if (!onHttps) {
        textEl && (textEl.textContent = 'Open deze app via HTTPS om notificaties te kunnen inschakelen.');
      } else if (isIOS && !isStandalone) {
        textEl && (textEl.textContent = 'Installeer de app op je beginscherm om notificaties te ontvangen.');
      } else {
        textEl && (textEl.textContent = 'Wil je een melding krijgen als er een nieuw rooster is?');
      }

      openPushModal();
    });
  };

  // Debug
  window.__pushDebug = {
    isIOS, isAndroid, isMobileUA, isStandalone, onHttps,
    pushSupported, perm: Notification.permission
  };
})();

// ---------- BIOMETRIE (WebAuthn / Passkeys) ----------
(function () {
  const modal    = document.getElementById('bioPrompt');
  const allowBtn = document.getElementById('bioAllowBtn');
  const declineBtn = document.getElementById('bioDeclineBtn');
  const closeX   = document.getElementById('bioCloseX');
  if (!modal || !allowBtn || !declineBtn) return;

  const SEC = window.SECURITY || {};
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';

  async function supported() {
    if (!('PublicKeyCredential' in window) || !window.isSecureContext) return false;
    try {
      return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch { return false; }
  }

  function canOfferBio() {
    if (!SEC.authenticated) return false;          // registreren vereist ingelogd
    if (SEC.has_webauthn) return false;            // al ingesteld? niet meer aanbieden
    if (!isStandalone) return false;
    if (!onHttps) return false;
    return true;
  }

  function openBioModal() { modal.hidden = false; modal.setAttribute('aria-hidden','false'); allowBtn && allowBtn.focus(); }
  function closeBioModal(){ modal.setAttribute('aria-hidden','true'); modal.hidden = true; }

  const b64uToBuf = (b64u) => {
    const s = b64u.replace(/-/g,'+').replace(/_/g,'/');
    const pad = s.length % 4 === 2 ? '==' : s.length % 4 === 3 ? '=' : '';
    const str = atob(s + pad);
    const buf = new ArrayBuffer(str.length);
    const view = new Uint8Array(buf);
    for (let i=0;i<str.length;i++) view[i] = str.charCodeAt(i);
    return buf;
  };
  const bufToB64u = (buf) => {
    const bytes = new Uint8Array(buf);
    let s = ''; for (let i=0;i<bytes.byteLength;i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  };

  async function beginRegistration() {
    const csrf = (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [,''])[1] || '';
    const res = await fetch('/webauthn/register/begin/', {
      method: 'POST',
      headers: { 'Content-Type':'application/json', 'X-CSRFToken': csrf },
      credentials:'same-origin',
      body: '{}'
    });
    if (!res.ok) throw new Error('register/begin faalde');
    const options = await res.json();

    const pubKey = options.publicKey || options;
    pubKey.challenge = b64uToBuf(pubKey.challenge);
    if (pubKey.user && pubKey.user.id) pubKey.user.id = b64uToBuf(pubKey.user.id);
    if (Array.isArray(pubKey.excludeCredentials)) {
      pubKey.excludeCredentials = pubKey.excludeCredentials.map(c => ({ ...c, id: b64uToBuf(c.id) }));
    }

    const cred = await navigator.credentials.create({ publicKey: pubKey });
    const att = cred.response;
    const payload = {
      id: cred.id,
      rawId: bufToB64u(cred.rawId),
      type: cred.type,
      response: {
        clientDataJSON: bufToB64u(att.clientDataJSON),
        attestationObject: bufToB64u(att.attestationObject),
      },
      transports: (att.getTransports ? att.getTransports() : []),
    };

    const fin = await fetch('/webauthn/register/complete/', {
      method: 'POST',
      headers: { 'Content-Type':'application/json', 'X-CSRFToken': csrf },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    });
    if (!fin.ok) throw new Error('register/complete faalde');

    // Succes: markeer passkey en onthoud username
    try {
      localStorage.setItem('passkeyEnabled','1');
      if (SEC && SEC.authenticated && SEC.username) {
        localStorage.setItem('lastUsername', SEC.username);
      }
    } catch {}
    closeBioModal();
  }

  // ---- Promise-achtige prompt voor serial use ----
  window.offerBioPrompt = async function () {
    try { if (!(await supported()) || !canOfferBio()) return; } catch { return; }
    return new Promise((resolve) => {
      const done = () => { closeBioModal(); resolve(); };
      const onAllow = () => { Promise.resolve(beginRegistration()).finally(done); };
      const onDecl  = () => { done(); };

      allowBtn   && (allowBtn.onclick   = onAllow);
      declineBtn && (declineBtn.onclick = onDecl);
      closeX     && (closeX.onclick     = onDecl);
      const backdrop = modal ? modal.querySelector('.push-backdrop') : null;
      if (backdrop) backdrop.addEventListener('click', onDecl, { once:true });
      const esc = (e)=>{ if (e.key === 'Escape') { onDecl(); window.removeEventListener('keydown', esc); } };
      window.addEventListener('keydown', esc);

      openBioModal();
    });
  };
})();

// ---------- ORCHESTRATOR: EERSTE PWA-OPEN (als ingelogd) → EERST BIO, DAN PUSH ----------
(function () {
  const SEC = window.SECURITY || {};
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;

  // Laat prompts precies één keer zien (onboarding)
  const onboardingDone = localStorage.getItem('onboardingDone') === '1';

  // We tonen bij de eerste keer dat de user de PWA opent (standalone) EN al ingelogd is
  if (!isStandalone || !SEC.authenticated || onboardingDone) {
    // Wel username onthouden als die bekend is
    try { if (SEC.username) localStorage.setItem('lastUsername', SEC.username); } catch {}
    return;
  }

  (async () => {
    // 1) eerst biometrie
    if (typeof window.offerBioPrompt === 'function') {
      try { await window.offerBioPrompt(); } catch {}
    }
    // 2) dan push
    if (typeof window.offerPushPrompt === 'function') {
      try { await window.offerPushPrompt(); } catch {}
    }

    // Markeer afgerond: niet nogmaals vragen bij volgende opens/logins
    try { localStorage.setItem('onboardingDone', '1'); } catch {}

    // Onthoud username voor auto-passkey op loginpagina
    try { if (SEC.username) localStorage.setItem('lastUsername', SEC.username); } catch {}
  })();
})();