(function () {
  // --- Upload UI
  const dz = document.getElementById('polDrop');
  const input = document.getElementById('polFile');
  const meta = document.getElementById('polMeta');
  const nameSpan = document.getElementById('polName');
  const uploadBtn = document.getElementById('polUpload');
  const clearBtn = document.getElementById('polClear');

  if (dz && input) {
    function setFile(file) {
      if (!file) return;
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      if (!isPdf) { alert('Kies een PDF (.pdf).'); return; }

      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;

      if (nameSpan) nameSpan.textContent = file.name;
      if (meta) meta.style.display = '';
      if (uploadBtn) uploadBtn.disabled = false;
      if (clearBtn) clearBtn.style.display = '';
    }

    input.addEventListener('change', () => setFile(input.files[0]));
    ['dragenter','dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('is-dragover'); }));
    ['dragleave','drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('is-dragover'); }));
    dz.addEventListener('drop', e => { const f = e.dataTransfer.files?.[0]; if (f) setFile(f); });

    clearBtn && clearBtn.addEventListener('click', () => {
      input.value = '';
      if (nameSpan) nameSpan.textContent = '';
      if (meta) meta.style.display = 'none';
      if (uploadBtn) uploadBtn.disabled = true;
      clearBtn.style.display = 'none';
    });
  }

  // --- Inline delete via fetch naar DEZELFDE URL
  const pages = document.getElementById('polPages');
  if (pages) {
    function getCSRF() {
      const m = document.cookie.match(/csrftoken=([^;]+)/);
      return m ? m[1] : '';
    }

    pages.addEventListener('click', async (e) => {
      const btn = e.target.closest('.del-btn');
      if (!btn) return;

      const img = btn.getAttribute('data-img');
      if (!img) return;

      if (!confirm('Weet je zeker dat je de PDF wilt verwijderen?')) return;
      btn.disabled = true;

      try {
        const resp = await fetch(window.location.href, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCSRF(),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          body: 'action=delete&img=' + encodeURIComponent(img)
        });

        const data = await resp.json();
        if (data && data.ok) {
          const hash = data.hash;
          document.querySelectorAll('.page').forEach(card => {
            const u = card.getAttribute('data-img') || '';
            if (u.includes('/cache/policies/' + hash + '/')) card.remove();
          });
        } else {
          alert((data && data.error) ? data.error : 'Verwijderen mislukt.');
          btn.disabled = false;
        }
      } catch (err) {
        alert('Netwerkfout bij verwijderen.');
        btn.disabled = false;
      }
    });
  }
})();
