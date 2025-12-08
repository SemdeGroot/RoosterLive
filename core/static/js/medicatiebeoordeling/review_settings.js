$(document).ready(function() {
    // Initialiseer bestaande velden
    initSelect2($('.atc-select'));
});

function initSelect2($element) {
    $element.select2({
        placeholder: 'Zoek ATC code of naam...',
        minimumInputLength: 2,
        closeOnSelect: false,
        width: '100%',
        language: {
            inputTooShort: function() { return "Typ min. 2 tekens..."; },
            searching: function() { return "Zoeken..."; },
            noResults: function() { return "Geen resultaten"; }
        },
        ajax: {
            url: "/medicatiebeoordeling/api/atc-lookup/",
            dataType: 'json',
            delay: 250,
            data: function (params) { return { q: params.term }; },
            processResults: function (data) { return { results: data.results }; },
            cache: true
        },
        templateResult: function(data) {
            if (data.loading || !data.id) return data.text;
            
            var currentSelection = $element.val() || [];
            
            // Check of item al gedekt is door ouder
            var coveredBy = currentSelection.find(function(sel) {
                return data.id.startsWith(sel) && data.id !== sel;
            });

            if (coveredBy) {
                return $(
                    '<span>' + data.text + '</span>' +
                    '<span class="atc-hierarchy-warning">Via ' + coveredBy + '</span>'
                );
            }
            return data.text;
        }
    });

    // ============================================================
    // LOGICA: KINDEREN VERWIJDEREN BIJ KIEZEN OUDER (FIXED)
    // ============================================================
    $element.on('select2:selecting', function(e) {
        var data = e.params.args.data; 
        var currentSelection = $element.val() || [];
        
        // 1. Ouder check
        var coveredBy = currentSelection.find(function(sel) {
            return data.id.startsWith(sel) && data.id !== sel;
        });

        if (coveredBy) {
            e.preventDefault(); 
            return; 
        }

        // 2. Kinder check
        var parentId = data.id;
        var childrenToRemove = [];

        $.each(currentSelection, function(index, value) {
            if (value.startsWith(parentId) && value !== parentId) {
                childrenToRemove.push(value);
            }
        });

        if (childrenToRemove.length > 0) {
            // Pauzeer selectie
            e.preventDefault();
            
            var msg = "Je kiest nu de hoofdgroep '" + data.text + "'.\n" +
                      "Hierdoor vervallen de specifiekere selecties (" + childrenToRemove.join(", ") + ").\n\n" +
                      "Klik OK om door te gaan.";

            if (confirm(msg)) {
                // Filter de kinderen eruit
                var newSelection = currentSelection.filter(function(val) {
                    return !childrenToRemove.includes(val);
                });
                
                // CRUCIALE FIX VOOR AJAX:
                // Omdat we preventDefault deden, bestaat de <option> nog niet in de DOM.
                // We moeten hem handmatig aanmaken, anders werkt .val() niet voor dit nieuwe item.
                if ($element.find("option[value='" + data.id + "']").length === 0) {
                    var newOption = new Option(data.text, data.id, true, true);
                    $element.append(newOption);
                }
                
                // Voeg de ouder toe aan de array
                newSelection.push(parentId);
                
                // Update Select2 en trigger change
                $element.val(newSelection).trigger('change');
                $element.select2('close');
            }
        }
    });

    // ============================================================
    // FIXES: BACKSPACE & PLACEHOLDER
    // ============================================================
    
    // We pakken de container die de input bevat (de selection container, niet de dropdown)
    var $selection = $element.data('select2').$selection;

    // Backspace preventie
    $selection.on('keydown', '.select2-search__field', function(e) {
        // Als toets Backspace (8) is EN veld is leeg
        if (e.which === 8 && $(this).val() === '') {
            // Stop Propagation voorkomt dat Select2 zijn interne 'remove last item' event triggert
            e.stopPropagation();
            return false;
        }
    });
    
    // Placeholder styling fix
    function fixPlaceholder() {
        var $input = $selection.find('.select2-search__field');
        $input.attr('placeholder', 'Zoek ATC code of naam...');
        // Min-width zorgt dat placeholder altijd past en niet afbreekt
        $input.css('min-width', '200px'); 
    }
    
    // Trigger placeholder fix bij events
    fixPlaceholder();
    $element.on('select2:select select2:unselect select2:open', fixPlaceholder);
}

function addNewRow() {
    const idx = Date.now();
    const template = document.getElementById('row-template').innerHTML;
    const newHtml = template.replace(/__idx__/g, idx);
    
    const $newRow = $(newHtml).hide();
    $('#questions-container').append($newRow);
    $newRow.fadeIn(300);
    
    initSelect2($newRow.find('.atc-select-new'));
}

function removeRow(idx) {
    if(confirm("Weet je het zeker?")) {
        $(`#row-${idx}`).fadeOut(200, function() { $(this).remove(); });
    }
}