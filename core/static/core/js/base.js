const toggleBtn = document.getElementById('navToggle');
const panel = document.getElementById('navPanel');

if (toggleBtn && panel) {
  const open = () => {
    panel.hidden = false;
    panel.classList.add('open');
    toggleBtn.setAttribute('aria-expanded', 'true');
    toggleBtn.setAttribute('aria-label', 'Sluit navigatie');
  };
  const close = () => {
    panel.classList.remove('open');
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.setAttribute('aria-label', 'Open navigatie');
    setTimeout(() => { panel.hidden = true; }, 120);
  };
  const isOpen = () => toggleBtn.getAttribute('aria-expanded') === 'true';

  toggleBtn.addEventListener('click', () => { isOpen() ? close() : open(); });
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen()) close(); });
  document.addEventListener('click', (e) => {
    if (!isOpen()) return;
    const t = e.target;
    if (!panel.contains(t) && !toggleBtn.contains(t)) close();
  });
  panel.querySelectorAll('a,button').forEach(el => {
    el.addEventListener('click', () => { if (isOpen()) close(); });
  });
  const mq = window.matchMedia('(min-width: 901px)');
  mq.addEventListener('change', () => { if (mq.matches) close(); });
}
