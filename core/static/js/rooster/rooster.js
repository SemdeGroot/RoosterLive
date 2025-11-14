(() => {
  // Scope alles onder #roosterRoot zodat er geen clash is met andere pagina's
  const root = document.getElementById('roosterRoot');
  if (!root) return;

  // -------- Week-picker elementen (identieke ids/klassen als mijnbeschikbaarheid) --------
  const btnPrev     = root.querySelector('#prevWeekBtn');
  const btnNext     = root.querySelector('#nextWeekBtn');
  const pickerBtn   = root.querySelector('#weekPickerBtn');
  const menu        = root.querySelector('#weekMenu');
  const mondayField = root.querySelector('#mondayField');

  // -------- Helpers --------
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

  // Veilig 'closest' vanaf event target (Text node → parentElement)
  function closestFromEventTarget(e, selector) {
    let el = e.target;
    if (el && el.nodeType !== 1) el = el.parentElement; // b.v. Text node
    return el && el.closest ? el.closest(selector) : null;
  }

  // -------- Week-picker open/close --------
  function openMenu() {
    if (!menu) return;
    menu.hidden = false;
    pickerBtn?.setAttribute('aria-expanded', 'true');
    // focus naar eerste optie of menu zelf
    const first = menu.querySelector('.week-option');
    (first || menu).focus({ preventScroll: true });
  }

  function closeMenu() {
    if (!menu) return;
    menu.hidden = true;
    pickerBtn?.setAttribute('aria-expanded', 'false');
  }

  // Toggle via button
  pickerBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    const isOpen = pickerBtn.getAttribute('aria-expanded') === 'true';
    isOpen ? closeMenu() : openMenu();
  });

  // Klik op optie in menu (robust tegen Text-nodes)
  menu?.addEventListener('click', (e) => {
    const opt = closestFromEventTarget(e, '.week-option');
    if (!opt) return;
    e.preventDefault();
    goTo(opt.dataset.value);
    closeMenu();
  });

  // Keyboard navigatie in menu
  menu?.addEventListener('keydown', (e) => {
    const opts = Array.from(menu.querySelectorAll('.week-option'));
    const idx  = opts.indexOf(document.activeElement);
    if (e.key === 'Escape') {
      closeMenu(); pickerBtn?.focus();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      (opts[idx + 1] || opts[0])?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      (opts[idx - 1] || opts[opts.length - 1])?.focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      const opt = document.activeElement;
      if (opt?.classList.contains('week-option')) {
        goTo(opt.dataset.value);
        closeMenu();
      }
    }
  });

  // Buiten-klik sluit het menu
  document.addEventListener('click', (e) => {
    if (!menu || menu.hidden) return;
    const inside = root.contains(e.target);
    const isPicker = pickerBtn && (e.target === pickerBtn || pickerBtn.contains(e.target));
    const inMenu = menu.contains(e.target);
    if (!inside || (!isPicker && !inMenu)) {
      closeMenu();
    }
  });

  // -------- Uploader --------
  const dz        = root.querySelector('#dropzone');
  const input     = root.querySelector('#rosterFile');
  const nameSpan  = root.querySelector('#fileName');
  const meta      = root.querySelector('#fileMeta');
  const uploadBtn = root.querySelector('#uploadBtn');
  const clearBtn  = root.querySelector('#clearBtn');

  function setFile(file) {
    if (!file) return;
    const isPdfMime = file.type === 'application/pdf';
    const isPdfExt  = file.name.toLowerCase().endsWith('.pdf');
    if (!isPdfMime && !isPdfExt) {
      alert('Kies een PDF-bestand (.pdf).');
      return;
    }

    // Stop file in het <input type="file"> zodat native submit werkt
    const dt = new DataTransfer();
    dt.items.add(file);
    if (input) input.files = dt.files;

    // UI updates
    if (nameSpan) nameSpan.textContent = file.name;
    if (meta) meta.style.display = '';
    if (uploadBtn) uploadBtn.disabled = false;
    if (clearBtn) clearBtn.style.display = '';
  }

  // Bestandskeuze via dialoog
  input?.addEventListener('change', () => {
    const f = input.files && input.files[0];
    if (f) setFile(f);
  });

  // Drag & drop states
  ['dragenter', 'dragover'].forEach((ev) => {
    dz?.addEventListener(ev, (e) => {
      e.preventDefault(); e.stopPropagation();
      dz.classList.add('is-dragover');
    });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    dz?.addEventListener(ev, (e) => {
      e.preventDefault(); e.stopPropagation();
      dz.classList.remove('is-dragover');
    });
  });
  dz?.addEventListener('drop', (e) => {
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setFile(f);
  });

  // Clear
  clearBtn?.addEventListener('click', () => {
    if (input) input.value = '';
    if (nameSpan) nameSpan.textContent = '';
    if (meta) meta.style.display = 'none';
    if (uploadBtn) uploadBtn.disabled = true;
    if (clearBtn) clearBtn.style.display = 'none';
  });
})();