document.addEventListener('DOMContentLoaded', function () {
    const modeSwitches = document.querySelectorAll('.mode-switch-input');
    const htmlElement = document.documentElement;

    // STAP 1 (Initialisatie) IS VERWIJDERD: 
    // Dit wordt nu afgehandeld door de MutationObserver in de <head>

    // 1. Event listeners voor de switches (interactie)
    modeSwitches.forEach(modeSwitch => {
        modeSwitch.addEventListener('change', function () {
            const isChecked = this.checked;
            const newTheme = isChecked ? 'light' : 'dark';
            
            // Synchroniseer alle switches op de pagina (bijv. mobiel en desktop menu)
            modeSwitches.forEach(sw => {
                if (sw !== this) sw.checked = isChecked;
            });

            // Update HTML attribuut en LocalStorage
            htmlElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            // Update de adresbalk kleur direct
            updateMetaTags(newTheme);
        });
    });

    /**
     * Past de theme-color meta tag aan.
     */
    function updateMetaTags(theme) {
        let meta = document.getElementById('meta-theme-color');
        
        if (!meta) {
            meta = document.createElement('meta');
            meta.id = 'meta-theme-color';
            meta.name = 'theme-color';
            document.head.appendChild(meta);
        }

        const isLogin = document.body.classList.contains('login-page');
        let themeColor;

        if (theme === 'dark') {
            themeColor = '#131a24'; 
        } else {
            themeColor = '#E3E8F0';
        }

        meta.setAttribute('content', themeColor);
    }
});