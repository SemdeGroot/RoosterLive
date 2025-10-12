const toggleBtn = document.getElementById('navToggle');
const panel = document.getElementById('navPanel');
const overlay = document.getElementById('navOverlay');
const closeBtn = document.getElementById('navClose');

if (toggleBtn && panel && overlay) {
    // Voorkom scrollen van body wanneer menu open is
    const preventScroll = () => { document.body.style.overflow = 'hidden'; };
    const allowScroll = () => { document.body.style.overflow = ''; };

    const open = () => {
        panel.hidden = false;
        overlay.classList.add('active');
        requestAnimationFrame(() => { panel.classList.add('open'); });
        toggleBtn.setAttribute('aria-expanded', 'true');
        toggleBtn.setAttribute('aria-label', 'Sluit navigatie');
        preventScroll();

        // VERWIJDERD: geen auto-focus op eerste link om blauwe outline te voorkomen
        // const firstLink = panel.querySelector('.nav-link');
        // if (firstLink) setTimeout(() => firstLink.focus(), 250);
    };

    const close = () => {
        panel.classList.remove('open');
        overlay.classList.remove('active');
        toggleBtn.setAttribute('aria-expanded', 'false');
        toggleBtn.setAttribute('aria-label', 'Open navigatie');
        allowScroll();
        setTimeout(() => { panel.hidden = true; }, 250);
    };

    const isOpen = () => toggleBtn.getAttribute('aria-expanded') === 'true';

    toggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        isOpen() ? close() : open();
    });

    if (closeBtn) closeBtn.addEventListener('click', close);

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen()) {
            close();
            toggleBtn.focus();
        }
    });

    overlay.addEventListener('click', close);

    document.addEventListener('click', (e) => {
        if (!isOpen()) return;
        if (!panel.contains(e.target) && !toggleBtn.contains(e.target)) close();
    });

    panel.querySelectorAll('.nav-link').forEach(el => {
        el.addEventListener('click', () => { if (isOpen()) close(); });
    });

    const mq = window.matchMedia('(min-width: 901px)');
    mq.addEventListener('change', (e) => { if (e.matches && isOpen()) close(); });

    // Focus trap blijft: (laat staan voor toegankelijkheid)
    panel.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab' || !isOpen()) return;
        const focusableElements = panel.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        if (!firstElement || !lastElement) return;

        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    });
}