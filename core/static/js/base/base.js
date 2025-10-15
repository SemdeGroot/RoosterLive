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

// ---------- Web Push init (iOS/Android/Desktop) ----------

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

  const VAPID = (window.PWA && window.PWA.VAPID_PUBLIC_KEY) || null;
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true; // iOS legacy
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';

  const banner   = document.getElementById('pushBanner');
  const btnAllow = document.getElementById('enablePushBtn');
  const btnNope  = document.getElementById('declinePushBtn');
  const txt      = document.getElementById('pushBannerText');

  // Zorg dat banner altijd klikbaar is (boven overlays)
  if (banner) { banner.style.position = 'relative'; banner.style.zIndex = 1101; }

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

  async function subscribeFlow() {
    if (!VAPID) { alert('VAPID sleutel ontbreekt.'); return; }
    if (!onHttps) { alert('Notificaties vereisen HTTPS.'); return; }
    if (isIOS && !isStandalone) {
      alert('Installeer deze app op je beginscherm om notificaties te kunnen ontvangen:\n\nDeel ▸ Zet op beginscherm\n\nOpen daarna de app vanaf je beginscherm en probeer opnieuw.');
      return;
    }

    const reg = await registerSW();
    if (!reg) return;

    // User-gesture pad → nu mag iOS vragen
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      // Gebruiker weigerde → banner weg & opslaan keuze
      localStorage.setItem('pushDismissed', '1');
      if (banner) banner.style.display = 'none';
      return;
    }

    const existing = await reg.pushManager.getSubscription();
    const sub = existing || await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: b64ToUint8Array(VAPID),
    });
    await saveSubscription(sub);

    localStorage.setItem('pushDismissed', '1'); // niet opnieuw vragen
    if (banner) banner.style.display = 'none';
  }

  function declineFlow() {
    localStorage.setItem('pushDismissed', '1'); // respecteer: niet nu
    if (banner) banner.style.display = 'none';
  }

  function showBannerIfNeeded() {
    if (!banner || !btnAllow || !btnNope) return;

    // Als al ingesteld of bewust weggeklikt → geen banner
    if (localStorage.getItem('pushDismissed') === '1') {
      banner.style.display = 'none';
      return;
    }

    if (Notification.permission === 'granted') {
      banner.style.display = 'none';
      return;
    }

    // Toon banner met correcte tekst per situatie
    banner.style.display = 'block';
    if (!onHttps) {
      txt.textContent = 'Open deze app via HTTPS om notificaties te kunnen inschakelen.';
    } else if (isIOS && !isStandalone) {
      txt.textContent = 'Installeer de app op je beginscherm om notificaties te ontvangen.';
    } else if (Notification.permission === 'denied') {
      txt.textContent = 'Meldingen zijn geblokkeerd. Schakel ze in via Instellingen → Meldingen → “Jansen Portaal”.';
    } else {
      txt.textContent = 'Wil je een melding krijgen als er een nieuw rooster is?';
    }

    btnAllow.onclick = subscribeFlow;
    btnNope.onclick  = declineFlow;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showBannerIfNeeded);
  } else {
    showBannerIfNeeded();
  }

  // Handig in console:
  window.__pushDebug = {
    isIOS, isStandalone, onHttps,
    perm: Notification.permission
  };
})();