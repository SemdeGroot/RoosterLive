// Bestand: static/js/medicatiebeoordeling/medicatiebeoordeling_create.js

$(document).ready(function() {
    
    // ==========================================
    // 1. SELECT2 INITIALISATIE
    // ==========================================
    const $select = $('.django-select2').select2({
        placeholder: "Klik om een afdeling te zoeken...",
        allowClear: true,
        width: '100%'
    });

    // Zorg dat de focus direct in het zoekveld komt bij openen
    $select.on('select2:open', function() {
        const searchField = document.querySelector('.select2-search__field');
        if (searchField) {
            searchField.placeholder = "Typ om te zoeken..."; 
            searchField.focus();
        }
    });

    // ==========================================
    // 2. DYNAMISCHE INSTRUCTIES (Source & Scope)
    // ==========================================
    
    // Definieer hier de teksten. 
    const instructions = {
        'medimo_afdeling': `
            1. Controleer rechtsboven of de juiste zorginstelling geselecteerd is.<br>
            2. Ga naar <em>Alle overzichten</em> en kies <em>Overzicht medicatie patiënt</em>.<br>
            3. Selecteer de gewenste afdeling.<br>
            4. Selecteer en kopieer alles vanaf de kop <em>Overzicht medicatie Afdeling</em> tot en met de laatste medicatieregel.<br>
            5. Plak de tekst in het vak hieronder en start de analyse.
        `,
        'medimo_patient': `
            1. Controleer rechtsboven of de juiste zorginstelling is geselecteerd.<br>
            2. Zoek rechtsboven de patiënt die je wilt beoordelen.<br>
            3. Vul hierboven de afdeling in die onder de naam van de patiënt staat.<br>
            4. Kopieer de gegevens door op de knop <em>Medicatie</em> te klikken.<br>
            5. Plak het overzicht in het tekstvak hieronder.
        `
    };

    function updateInstruction() {
        const source = $('#id_source').val(); 
        const scope = $('#id_scope').val();
        
        const $wrapper = $('#instruction-wrapper'); 
        const $content = $('#instruction-content'); 
        
        const key = `${source}_${scope}`;

        if (instructions[key]) {
            $content.html(instructions[key]);
            if ($wrapper.is(':hidden')) {
                $wrapper.slideDown(200);
            }
        } else {
            $wrapper.slideUp(200);
        }
    }

    $('#id_source, #id_scope').on('change', updateInstruction);
    updateInstruction();

    // ==========================================
    // 3. TABEL FILTER (ZOEKFUNCTIE)
    // ==========================================
    $('#manageSearchInput').on('keyup', function() {
        const filter = $(this).val().toLowerCase();
        
        $('.manage-row').each(function() {
            const $row = $(this);
            const text = $row.text().toLowerCase();
            $row.toggle(text.indexOf(filter) > -1);
        });
    });

    // ==========================================
    // 5. REVIEW LOADING OVERLAY (Start Analyse)
    // ==========================================
    // Alleen voor het formulier dat de medicatiereview start
    const $reviewForm = $('form').filter(function() {
        return $(this).find('input[name="btn_start_review"]').length > 0;
    });

    if ($reviewForm.length) {
        $reviewForm.on('submit', function() {
            const $overlay = $('#review-loading-overlay');
            if (!$overlay.length) return;

            // Basis state
            $('#review-loading-main').text('Container opstarten...');
            $overlay.removeClass('is-long-wait').addClass('is-visible');

            // Oude timers opruimen (voor het geval van back/forward nav)
            if (window.reviewLoadingTimers && window.reviewLoadingTimers.length) {
                window.reviewLoadingTimers.forEach(function(id) { clearTimeout(id); });
            }
            window.reviewLoadingTimers = [];

            // Na 5 seconden: andere tekst
            window.reviewLoadingTimers.push(
                setTimeout(function() {
                    $('#review-loading-main').text('Medicatiereview uitvoeren...');
                }, 5000)
            );

            // Na 20 seconden: overlay een subtiel "lange wachttijd" accent geven
            window.reviewLoadingTimers.push(
                setTimeout(function() {
                    $overlay.addClass('is-long-wait');
                }, 20000)
            );

            // Geen preventDefault: formulier mag normaal submitten
            // De overlay blijft zichtbaar totdat de server response terug is
        });
    }

});

// ==========================================
// 4. GLOBALE FUNCTIES (Voor onclick="" attributes)
// ==========================================

window.toggleEditRow = function(id) {
    const row = document.getElementById('edit-row-' + id);
    if (row) {
        row.style.display = (row.style.display === 'none' || row.style.display === '') ? 'table-row' : 'none';
    }
};