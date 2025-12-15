/* core/static/js/nazendingen/nazendingen.js */

document.addEventListener("DOMContentLoaded", function () {
    
    /**
     * Format functie voor de resultatenlijst (Dropdown items).
     * Zorgt voor: "ZI: 12345678" (dikgedrukt) en daaronder de naam.
     */
    function formatRepo(repo) {
        if (repo.loading) {
            return repo.text;
        }

        // repo.id bevat het ZI nummer
        // repo.text bevat "ZI - Naam" string uit de backend, 
        // maar we splitsen het liever netjes als we de data los zouden hebben.
        // Omdat de backend nu "ZI - Naam" stuurt in 'text', parsen we het even simpel 
        // of we stylen de hele string. 
        
        // Optie A: We vertrouwen op de backend string "12345678 - Paracetamol"
        // We splitsen op ' - ' om ze los te stylen.
        const parts = repo.text.split(' - ');
        const zi = parts[0] || repo.id;
        // De rest is de naam (join voor het geval er nog streepjes in de naam zitten)
        const naam = parts.slice(1).join(' - ') || ''; 

        // HTML output voor in de dropdown
        var $container = $(
            "<div class='select2-result-repository clearfix'>" +
                "<div class='select2-result-repository__meta'>" +
                    "<div class='select2-result-repository__title' style='font-weight:700; color:#333; font-size:1.1em;'>" + 
                         "<span style='color:#666; font-size:0.8em; font-weight:normal;'>ZI:</span> " + zi + 
                    "</div>" +
                    "<div class='select2-result-repository__description' style='font-size:0.95em; color:#555; margin-top:2px;'>" + naam + "</div>" +
                "</div>" +
            "</div>"
        );

        return $container;
    }

    /**
     * Format functie voor het geselecteerde item (wat je ziet na klikken).
     * Hier houden we het simpel: "12345678 - Naam".
     */
    function formatRepoSelection(repo) {
        return repo.text || repo.id;
    }

    // 1. Configuratie object
    const select2AjaxConfig = {
        width: '100%',
        placeholder: "Typ ZI-nummer of naam...",
        allowClear: true,
        minimumInputLength: 2, 
        closeOnSelect: true, 
        language: {
            inputTooShort: function () { return "Typ min. 2 tekens..."; },
            searching: function () { return "Zoeken..."; },
            noResults: function () { return "Geen resultaten"; },
            errorLoading: function () { return "Resultaten konden niet worden geladen."; }
        },
        ajax: {
            url: '/api/voorraad-zoeken/', 
            dataType: 'json',
            delay: 250, 
            data: function (params) {
                return { q: params.term };
            },
            processResults: function (data) {
                return { results: data.results };
            },
            cache: true
        },
        // KOPPEL DE FORMAT FUNCTIES HIER:
        templateResult: formatRepo, 
        templateSelection: formatRepoSelection,
        escapeMarkup: function(m) { return m; } // Nodig om HTML te renderen
    };

    // 2. Initialiseer Select2 op het 'Toevoegen' formulier
    const addSelect = $('#id_voorraad_item');
    if (addSelect.length) {
        addSelect.select2(select2AjaxConfig);
    }

    // 3. Initialiseer Datum maskers
    document.querySelectorAll(".js-date").forEach(function (input) {
         IMask(input, {
            mask: 'd-m-Y',
            lazy: true,
            blocks: {
                d: { mask: IMask.MaskedRange, from: 1, to: 31, maxLength: 2 },
                m: { mask: IMask.MaskedRange, from: 1, to: 12, maxLength: 2 },
                Y: { mask: IMask.MaskedRange, from: 1900, to: 2100, maxLength: 4 }
            }
        });
    });

    // 4. Client-side filter tabel
    const filterInput = document.getElementById('filterInput');
    if(filterInput){
        filterInput.addEventListener('keyup', function() {
            const term = this.value.toLowerCase();
            document.querySelectorAll('#nazendingTable tbody tr.manage-row').forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        });
    }
});

// --- Toggle Functies ---

function toggleAddSection() {
    const section = document.getElementById('addSection');
    const btn = document.getElementById('toggleAddBtn');
    
    if (section.style.display === 'none') {
        section.style.display = 'block';
        btn.textContent = '- Annuleren';
        btn.classList.add('ghost'); 
    } else {
        section.style.display = 'none';
        btn.textContent = '+ Toevoegen';
        btn.classList.remove('ghost');
    }
}

function toggleEditRow(id) {
    const viewRow = document.getElementById('row-' + id);
    const editRow = document.getElementById('edit-row-' + id);
    
    if (editRow.style.display === 'none') {
        viewRow.style.display = 'none';
        editRow.style.display = 'table-row';
        
        const $select = $(editRow).find('.select2-edit');
        
        if (!$select.hasClass("select2-hidden-accessible")) {
            // We dupliceren de config maar voegen dropdownParent toe
            // Helaas kunnen we 'select2AjaxConfig' niet 1-op-1 gebruiken als we 
            // dropdownParent dynamisch moeten zetten.
            
            $select.select2({
                width: '100%',
                placeholder: "Kies medicijn...",
                minimumInputLength: 2,
                closeOnSelect: true,
                dropdownParent: $(editRow), // Cruciaal voor edits in tabel
                language: {
                    inputTooShort: function () { return "Typ min. 2 tekens..."; },
                    searching: function () { return "Zoeken..."; },
                    noResults: function () { return "Geen resultaten"; }
                },
                ajax: {
                    url: '/api/voorraad-zoeken/',
                    dataType: 'json',
                    delay: 250,
                    data: function (params) { return { q: params.term }; },
                    processResults: function (data) { return { results: data.results }; },
                    cache: true
                },
                // Ook hier de formatting functies
                templateResult: function(repo) {
                     if (repo.loading) return repo.text;
                     const parts = repo.text.split(' - ');
                     const zi = parts[0] || repo.id;
                     const naam = parts.slice(1).join(' - ') || ''; 
                     return $(
                        "<div class='select2-result-repository clearfix'>" +
                            "<div class='select2-result-repository__meta'>" +
                                "<div class='select2-result-repository__title' style='font-weight:700; color:#333;'>" + 
                                     "<span style='color:#666; font-weight:normal; font-size:0.9em;'>ZI:</span> " + zi + 
                                "</div>" +
                                "<div class='select2-result-repository__description' style='font-size:0.9em; color:#555;'>" + naam + "</div>" +
                            "</div>" +
                        "</div>"
                    );
                },
                templateSelection: function(repo) { return repo.text || repo.id; },
                escapeMarkup: function(m) { return m; }
            });
        }

    } else {
        viewRow.style.display = 'table-row';
        editRow.style.display = 'none';
    }
}