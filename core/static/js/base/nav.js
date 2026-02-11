// ============================
// MOBILE NAV PANEL
// ============================
(function () {
  const toggleBtn = document.getElementById('navToggle');
  const panel = document.getElementById('navPanel');
  const overlay = document.getElementById('navOverlay');
  const closeBtn = document.getElementById('navClose');

  if (!toggleBtn || !panel || !overlay) return;

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

  const close = (immediate = false) => {
    panel.classList.remove('open');
    overlay.classList.remove('active');
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.setAttribute('aria-label', 'Open navigatie');
    allowScroll();

    if (immediate) {
      panel.hidden = true;
      return;
    }
    setTimeout(() => { panel.hidden = true; }, 250);
  };

  const isOpen = () => toggleBtn.getAttribute('aria-expanded') === 'true';

  // Altijd dicht bij pageload + bij back/forward cache restores
  const forceClosed = () => close(true);
  forceClosed();
  window.addEventListener('pageshow', forceClosed);

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    isOpen() ? close() : open();
  });

  if (closeBtn) closeBtn.addEventListener('click', () => close());

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen()) {
      close();
      toggleBtn.focus();
    }
  });

  overlay.addEventListener('click', () => close());

  document.addEventListener('click', (e) => {
    if (!isOpen()) return;
    if (!panel.contains(e.target) && !toggleBtn.contains(e.target)) close();
  });

  // Alleen sluiten bij echte navigatie links of logout submit
  panel.querySelectorAll('a[href], form button[type="submit"]').forEach(el => {
    el.addEventListener('click', () => { if (isOpen()) close(); });
  });

  // Submenu toggle (summary) mag niet sluiten
  panel.querySelectorAll('summary').forEach(s => {
    s.addEventListener('click', (e) => e.stopPropagation());
  });

  const mq = window.matchMedia('(min-width: 901px)');
  mq.addEventListener('change', (e) => { if (e.matches && isOpen()) close(true); });

  // Focus trap
  panel.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab' || !isOpen()) return;
    const focusable = panel.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
})();


// ============================
// DESKTOP SIDEBAR COLLAPSE
// ============================
(function () {
  const btn = document.getElementById('sidebarToggle');
  const app = document.querySelector('.app');
  if (!btn || !app) return;

  const key = 'sidebarCollapsed_v1';

  const apply = (collapsed, animate = false) => {
    if (animate) document.documentElement.classList.add('sidebar-animating');

    app.classList.toggle('sidebar-collapsed', collapsed);
    document.documentElement.classList.toggle('sidebar-open', !collapsed);

    btn.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
    btn.setAttribute('aria-label', collapsed ? 'Klap menu uit' : 'Klap menu in');

    if (!animate) return;

    const onDone = (e) => {
      if (e.propertyName !== 'grid-template-columns') return;
      document.documentElement.classList.remove('sidebar-animating');
      app.removeEventListener('transitionend', onDone);
    };
    app.addEventListener('transitionend', onDone);
  };

  const readCollapsed = () => {
    try {
      const v = localStorage.getItem(key);  // '1' | '0' | null
      if (v === null) return false;         // default: open
      return v === '1';
    } catch {
      return false;
    }
  };

  const applyFromStorage = () => apply(readCollapsed(), false);

  // Init: sync app + aria met wat inline in head al bepaalde
  applyFromStorage();

  // BFCache restores: opnieuw syncen
  window.addEventListener('pageshow', applyFromStorage);

  btn.addEventListener('click', () => {
    const nextCollapsed = !app.classList.contains('sidebar-collapsed');
    try { localStorage.setItem(key, nextCollapsed ? '1' : '0'); } catch {}
    apply(nextCollapsed, true);
  });
})();