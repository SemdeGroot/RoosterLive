document.addEventListener('DOMContentLoaded', function () {
    const modeSwitches = document.querySelectorAll('.mode-switch-input');
    const htmlElement = document.documentElement;

    // 1. Initialiseer checkbox status bij laden
    // (Het thema zelf is al gezet door het script in de <head>)
    const currentTheme = localStorage.getItem('theme') || 'dark';
    modeSwitches.forEach(sw => {
        sw.checked = (currentTheme === 'light');
    });

    // 2. Event listeners voor de switches
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
     * We gebruiken hardcoded waardes die matchen met je CSS variabelen 
     * om vertraging door 'getComputedStyle' te voorkomen.
     */
    function updateMetaTags(theme) {
        let meta = document.getElementById('meta-theme-color');
        
        // Mocht de meta tag niet bestaan, maak hem aan
        if (!meta) {
            meta = document.createElement('meta');
            meta.id = 'meta-theme-color';
            meta.name = 'theme-color';
            document.head.appendChild(meta);
        }

        // Bepaal de kleur op basis van thema en pagina type
        const isLogin = document.body.classList.contains('login-page');
        let themeColor;

        if (theme === 'dark') {
            themeColor = isLogin ? '#131a24' : '#131a24'; // Pas aan indien login anders moet zijn
        } else {
            themeColor = isLogin ? '#E3E8F0' : '#E3E8F0'; // Pas aan indien login anders moet zijn
        }

        meta.setAttribute('content', themeColor);
    }
});