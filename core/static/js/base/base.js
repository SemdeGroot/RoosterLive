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
