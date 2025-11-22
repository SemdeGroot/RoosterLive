// installprompt.js
// - Android: Progressier-achtige install prompt (modal) met één "Installeer app"-knop.
//   Deze knop triggert Chrome's Richer Install UI (met screenshots/description uit je manifest).
// - iOS: Progressier-achtige install prompt met 4 stappen en OS-iconen.
// - Beide:
//   * Nooit tonen als de app als PWA draait.
//   * Maximaal 1x per sessie via sessionStorage.
//   * Alleen op mobile (iOS/Android), niet op desktop.

(() => {
  const ua = navigator.userAgent || '';
  const isAndroid = /android/i.test(ua);
  const isIos = /iphone|ipad|ipod/i.test(ua);
  const isMobile = /android|iphone|ipad|ipod|mobile/i.test(ua);

  const isDisplayStandalone =
    window.matchMedia &&
    window.matchMedia('(display-mode: standalone)').matches;

  const isStandaloneIOS = !!window.navigator.standalone;
  const isStandalone = isDisplayStandalone || isStandaloneIOS;

  const onHttps =
    location.protocol === 'https:' || location.hostname === 'localhost';

  document.addEventListener('DOMContentLoaded', () => {
    if (!onHttps) return;
    if (!isMobile) return;       // nooit op desktop
    if (isStandalone) return;    // nooit als PWA al draait

    if (isAndroid) {
      setupAndroidInstallPrompt();
    }

    if (isIos) {
      setupIosInstallPrompt();
    }
  });

  // ---------------------------------------------------------------------------
  // ANDROID: INSTALL PROMPT VIA EIGEN MODAL + "INSTALLEER APP" KNOP
  // ---------------------------------------------------------------------------

    function setupAndroidInstallPrompt() {
  let deferredPrompt = null;
  const SESSION_KEY = 'pwa_android_install_prompt_shown_v1';

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();

    // Per sessie maar één keer
    if (sessionStorage.getItem(SESSION_KEY) === '1') return;

    deferredPrompt = event;
    openAndroidInstallModal();
  });

  function openAndroidInstallModal() {
    if (document.getElementById('androidInstallModal')) return;

    const appName =
      document.querySelector('meta[name="application-name"]')?.content ||
      document.title ||
      'Mijn App';

    const iconHref = document.querySelector('link[rel="apple-touch-icon"]')?.href || '';
    const appDomain = location.host;

    const modal = document.createElement('div');
    modal.id = 'androidInstallModal';
    modal.className = 'push-modal android-install-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-hidden', 'false');

    modal.innerHTML = `
      <div class="push-backdrop"></div>
      <div class="push-card ios-install-card android-install-card">
        <button class="push-close" type="button" aria-label="Sluiten">&times;</button>

        <header class="ios-install-header">
          <h2 class="ios-install-title">Installeer de app</h2>
        </header>

        <section class="ios-app-row">
          <div class="ios-app-icon">
            ${iconHref ? `<img src="${iconHref}" alt="${appName} icoon" loading="lazy">` : ''}
          </div>
          <div class="ios-app-meta">
            <div class="ios-app-name">${appName}</div>
            <div class="ios-app-domain">${appDomain}</div>
          </div>
        </section>

        <p class="android-install-text">
          Installeer de Apo Jansen app op je apparaat voor snelle toegang, zo werkt het net als een normale app.
        </p>

        <div class="android-install-actions">
          <button type="button" class="android-install-cta">
            Installeer app
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const backdrop = modal.querySelector('.push-backdrop');
    const closeBtn = modal.querySelector('.push-close');
    const ctaBtn = modal.querySelector('.android-install-cta');

    const close = () => {
      modal.setAttribute('aria-hidden', 'true');
      setTimeout(() => {
        if (modal.parentNode) modal.parentNode.removeChild(modal);
      }, 250);
    };

    backdrop.addEventListener('click', close);
    closeBtn.addEventListener('click', close);

    ctaBtn.addEventListener('click', async () => {
      if (!deferredPrompt) {
        console.warn('[pwa] Geen deferred install prompt beschikbaar voor Android.');
        close();
        return;
      }

      try {
        const result = await deferredPrompt.prompt(); // Richer UI
        console.log('[pwa] Android install outcome:', result.outcome);
      } catch (err) {
        console.warn('[pwa] Android install error:', err);
      } finally {
        // Markeer als getoond in deze sessie
        sessionStorage.setItem(SESSION_KEY, '1');
        deferredPrompt = null;
        close();
      }
    });
  }
}

  // ---------------------------------------------------------------------------
  // iOS: PROGRESSIER-STYLE INSTALL PROMPT (PER SESSIE)
  // ---------------------------------------------------------------------------

  function setupIosInstallPrompt() {
    const SESSION_KEY = 'pwa_ios_install_prompt_shown_v1';

    // Per sessie/tab maar één keer tonen
    if (sessionStorage.getItem(SESSION_KEY) === '1') return;

    // Markeer direct als "gepland voor deze sessie"
    sessionStorage.setItem(SESSION_KEY, '1');

    setTimeout(() => {
      openIosInstallModal();
    }, 500);
  }

  function openIosInstallModal() {
    if (document.getElementById('iosInstallModal')) return;

    // Appnaam: apple-mobile-web-app-title > application-name > document.title
    const appName =
      document.querySelector('meta[name="apple-mobile-web-app-title"]')?.content ||
      document.querySelector('meta[name="application-name"]')?.content ||
      document.title ||
      'Mijn App';

    // Logo: apple-touch-icon uit de head
    const iconHref = document.querySelector('link[rel="apple-touch-icon"]')?.href || '';

    const appDomain = location.host;

    const modal = document.createElement('div');
    modal.id = 'iosInstallModal';
    modal.className = 'push-modal ios-install-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-hidden', 'false');

    modal.innerHTML = `
      <div class="push-backdrop"></div>
      <div class="push-card ios-install-card">
        <button class="push-close" type="button" aria-label="Sluiten">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        <header class="ios-install-header">
          <h2 class="ios-install-title">Installeer de app</h2>
        </header>

        <section class="ios-app-row">
          <div class="ios-app-icon">
            ${iconHref ? `<img src="${iconHref}" alt="${appName} icoon" loading="lazy">` : ''}
          </div>
          <div class="ios-app-meta">
            <div class="ios-app-name">${appName}</div>
            <div class="ios-app-domain">${appDomain}</div>
          </div>
        </section>

        <ol class="ios-steps ios-install-steps">

          <!-- Stap 1 -->
          <li>
            Tik onderaan in Safari op
            <span class="ios-chip">
              <span class="ios-chip-icon">
                <!-- iOS share icon -->
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                     xmlns="http://www.w3.org/2000/svg">
                  <path d="M20 13V19C20 20.1046 19.1046 21 18 21H6C4.89543 21 4 20.1046 4 19V13"
                        stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                        stroke-linejoin="round"></path>
                  <path d="M12 15V3M12 3L8.5 6.5M12 3L15.5 6.5"
                        stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                        stroke-linejoin="round"></path>
                </svg>
              </span>
            </span>
          </li>

          <!-- Stap 2 -->
          <li>
            Kies
            <span class="ios-chip ios-chip-button">
              <span class="ios-chip-icon">
                <!-- Add to Home Screen icon -->
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                     xmlns="http://www.w3.org/2000/svg">
                  <path d="M9 12H12M15 12H12M12 12V9M12 12V15"
                        stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                        stroke-linejoin="round"></path>
                  <path d="M21 3.6V20.4C21 20.7314 20.7314 21 20.4 21H3.6C3.26863 21 3 20.7314 3 20.4V3.6C3 3.26863 3.26863 3 3.6 3H20.4C20.7314 3 21 3.26863 21 3.6Z"
                        stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                        stroke-linejoin="round"></path>
                </svg>
              </span>
              <span class="ios-chip-label">Zet op beginscherm</span>
            </span>
          </li>

          <!-- Stap 3 -->
          <li>
            Klik rechtsboven op <strong>‘Voeg toe’</strong>.
          </li>

          <!-- Stap 4 -->
          <li>
            Zoek daarna het <strong>${appName}</strong> icoon op je beginscherm.
          </li>

        </ol>
      </div>
    `;

    document.body.appendChild(modal);

    const backdrop = modal.querySelector('.push-backdrop');
    const closeBtn = modal.querySelector('.push-close');

    const close = () => {
      modal.setAttribute('aria-hidden', 'true');
      setTimeout(() => {
        if (modal.parentNode) modal.parentNode.removeChild(modal);
      }, 250);
    };

    backdrop.addEventListener('click', close);
    closeBtn.addEventListener('click', close);
  }
})();