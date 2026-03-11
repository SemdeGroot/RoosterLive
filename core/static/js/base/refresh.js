// ---------- PULL TO REFRESH IN PWA STANDALONE ----------
(function () {
  const isCapacitor = !!window.Capacitor;
  const isStandalone =
    (window.matchMedia &&
      window.matchMedia('(display-mode: standalone)').matches) ||
    window.navigator.standalone === true ||
    isCapacitor;

  if (!isStandalone) {
    return;
  }

  const ptr = document.getElementById('pull-to-refresh');
  if (!ptr) return;

  const dots = Array.from(ptr.querySelectorAll('.ptr-dot'));
  const app = document.querySelector('.app');
  const body = document.body;
  const content = document.querySelector('.content'); // cached
  const navPanel = document.getElementById('navPanel'); // voor nav-open check

  let startY = 0;
  let pulling = false;
  let maxPull = 0;
  let wasArmed = false;

  const PULL_THRESHOLD = 200;   // hoeveel je moet pullen
  const MAX_VISUAL_PULL = 100;  // hoe ver de indicator visueel naar beneden komt
  const REFRESH_OFFSET = 100;    // zelfde positie aanhouden tijdens refresh
  const CONTENT_PUSH_MAX = 80;  // max px de content mee naar beneden schuift

  // ============================
  //  SENTINEL: "bovenaan" detectie
  // ============================
  let sentinelVisible = true;

  (function setupSentinel() {
    if (!content) return;

    const sentinel = document.createElement('div');
    sentinel.setAttribute('data-ptr-sentinel', 'true');
    // position:absolute zodat hij NIET als grid-item meedoet (geen extra rij + gap)
    sentinel.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none;';

    content.insertBefore(sentinel, content.firstChild);

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        sentinelVisible = !!entry.isIntersecting && entry.intersectionRatio > 0;
      },
      {
        root: null,
        threshold: 0.01
      }
    );

    observer.observe(sentinel);
  })();

  async function hapticTick() {
    // 1) Capacitor native eerst
    try {
      const Cap = window.Capacitor;
      const isNative =
        !!Cap &&
        typeof Cap.isNativePlatform === "function" &&
        Cap.isNativePlatform();

      const Haptics = Cap?.Plugins?.Haptics;

      if (isNative && Haptics && typeof Haptics.impact === "function") {
        await Haptics.impact({ style: "LIGHT" });
        return;
      }
    } catch (_) {}

    // 2) Web/PWA fallback
    if (navigator.vibrate) {
      navigator.vibrate(40);
      return;
    }

    const el = document.createElement("div");
    const id = "haptic-" + Math.random().toString(36).slice(2);

    el.innerHTML =
      '<input type="checkbox" id="' + id + '" switch />' +
      '<label for="' + id + '"></label>';

    el.style.cssText =
      "position:fixed;left:-9999px;top:auto;width:1px;height:1px;" +
      "overflow:hidden;opacity:0;pointer-events:none;";

    document.body.appendChild(el);

    const label = el.querySelector("label");
    if (label) label.click();

    setTimeout(() => el.remove(), 500);
  }

  function updateDotsByProgress(progress) {
    const count = Math.round(progress * dots.length);
    dots.forEach((dot, i) => {
      dot.classList.toggle('active', i < count);
    });
  }

  function setProgress(dy) {
    const clamped = Math.max(0, dy);
    const visual = Math.min(clamped, MAX_VISUAL_PULL);
    const progress = Math.min(clamped / PULL_THRESHOLD, 1);

    ptr.style.setProperty('--ptr-translate', `${visual}px`);
    ptr.style.setProperty(
      '--ptr-opacity',
      Math.min(1, clamped / 40).toString()
    );

    updateDotsByProgress(progress);

    // Schuif de content proportioneel mee voor vloeiende PTR-feedback
    if (content) {
      const push = Math.min(progress * CONTENT_PUSH_MAX, CONTENT_PUSH_MAX);
      content.style.transform = `translateY(${push}px)`;
    }

    if (progress >= 1 && !wasArmed) {
      wasArmed = true;
      hapticTick();
    }
    if (progress < 1) {
      wasArmed = false;
    }
  }

  function resetPTR() {
    pulling = false;
    maxPull = 0;
    wasArmed = false;
    ptr.classList.remove('refreshing');
    ptr.style.setProperty('--ptr-translate', '0px');
    ptr.style.setProperty('--ptr-opacity', '0');
    dots.forEach((dot) => dot.classList.remove('active'));

    if (content) {
      content.classList.remove('ptr-shift-down');
      content.style.transition = ''; // herstel CSS-transitie
      content.style.transform = '';  // spring terug naar 0 (via CSS-transitie)
    }
  }

  window.addEventListener(
    'touchstart',
    (e) => {
      if (e.touches.length !== 1) return;

      // Niet starten als de nav open is (voorkomt accidentele PTR + viewport-bounce na sluiten)
      if (navPanel && !navPanel.hidden) return;

      const target = e.target;

      if (target.closest('input, textarea, select, [contenteditable="true"]')) {
        return;
      }

      let el = target;
      let isInnerScrolled = false;
      while (el && el !== document.body && el !== document.documentElement) {
        if (el.scrollTop > 0) {
          isInnerScrolled = true;
          break;
        }
        el = el.parentElement;
      }

      if (content && content.scrollTop > 0) {
        isInnerScrolled = true;
      }

      if (isInnerScrolled) return;
      if (!sentinelVisible) return;

      startY = e.touches[0].clientY;
      pulling = true;
      maxPull = 0;
      wasArmed = false;

      ptr.style.transition = 'none';
      if (content) content.style.transition = 'none'; // geen transitie tijdens drag
      setProgress(0);
    },
    { passive: true }
  );

  window.addEventListener(
    'touchmove',
    (e) => {
      if (!pulling) return;

      const target = e.target;

      if (target.closest('input, textarea, select, [contenteditable="true"]')) {
        return;
      }

      const dy = e.touches[0].clientY - startY;
      if (dy <= 0) {
        ptr.style.transition =
          'transform 0.18s ease-out, opacity 0.18s ease-out';
        resetPTR();
        return;
      }

      maxPull = Math.max(maxPull, dy);
      setProgress(dy);
    },
    { passive: true }
  );

  window.addEventListener('touchend', () => {
    if (!pulling) return;

    ptr.style.transition = 'transform 0.18s ease-out, opacity 0.18s ease-out';
    if (content) content.style.transition = ''; // herstel CSS-transitie voor animatie

    if (maxPull >= PULL_THRESHOLD) {
      ptr.classList.add('refreshing');
      ptr.style.setProperty('--ptr-translate', `${REFRESH_OFFSET}px`);
      ptr.style.setProperty('--ptr-opacity', '1');
      dots.forEach((dot) => dot.classList.remove('active'));

      if (content) {
        // inline transform houdt de content op 60px terwijl de pagina herlaadt
        content.style.transform = `translateY(60px)`;
      }

      setTimeout(() => {
        window.location.reload();
      }, 2500);
    } else {
      resetPTR();
    }
  });
})();
