document.addEventListener('DOMContentLoaded', function () {
    const modeSwitches = document.querySelectorAll('.mode-switch-input');
    const htmlElement = document.documentElement;

    // 1. Initialiseer checkbox status voor ALLE switches
    const currentTheme = localStorage.getItem('theme') || 'dark';
    modeSwitches.forEach(sw => {
        sw.checked = (currentTheme === 'light');
    });

    // Update meta tags bij laden
    updateMetaTags();

    modeSwitches.forEach(modeSwitch => {
        modeSwitch.addEventListener('change', function () {
            const isChecked = this.checked;
            const newTheme = isChecked ? 'light' : 'dark';
            
            // SYNCHRONISATIE: Zet alle andere switches ook op dezelfde status
            modeSwitches.forEach(sw => {
                if (sw !== this) sw.checked = isChecked;
            });

            // Zet het attribuut op <html>
            htmlElement.setAttribute('data-theme', newTheme);
            
            // Sla op in localStorage
            localStorage.setItem('theme', newTheme);

            // Update de adresbalk kleur
            updateMetaTags();
        });
    });

    function updateMetaTags() {
        // Verwijder oude meta tags
        const existingMetas = document.querySelectorAll('meta[name="theme-color"]');
        existingMetas.forEach(meta => meta.remove());

        // Bepaal de juiste kleur uit CSS variabelen
        const isLogin = document.body.classList.contains('login-page');
        const variableName = isLogin ? '--theme-meta-login' : '--theme-meta-base';
        
        // Gebruik een kleine timeout om de browser de kans te geven de CSS variabelen 
        // van het nieuwe thema eerst te berekenen
        setTimeout(() => {
            const themeColor = getComputedStyle(htmlElement).getPropertyValue(variableName).trim();

            if (themeColor) {
                const newMeta = document.createElement('meta');
                newMeta.name = "theme-color";
                newMeta.content = themeColor;
                newMeta.id = "meta-theme-color"; 
                document.head.appendChild(newMeta);
            }
        }, 50);
    }
});