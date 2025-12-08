$(document).ready(function() {
    // Initialiseer op bestaande velden
    initSelect2($('.atc-select'));
});

function initSelect2($element) {
    $element.select2({
        placeholder: 'Zoek ATC code of naam...',
        minimumInputLength: 2,
        closeOnSelect: false, // BELANGRIJK: Dropdown blijft open!
        width: '100%',
        language: {
            inputTooShort: function() { return "Typ min. 2 tekens..."; },
            searching: function() { return "Zoeken..."; },
            noResults: function() { return "Geen resultaten"; }
        },
        ajax: {
            url: "/medicatiebeoordeling/api/atc-lookup/", // Check je URLS.py
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return { q: params.term };
            },
            processResults: function (data) {
                return { results: data.results };
            },
            cache: true
        }
    });
}

function addNewRow() {
    const idx = Date.now();
    const template = document.getElementById('row-template').innerHTML;
    const newHtml = template.replace(/__idx__/g, idx);
    
    const $newRow = $(newHtml).hide();
    $('#questions-container').append($newRow);
    $newRow.fadeIn(300);
    
    // Initialiseer select2 in de nieuwe rij
    initSelect2($newRow.find('.atc-select-new'));
}

function removeRow(idx) {
    if(confirm("Weet je het zeker?")) {
        $(`#row-${idx}`).fadeOut(200, function() { $(this).remove(); });
    }
}