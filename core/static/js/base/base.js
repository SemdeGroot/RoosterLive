// ==========================================
// Scroll-positie behouden over redirects
// ==========================================
(function () {
  const KEY = 'rl_scroll_restore';

  // Stabiele DOM-path als sleutel: "div[2]/main[0]/div[3]"
  function domPath(el) {
    const parts = [];
    let node = el;
    while (node && node !== document.body) {
      const parent = node.parentElement;
      if (!parent) break;
      const idx = Array.prototype.indexOf.call(parent.children, node);
      parts.unshift(node.tagName.toLowerCase() + '[' + idx + ']');
      node = parent;
    }
    return parts.join('/');
  }

  // Zoek element terug op via opgeslagen path
  function findByPath(path) {
    let el = document.body;
    for (const part of path.split('/')) {
      const m = part.match(/^(\w+)\[(\d+)\]$/);
      if (!m) return null;
      const child = el.children[parseInt(m[2])];
      if (!child || child.tagName.toLowerCase() !== m[1]) return null;
      el = child;
    }
    return el;
  }

  // Sla alle gescrolde elementen op bij form-submit
  document.addEventListener('submit', function () {
    const positions = {};
    document.querySelectorAll('*').forEach(el => {
      if (el.scrollTop > 0 || el.scrollLeft > 0) {
        positions[domPath(el)] = { top: el.scrollTop, left: el.scrollLeft };
      }
    });
    if (Object.keys(positions).length) {
      sessionStorage.setItem(KEY, JSON.stringify(positions));
    }
  }, true);

  // Herstel na page load; rAF zodat layout klaarstaat, daarna class verwijderen om te tonen
  const raw = sessionStorage.getItem(KEY);
  if (raw) {
    sessionStorage.removeItem(KEY);
    requestAnimationFrame(() => {
      const positions = JSON.parse(raw);
      Object.entries(positions).forEach(([path, pos]) => {
        const el = findByPath(path);
        if (el) {
          el.scrollTop = pos.top;
          el.scrollLeft = pos.left;
        }
      });
      document.documentElement.classList.remove('restoring-scroll');
    });
  } else {
    // Geen herstel nodig: class direct verwijderen (veiligheidshalve)
    document.documentElement.classList.remove('restoring-scroll');
  }
})();

// ==========================================
// Header-hoogte als CSS-var (voor flash-container top)
// ==========================================
(function () {
  const header = document.querySelector('.header');
  if (!header) return;
  const update = () =>
    document.documentElement.style.setProperty('--header-h', header.offsetHeight + 'px');
  update();
  new ResizeObserver(update).observe(header);
})();

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

// ==================================================
// SERVICE WORKER REGISTRATIE + CLEANUP VIA ?sw_cleanup=1
// ==================================================
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
