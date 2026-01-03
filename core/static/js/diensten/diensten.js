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

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("syncAgendaBtn");
  const modal = document.getElementById("agendaModal");
  const closeBtn = document.getElementById("agendaModalClose");

  if (!btn || !modal) return;

  const desktopWrap = document.getElementById("agendaDesktop");
  const mobileWrap = document.getElementById("agendaMobile");

  const webcalUrl = btn.getAttribute("data-webcal") || "";
  const httpsUrl = btn.getAttribute("data-https") || "";

  const webcalInput = document.getElementById("webcalInput");
  const copyBtn = document.getElementById("copyWebcalBtn");
  const copyBtnMobile = document.getElementById("copyWebcalBtnMobile");
  const openAgendaBtn = document.getElementById("openAgendaBtn");

  const okDesktop = document.getElementById("agendaModalOkDesktop");
  const okMobile = document.getElementById("agendaModalOkMobile");

  function isMobile() {
    return window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  }

  function openModal() {
    modal.style.display = "block";

    const mobile = isMobile();
    if (desktopWrap) desktopWrap.style.display = mobile ? "none" : "block";
    if (mobileWrap) mobileWrap.style.display = mobile ? "block" : "none";

    if (webcalInput) webcalInput.value = webcalUrl || httpsUrl;
  }

  function closeModal() {
    modal.style.display = "none";
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      // fallback
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        document.body.removeChild(ta);
        return true;
      } catch (e2) {
        document.body.removeChild(ta);
        return false;
      }
    }
  }

  btn.addEventListener("click", openModal);

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (okDesktop) okDesktop.addEventListener("click", closeModal);
  if (okMobile) okMobile.addEventListener("click", closeModal);

  // Sluit als je op overlay klikt
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  // Copy (desktop)
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const ok = await copyText(webcalUrl || httpsUrl);
      copyBtn.textContent = ok ? "Gekopieerd" : "Mislukt";
      setTimeout(() => (copyBtn.textContent = "Kopieer"), 1200);
    });
  }

  // Copy (mobile)
  if (copyBtnMobile) {
    copyBtnMobile.addEventListener("click", async () => {
      const ok = await copyText(webcalUrl || httpsUrl);
      copyBtnMobile.textContent = ok ? "Gekopieerd" : "Mislukt";
      setTimeout(() => (copyBtnMobile.textContent = "Kopieer link"), 1200);
    });
  }

  // Open agenda app (mobile)
  if (openAgendaBtn) {
    openAgendaBtn.addEventListener("click", () => {
      // webcal:// is het meest “agenda-app friendly”
      if (webcalUrl) {
        window.location.href = webcalUrl;
      } else if (httpsUrl) {
        window.location.href = httpsUrl;
      }
    });
  }
});