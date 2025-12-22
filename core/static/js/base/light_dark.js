document.addEventListener('DOMContentLoaded', function () {
    const modeSwitches = document.querySelectorAll('.mode-switch-input');
    const htmlElement = document.documentElement;

    // Initialiseer checkbox status
    const currentTheme = localStorage.getItem('theme') || 'dark';
    modeSwitches.forEach(sw => {
        sw.checked = (currentTheme === 'light');
    });

    // Update meta tags bij laden
    updateMetaTags();

    modeSwitches.forEach(modeSwitch => {
        modeSwitch.addEventListener('change', function () {
            const newTheme = this.checked ? 'light' : 'dark';
            
            // Zet het attribuut op <html> (CSS doet de rest)
            htmlElement.setAttribute('data-theme', newTheme);
            
            // Sla op in localStorage
            localStorage.setItem('theme', newTheme);

            // Update de adresbalk kleur
            updateMetaTags();
        });
    });

    function updateMetaTags() {
        // 1. Zoek alle bestaande theme-color tags en verwijder ze
        // Dit dwingt de browser om de nieuwe tag die we zo maken te 'zien' als de enige waarheid
        const existingMetas = document.querySelectorAll('meta[name="theme-color"]');
        existingMetas.forEach(meta => meta.remove());

        // 2. Bepaal de juiste kleur uit CSS variabelen
        const htmlElement = document.documentElement;
        const isLogin = document.body.classList.contains('login-page');
        const variableName = isLogin ? '--theme-meta-login' : '--theme-meta-base';
        
        // Zorg dat we de berekende kleur echt te pakken hebben
        const themeColor = getComputedStyle(htmlElement).getPropertyValue(variableName).trim();

        // 3. Maak een gloednieuwe meta tag aan
        const newMeta = document.createElement('meta');
        newMeta.name = "theme-color";
        newMeta.content = themeColor;
        
        // Optioneel: voeg een ID toe voor de volgende ronde (hoeft niet per se met de querySelectorAll hierboven)
        newMeta.id = "meta-theme-color"; 
        
        document.getElementsByTagName('head')[0].appendChild(newMeta);
        
        // Debug log om in je console te checken of hij echt verandert
        console.log(`PWA Theme Color geüpdatet naar: ${themeColor}`);
    }
});