/* Bestand: static/js/medicatiebeoordeling/medicatiebeoordeling_create.js */

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
    // Let op: De titel 'Instructie:' staat al hardcoded in je HTML wrapper, 
    // dus die hoeft hier niet meer in de tekst.
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
        
        // Elementen ophalen
        const $wrapper = $('#instruction-wrapper'); // De container met de titel "Instructie:"
        const $content = $('#instruction-content'); // Het vakje voor de tekst
        
        // Maak de sleutel (bijv: "medimo_afdeling")
        const key = `${source}_${scope}`;

        if (instructions[key]) {
            // 1. Vul de tekst
            $content.html(instructions[key]);
            
            // 2. Toon de wrapper (inclusief titel) als deze nog verborgen is
            if ($wrapper.is(':hidden')) {
                $wrapper.slideDown(200);
            }
        } else {
            // Verberg de hele wrapper als er geen instructie is
            $wrapper.slideUp(200);
        }
    }

    // Luister naar wijzigingen op de dropdowns
    $('#id_source, #id_scope').on('change', updateInstruction);

    // Initialiseer direct bij laden pagina
    updateInstruction();

    // ==========================================
    // 3. TABEL FILTER (ZOEKFUNCTIE)
    // ==========================================
    $('#manageSearchInput').on('keyup', function() {
        const filter = $(this).val().toLowerCase();
        
        $('.manage-row').each(function() {
            const $row = $(this);
            const text = $row.text().toLowerCase();
            
            // Toggle laat de rij zien of verbergt hem op basis van de boolean
            $row.toggle(text.indexOf(filter) > -1);
        });
    });

});

// ==========================================
// 4. GLOBALE FUNCTIES (Voor onclick="" attributes)
// ==========================================

// We hangen deze aan window zodat de onclick in de HTML hem kan vinden
window.toggleEditRow = function(id) {
    const row = document.getElementById('edit-row-' + id);
    if (row) {
        // Toggle display style
        row.style.display = (row.style.display === 'none' || row.style.display === '') ? 'table-row' : 'none';
    }
};