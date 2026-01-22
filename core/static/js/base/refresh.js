// ---------- PULL TO REFRESH IN PWA STANDALONE ----------
(function () {
  const isCapacitor = !!window.Capacitor;
  const isStandalone =
    (window.matchMedia &&
      window.matchMedia('(display-mode: standalone)').matches) ||
    window.navigator.standalone === true ||
    isCapacitor; // Voeg deze toe

  if (!isStandalone) {
    return; 
  }

  const ptr = document.getElementById('pull-to-refresh');
  if (!ptr) return;

  const dots = Array.from(ptr.querySelectorAll('.ptr-dot'));
  const app = document.querySelector('.app');
  const body = document.body;

  let startY = 0;
  let pulling = false;
  let maxPull = 0;
  let wasArmed = false;

  const PULL_THRESHOLD = 220;   // hoeveel je moet pullen
  const MAX_VISUAL_PULL = 90;   // hoe ver de indicator visueel naar beneden komt
  const REFRESH_OFFSET = 90;    // zelfde positie aanhouden tijdens refresh

  // ============================
  //  SENTINEL: "bovenaan" detectie
  // ============================
  let sentinelVisible = true; // fallback: liever wél PTR aan de top als er iets misgaat

  (function setupSentinel() {
    const content = document.querySelector('main.content');
    if (!content) return; // fallback: dan doen we het zonder sentinel

    // klein onzichtbaar element bovenaan de content
    const sentinel = document.createElement('div');
    sentinel.setAttribute('data-ptr-sentinel', 'true');
    sentinel.style.position = 'relative';
    sentinel.style.width = '1px';
    sentinel.style.height = '1px';
    sentinel.style.margin = '0';
    sentinel.style.padding = '0';
    sentinel.style.opacity = '0';
    sentinel.style.pointerEvents = 'none';

    // als eerste kind van .content
    content.insertBefore(sentinel, content.firstChild);

    // observer die bijhoudt of de sentinel in beeld is
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        sentinelVisible = !!entry.isIntersecting && entry.intersectionRatio > 0;
      },
      {
        root: null,          // viewport
        threshold: 0.01      // zodra hij maar een beetje in beeld is
      }
    );

    observer.observe(sentinel);
  })();

  // Eén tikje haptic feedback (Android: vibrate, iOS: switch-hack)
  function hapticTick() {
    if (navigator.vibrate) {
      // Android / sommige browsers
      navigator.vibrate(40); // kort voelbaar tikje
      return;
    }

    // iOS fallback: onzichtbare switch togglen voor haptics
    const el = document.createElement('div');
    const id = 'haptic-' + Math.random().toString(36).slice(2);

    el.innerHTML =
      '<input type="checkbox" id="' + id + '" switch />' +
      '<label for="' + id + '"></label>';

    el.style.cssText =
      'position:fixed;left:-9999px;top:auto;width:1px;height:1px;' +
      'overflow:hidden;opacity:0;pointer-events:none;';

    document.body.appendChild(el);

    const label = el.querySelector('label');
    if (label) {
      label.click(); // triggert de haptic
    }

    setTimeout(() => {
      el.remove();
    }, 500);
  }

  function updateDotsByProgress(progress) {
    // progress: 0–1 → aantal actieve dots
    const count = Math.round(progress * dots.length);
    dots.forEach((dot, i) => {
      dot.classList.toggle('active', i < count);
    });
  }

  function setProgress(dy) {
    const clamped = Math.max(0, dy);
    const visual = Math.min(clamped, MAX_VISUAL_PULL);
    const progress = Math.min(clamped / PULL_THRESHOLD, 1); // 0–1

    // verticale positie en zichtbaarheid
    ptr.style.setProperty('--ptr-translate', `${visual}px`);
    ptr.style.setProperty(
      '--ptr-opacity',
      Math.min(1, clamped / 40).toString()
    );

    // dots vullen per stap
    updateDotsByProgress(progress);

    // "tikje" als de drempel voor het eerst wordt gehaald
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

    if (app) {
      app.classList.remove('ptr-shift-down');
    }

    if (body) {              
      body.classList.remove('ptr-panel-bg');
    }
  }

  window.addEventListener(
    'touchstart',
    (e) => {
      if (e.touches.length !== 1) return;

      const target = e.target;

      // Nooit PTR starten op form-controls
      if (target.closest('input, textarea, select, [contenteditable="true"]')) {
        return;
      }

      if (!sentinelVisible) return;

      startY = e.touches[0].clientY;
      pulling = true;
      maxPull = 0;
      wasArmed = false;

      ptr.style.transition = 'none';
      setProgress(0);
    },
    { passive: true }
  );

  window.addEventListener(
    'touchmove',
    (e) => {
      if (!pulling) return;

      const target = e.target;

      // Extra veiligheid: tijdens move ook niet rommelen met form-controls
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

    if (maxPull >= PULL_THRESHOLD) {
      // Drempel gehaald → dots worden spinner
      ptr.classList.add('refreshing');
      ptr.style.setProperty('--ptr-translate', `${REFRESH_OFFSET}px`);
      ptr.style.setProperty('--ptr-opacity', '1');
      dots.forEach((dot) => dot.classList.remove('active'));

      // hele app (header + content) een beetje omlaag
      if (app) {
        app.classList.add('ptr-shift-down');
      }

      // body-top vlak in kleur var(--panel)
      if (body) {
        body.classList.add('ptr-panel-bg');
      }

      // kleine delay zodat spinner + shift zichtbaar zijn
      setTimeout(() => {
        window.location.reload();
      }, 2500); // tijd van animatie
    } else {
      resetPTR();
    }
  });
})();