(() => {
  // Scope alles onder #roosterRoot zodat er geen clash is met andere pagina's
  const root       = document.getElementById('roosterRoot');
  if (!root) return;

  // Week-picker elementen (identieke ids/klassen als mijnbeschikbaarheid)
  const btnPrev     = root.querySelector('#prevWeekBtn');
  const btnNext     = root.querySelector('#nextWeekBtn');
  const pickerBtn   = root.querySelector('#weekPickerBtn');
  const menu        = root.querySelector('#weekMenu');
  const mondayField = root.querySelector('#mondayField');

  // ---------- Navigatie helpers ----------
  function goTo(targetISO) {
    if (!targetISO) return;
    if (mondayField) mondayField.value = targetISO; // upload landt op gekozen week
    const url = new URL(window.location.href);
    url.searchParams.set('monday', targetISO);
    window.location.href = url.toString();
  }

  function bindArrow(btn) {
    if (!btn || btn.disabled) return;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = btn.dataset.target;
      if (target) goTo(target);
    });
  }
  bindArrow(btnPrev);
  bindArrow(btnNext);

  // ---------- Week-picker open/close (zoals mijnbeschikbaarheid) ----------
  function openMenu() {
    if (!menu) return;
    menu.hidden = false;
    pickerBtn?.setAttribute('aria-expanded','true');
    menu.focus({ preventScroll: true });
  }
  function closeMenu() {
    if (!menu) return;
    menu.hidden = true;
    pickerBtn?.setAttribute('aria-expanded','false');
  }

  pickerBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    const isOpen = pickerBtn.getAttribute('aria-expanded') === 'true';
    isOpen ? closeMenu() : openMenu();
  });

  menu?.addEventListener('click', (e) => {
    const opt = e.target.closest('.week-option');
    if (!opt) return;
    goTo(opt.dataset.value);
    closeMenu();
  });

  // Keyboardnavigatie (idem)
  menu?.addEventListener('keydown', (e) => {
    const opts = Array.from(menu.querySelectorAll('.week-option'));
    const idx = opts.indexOf(document.activeElement);
    if (e.key === 'Escape') { closeMenu(); pickerBtn?.focus(); }
    else if (e.key === 'ArrowDown') {
      e.preventDefault(); (opts[idx+1] || opts[0]).focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault(); (opts[idx-1] || opts[opts.length-1]).focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      const opt = document.activeElement;
      if (opt?.classList.contains('week-option')) {
        goTo(opt.dataset.value);
        closeMenu();
      }
    }
  });

  menu?.querySelectorAll('.week-option').forEach(el => el.setAttribute('tabindex','-1'));

  // Klik buiten menu => sluiten (maar alleen binnen deze root)
  document.addEventListener('click', (e) => {
    if (!menu || menu.hidden) return;
    // clicks binnen root: laat open/close normaal werken
    if (root.contains(e.target)) {
      if (e.target === pickerBtn || pickerBtn?.contains(e.target)) return;
      if (menu.contains(e.target)) return;
      closeMenu();
      return;
    }
    // click buiten root: ook sluiten
    closeMenu();
  });

  // ---------- Uploader ----------
  const dz        = root.querySelector('#dropzone');
  const input     = root.querySelector('#rosterFile');
  const meta      = root.querySelector('#fileMeta');
  const nameSpan  = root.querySelector('#fileName');
  const uploadBtn = root.querySelector('#uploadBtn');
  const clearBtn  = root.querySelector('#clearBtn');

  function setFile(file) {
    if (!file) return;
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Kies een PDF-bestand (.pdf).'); return;
    }
    const dt = new DataTransfer();
    dt.items.add(file);
    if (input) input.files = dt.files;

    if (nameSpan) nameSpan.textContent = file.name;
    if (meta) meta.style.display = '';
    if (uploadBtn) uploadBtn.disabled = false;
    if (clearBtn) clearBtn.style.display = '';
  }

  input?.addEventListener('change', () => setFile(input.files[0]));

  ['dragenter','dragover'].forEach(ev =>
    dz?.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dz.classList.add('is-dragover'); })
  );
  ['dragleave','drop'].forEach(ev =>
    dz?.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dz.classList.remove('is-dragover'); })
  );
  dz?.addEventListener('drop', e => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setFile(f);
  });

  clearBtn?.addEventListener('click', () => {
    if (input) input.value = '';
    if (nameSpan) nameSpan.textContent = '';
    if (meta) meta.style.display = 'none';
    if (uploadBtn) uploadBtn.disabled = true;
    if (clearBtn) clearBtn.style.display = 'none';
  });
})();