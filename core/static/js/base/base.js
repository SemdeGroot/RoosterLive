const toggleBtn = document.getElementById('navToggle');
const panel = document.getElementById('navPanel');
const overlay = document.getElementById('navOverlay');
const closeBtn = document.getElementById('navClose');

if (toggleBtn && panel && overlay) {
    // Voorkom scrollen van body wanneer menu open is
    const preventScroll = () => { document.body.style.overflow = 'hidden'; };
    const allowScroll = () => { document.body.style.overflow = ''; };

    const open = () => {
        panel.hidden = false;
        overlay.classList.add('active');
        requestAnimationFrame(() => { panel.classList.add('open'); });
        toggleBtn.setAttribute('aria-expanded', 'true');
        toggleBtn.setAttribute('aria-label', 'Sluit navigatie');
        preventScroll();

        // VERWIJDERD: geen auto-focus op eerste link om blauwe outline te voorkomen
        // const firstLink = panel.querySelector('.nav-link');
        // if (firstLink) setTimeout(() => firstLink.focus(), 250);
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

    // Focus trap blijft: (laat staan voor toegankelijkheid)
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

// ---------- Web Push init (alleen mobiel, met modaal) ----------

// VAPID key: eerst uit window.PWA, anders van data-attribute op dit script
const VAPID =
  (window.PWA && window.PWA.VAPID_PUBLIC_KEY) ||
  (document.currentScript && document.currentScript.dataset && document.currentScript.dataset.vapid) ||
  (function(){
    const s = document.querySelector('script[src$="base.js"]');
    return s && s.dataset ? s.dataset.vapid : null;
  })();

(function(){
  if (!('serviceWorker' in navigator) || !('Notification' in window)) return;

  // Basis platform-detectie
  const ua = navigator.userAgent || "";
  const isIOS = /iPad|iPhone|iPod/.test(ua);
  const isAndroid = /Android/.test(ua);
  const isMobileUA = /Android|iPhone|iPad|iPod/i.test(ua);
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true; // iOS legacy
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';
  const pushSupported = 'PushManager' in window;

  // Elements voor modaal
  const modal   = document.getElementById('pushPrompt');
  const btnAllow = document.getElementById('pushAllowBtn');
  const btnDecl  = document.getElementById('pushDeclineBtn');
  const btnCloseX= document.getElementById('pushCloseX');
  const titleEl  = document.getElementById('pushTitle');
  const textEl   = document.getElementById('pushText');

  // Helpers (uit jouw bestaande code)
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

  // ✅ Show logic: alleen tonen als push écht kan én zinvol is
  function canOfferPush() {
    if (!modal || !btnAllow || !btnDecl) return false;
    if (!VAPID) return false;                   // zonder VAPID geen aanbod
    if (!onHttps) return false;                 // push vereist HTTPS
    if (!pushSupported) return false;           // Push API nodig
    if (Notification.permission === 'granted') return false; // al ingesteld
    if (Notification.permission === 'denied') return false;  // gebruiker blokkeerde
    if (localStorage.getItem('pushDismissed') === '1') return false; // eerder weggeklikt

    // ❌ Desktop overslaan (alleen mobiel)
    if (!isMobileUA) return false;

    // iOS: alleen aanbieden als PWA/standalone (iOS 16.4+)
    if (isIOS) return isStandalone;

    // Android: mobiel + pushSupported is voldoende
    if (isAndroid) return true;

    // Overig mobiel (zeldzaam): conservatief uit
    return false;
  }

  function openModal() {
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    // kleine UX-tweak: focus op primaire knop
    requestAnimationFrame(() => btnAllow && btnAllow.focus());
  }

  function closeModal() {
    modal.setAttribute('aria-hidden', 'true');
    // verberg na animatie; hier simpel direct:
    modal.hidden = true;
  }

  async function subscribeFlow() {
    if (!VAPID) { alert('VAPID sleutel ontbreekt.'); return; }
    if (!onHttps) { alert('Notificaties vereisen HTTPS.'); return; }

    // iOS guard (zou met canOfferPush niet nodig hoeven zijn, maar dubbel is oké)
    if (isIOS && !isStandalone) {
      alert('Installeer deze app op je beginscherm om notificaties te ontvangen:\n\nDeel ▸ Zet op beginscherm\n\nOpen daarna de app vanaf je beginscherm en probeer opnieuw.');
      return;
    }

    const reg = await registerSW();
    if (!reg) return;

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      localStorage.setItem('pushDismissed', '1');
      closeModal();
      return;
    }

    const existing = await reg.pushManager.getSubscription();
    const sub = existing || await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: b64ToUint8Array(VAPID),
    });
    await saveSubscription(sub);

    localStorage.setItem('pushDismissed', '1');
    closeModal();
  }

  function declineFlow() {
    localStorage.setItem('pushDismissed', '1');
    closeModal();
  }

  function showPromptIfEligible() {
    if (!canOfferPush()) return;

    // Contextuele tekst
    if (!onHttps) {
      textEl && (textEl.textContent = 'Open deze app via HTTPS om notificaties te kunnen inschakelen.');
    } else if (isIOS && !isStandalone) {
      textEl && (textEl.textContent = 'Installeer de app op je beginscherm om notificaties te ontvangen.');
    } else {
      textEl && (textEl.textContent = 'Wil je een melding krijgen als er een nieuw rooster is?');
    }

    openModal();
  }

  // Wire up
  if (btnAllow)  btnAllow.onclick  = subscribeFlow;
  if (btnDecl)   btnDecl.onclick   = declineFlow;
  if (btnCloseX) btnCloseX.onclick = declineFlow;
  // backdrop klik sluit ook
  const backdrop = modal ? modal.querySelector('.push-backdrop') : null;
  if (backdrop)  backdrop.addEventListener('click', declineFlow);

  // ESC sluit
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && !modal.hidden) declineFlow();
  });

  // Init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showPromptIfEligible);
  } else {
    showPromptIfEligible();
  }

  // Debug in console
  window.__pushDebug = {
    isIOS, isAndroid, isMobileUA, isStandalone, onHttps,
    pushSupported, perm: Notification.permission
  };
})();