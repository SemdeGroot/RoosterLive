(() => {
  /* ---------- URL helpers ---------- */
  function goToMonday(targetISO){
    const url = new URL(window.location.href);
    if (targetISO) url.searchParams.set('monday', targetISO);
    else url.searchParams.delete('monday');
    window.location.href = url.toString();
  }

  function goToDayIdx(dayIdx){
    const url = new URL(window.location.href);
    url.searchParams.set('day', String(dayIdx));
    window.location.href = url.toString();
  }

  /* ---------- Day picker ---------- */
  const dayPicker = document.getElementById('dayPicker');
  dayPicker?.addEventListener('change', (e) => {
    goToDayIdx(e.target.value);
  });

  /* ---------- Arrows ---------- */
  const btnPrev = document.getElementById('prevWeekBtn');
  const btnNext = document.getElementById('nextWeekBtn');

  function bindArrow(btn){
    if (!btn || btn.disabled) return;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = btn.dataset.target;
      if (target) goToMonday(target);
    });
  }

  bindArrow(btnPrev);
  bindArrow(btnNext);

  /* ---------- Dropdown: portal + fixed positioning ---------- */
  const pickerBtn = document.getElementById('weekPickerBtn');
  const originalMenu = document.getElementById('weekMenu');
  let menu = originalMenu;
  let isPortaled = false;

  function portalMenuToBody(){
    if (!isPortaled) {
      document.body.appendChild(menu);
      isPortaled = true;
    }
  }

  function restoreMenu(){
    if (isPortaled) {
      document.querySelector('.week-picker')?.appendChild(menu);
      isPortaled = false;
    }
  }

  function positionMenu(){
    if (!pickerBtn || !menu) return;
    const gap = 6;
    const rect = pickerBtn.getBoundingClientRect();

    let top  = rect.bottom + gap;
    let left = rect.left + rect.width / 2;

    const vw = window.innerWidth;
    const vh = window.innerHeight;

    const mw = Math.max(menu.offsetWidth || 340, 340);
    const mh = Math.min(menu.offsetHeight || 0, 280);
    const half = mw / 2;

    if (left - half < 8) left = 8 + half;
    if (left + half > vw - 8) left = vw - 8 - half;

    if (top + mh > vh - 8) top = Math.max(8, rect.top - gap - mh);

    menu.style.top = `${top}px`;
    menu.style.left = `${left}px`;
  }

  function openMenu(){
    if (!menu) return;
    portalMenuToBody();
    menu.hidden = false;
    pickerBtn?.setAttribute('aria-expanded', 'true');
    positionMenu();
    menu.setAttribute('tabindex', '-1');
    menu.focus({ preventScroll: true });

    window.addEventListener('resize', positionMenu);
    window.addEventListener('scroll', positionMenu, { passive: true });
  }

  function closeMenu(){
    if (!menu) return;
    menu.hidden = true;
    pickerBtn?.setAttribute('aria-expanded', 'false');

    window.removeEventListener('resize', positionMenu);
    window.removeEventListener('scroll', positionMenu);
    restoreMenu();
  }

  pickerBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    const isOpen = pickerBtn.getAttribute('aria-expanded') === 'true';
    isOpen ? closeMenu() : openMenu();
  });

  menu?.addEventListener('click', (e) => {
    const opt = e.target.closest('.week-option');
    if (!opt) return;
    goToMonday(opt.dataset.value);
    closeMenu();
  });

  menu?.addEventListener('keydown', (e) => {
    const opts = Array.from(menu.querySelectorAll('.week-option'));
    const idx = opts.indexOf(document.activeElement);

    if (e.key === 'Escape'){
      e.preventDefault();
      closeMenu();
      pickerBtn?.focus();
    } else if (e.key === 'ArrowDown'){
      e.preventDefault();
      (opts[idx+1] || opts[0])?.focus();
    } else if (e.key === 'ArrowUp'){
      e.preventDefault();
      (opts[idx-1] || opts[opts.length-1])?.focus();
    } else if (e.key === 'Enter' || e.key === ' '){
      e.preventDefault();
      const opt = document.activeElement;
      if (opt?.classList.contains('week-option')) {
        goToMonday(opt.dataset.value);
        closeMenu();
      }
    }
  });

  menu?.querySelectorAll('.week-option').forEach(el => el.setAttribute('tabindex','-1'));

  document.addEventListener('click', (e) => {
    if (!menu || menu.hidden) return;
    if (e.target === pickerBtn || pickerBtn?.contains(e.target)) return;
    if (menu.contains(e.target)) return;
    closeMenu();
  });

  /* ---------- Sorteren via badges ---------- */
  const body = document.getElementById('matrixBody');
  const badges = document.querySelectorAll('.slot-badge');

  function setActiveBadge(slotId){
    badges.forEach(b => b.classList.toggle('active', b.dataset.slot === slotId));
  }

  function notifyPeriodChange(period){
    // koppel links (sort) aan rechts (actiepaneel)
    window.dispatchEvent(new CustomEvent("pd:periodChange", { detail: { period } }));
  }

  function sortBySlot(slotId){
    if (!body || !slotId) return;

    const [d, part] = String(slotId).split('|');
    const rows = Array.from(body.querySelectorAll('.matrix-row'));

    rows.sort((a, b) => {
      const aAvail = Number(a.getAttribute(`data-${d}-${part}`));
      const bAvail = Number(b.getAttribute(`data-${d}-${part}`));
      if (bAvail !== aAvail) return bAvail - aAvail;

      const ag = (a.getAttribute('data-group') || '').toLowerCase();
      const bg = (b.getAttribute('data-group') || '').toLowerCase();
      if (ag !== bg) return ag.localeCompare(bg);

      const af = (a.getAttribute('data-firstname') || '').toLowerCase();
      const bf = (b.getAttribute('data-firstname') || '').toLowerCase();
      return af.localeCompare(bf);
    });

    rows.forEach(r => body.appendChild(r));
    setActiveBadge(slotId);

    // sync naar actiepaneel
    notifyPeriodChange(part);
  }

  badges.forEach(b => b.addEventListener('click', () => sortBySlot(b.dataset.slot)));

  // default: altijd Ochtend actief bij GET
  try {
    const morningBadge = Array.from(badges).find(b => String(b.dataset.slot || '').endsWith('|morning'));
    if (morningBadge?.dataset?.slot) sortBySlot(morningBadge.dataset.slot);
  } catch(e) {
    // ignore
  }

  /* ---------- Search filter ---------- */
  const searchInput = document.getElementById('userSearch');
  if (searchInput && body) {
    const allRows = Array.from(body.querySelectorAll('.matrix-row'));

    searchInput.addEventListener('input', () => {
      const q = (searchInput.value || '').trim().toLowerCase();
      if (!q) {
        allRows.forEach(r => r.style.display = '');
        return;
      }
      allRows.forEach(r => {
        const g = (r.getAttribute('data-group') || '').toLowerCase();
        const f = (r.getAttribute('data-firstname') || '').toLowerCase();
        const hit = g.includes(q) || f.includes(q);
        r.style.display = hit ? '' : 'none';
      });
    });
  }
})();