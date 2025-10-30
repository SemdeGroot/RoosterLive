(() => {
  const form = document.getElementById('availabilityForm');
  const redirectField = document.getElementById('redirectToMonday');
  const checkboxes = form ? Array.from(form.querySelectorAll('input[type="checkbox"]')) : [];
  const initial = new Map(checkboxes.map(cb => [cb.name, cb.checked]));
  const PROMPT = "Wil je je beschikbaarheid opslaan?";

  const isDirty  = () => checkboxes.some(cb => cb.checked !== initial.get(cb.name));
  const saveThenGo = (targetISO) => { redirectField.value = targetISO || ""; form.submit(); };
  const discardAndGo = (targetISO) => {
    const url = new URL(window.location.href);
    url.searchParams.set('monday', targetISO);
    window.location.href = url.toString();
  };

  // Week-picker elementen
  const btnPrev = document.getElementById('prevWeekBtn');
  const btnNext = document.getElementById('nextWeekBtn');
  const pickerBtn = document.getElementById('weekPickerBtn');
  const menu = document.getElementById('weekMenu');

  function goTo(targetISO){
    if (!isDirty()) return discardAndGo(targetISO);
    if (confirm(PROMPT)) saveThenGo(targetISO);
    else discardAndGo(targetISO);
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
    if (e.key === 'Escape'){ closeMenu(); pickerBtn?.focus(); }
    else if (e.key === 'ArrowDown'){
      e.preventDefault();
      (opts[idx+1] || opts[0]).focus();
    } else if (e.key === 'ArrowUp'){
      e.preventDefault();
      (opts[idx-1] || opts[opts.length-1]).focus();
    } else if (e.key === 'Enter' || e.key === ' '){
      e.preventDefault();
      const opt = document.activeElement;
      if (opt?.classList.contains('week-option')) {
        goTo(opt.dataset.value);
        closeMenu();
      }
    }
  });

  menu?.querySelectorAll('.week-option').forEach(el => el.setAttribute('tabindex','-1'));

  document.addEventListener('click', (e)=>{
    if (!menu || menu.hidden) return;
    if (e.target === pickerBtn || pickerBtn?.contains(e.target)) return;
    if (menu.contains(e.target)) return;
    closeMenu();
  });

  window.addEventListener('pageshow', () => {
    checkboxes.forEach(cb => initial.set(cb.name, cb.checked));
  });
})();
