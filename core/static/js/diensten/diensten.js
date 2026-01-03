(() => {
  // Week-picker elementen (zelfde IDs als in jouw template)
  const btnPrev   = document.getElementById('prevWeekBtn');
  const btnNext   = document.getElementById('nextWeekBtn');
  const pickerBtn = document.getElementById('weekPickerBtn');
  const menu      = document.getElementById('weekMenu');

  function goTo(targetISO){
    if (!targetISO) return;
    const url = new URL(window.location.href);
    url.searchParams.set('monday', targetISO);
    window.location.href = url.toString();
  }

  function bindArrow(btn){
    if (!btn || btn.disabled) return;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = btn.dataset.target;
      if (target) goTo(target);
    });
  }
  bindArrow(btnPrev);
  bindArrow(btnNext);

  function openMenu(){
    if (!menu) return;
    menu.hidden = false;
    pickerBtn?.setAttribute('aria-expanded','true');
    menu.focus({ preventScroll:true });
  }
  function closeMenu(){
    if (!menu) return;
    menu.hidden = true;
    pickerBtn?.setAttribute('aria-expanded','false');
  }

  pickerBtn?.addEventListener('click', (e)=>{
    e.preventDefault();
    const isOpen = pickerBtn.getAttribute('aria-expanded') === 'true';
    isOpen ? closeMenu() : openMenu();
  });

  menu?.addEventListener('click', (e)=>{
    const opt = e.target.closest('.week-option');
    if (!opt) return;
    goTo(opt.dataset.value);
    closeMenu();
  });

  menu?.addEventListener('keydown', (e)=>{
    const opts = Array.from(menu.querySelectorAll('.week-option'));
    const idx = opts.indexOf(document.activeElement);

    if (e.key === 'Escape'){
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
        goTo(opt.dataset.value);
        closeMenu();
      }
    }
  });

  // zelfde tabindex gedrag als jouw availability script
  menu?.querySelectorAll('.week-option').forEach(el => el.setAttribute('tabindex','-1'));

  // klik buiten menu sluit menu
  document.addEventListener('click', (e)=>{
    if (!menu || menu.hidden) return;
    if (e.target === pickerBtn || pickerBtn?.contains(e.target)) return;
    if (menu.contains(e.target)) return;
    closeMenu();
  });
})();