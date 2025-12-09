$(document).ready(function () {
    // Initialiseer bestaande velden bij het laden van de pagina
    initSelect2($('.atc-select'));
});

/**
 * Hoofdfunctie voor Select2 initialisatie.
 * Bevat logic voor: AJAX, Hierarchy Check, Parent/Child conflict, Backspace fix.
 */
function initSelect2($elements) {
    $elements.each(function() {
        var $el = $(this);
        
        // Haal restrictie op (1, 3 of undefined)
        // Dit is nieuw toegevoegd aan jouw oude logica
        var limitLen = $el.data('atc-len'); 

        $el.select2({
            placeholder: 'Zoek ATC code of naam...',
            // Als ATC1 (len=1), mag je direct zoeken (0 chars), anders min. 2
            minimumInputLength: limitLen === 1 ? 0 : 2,
            closeOnSelect: false,
            width: '100%',
            language: {
                inputTooShort: function () { return "Typ min. 2 tekens..."; },
                searching: function () { return "Zoeken..."; },
                noResults: function () { return "Geen resultaten"; }
            },
            ajax: {
                url: "/medicatiebeoordeling/api/atc-lookup/",
                dataType: 'json',
                delay: 250,
                data: function (params) { 
                    return { 
                        q: params.term,
                        len: limitLen // Stuur parameter mee naar backend
                    }; 
                },
                processResults: function (data) { return { results: data.results }; },
                cache: true
            },
            templateResult: function (data) {
                if (data.loading || !data.id) return data.text;

                var currentSelection = $el.val() || [];

                // Check of item al gedekt is door ouder
                var coveredBy = currentSelection.find(function (sel) {
                    return data.id.startsWith(sel) && data.id !== sel;
                });

                if (coveredBy) {
                    return $(
                        '<span>' + data.text + '</span>' +
                        '<span class="atc-hierarchy-warning">Al geïncludeerd via ' + coveredBy + '</span>'
                    );
                }
                return data.text;
            }
        });

        // ============================================================
        // LOGICA: KINDEREN VERWIJDEREN BIJ KIEZEN OUDER
        // ============================================================
        $el.on('select2:selecting', function (e) {
            var data = e.params.args.data;
            var currentSelection = $el.val() || [];

            // 1. Ouder check: Als we een kind kiezen dat al gedekt is door een ouder
            var coveredBy = currentSelection.find(function (sel) {
                return data.id.startsWith(sel) && data.id !== sel;
            });

            if (coveredBy) {
                e.preventDefault();
                return;
            }

            // 2. Kinder check: Als we een ouder kiezen die kinderen overbodig maakt
            var parentId = String(data.id);
            var childrenToRemove = [];

            $.each(currentSelection, function (index, value) {
                if (value.startsWith(parentId) && value !== parentId) {
                    childrenToRemove.push(value);
                }
            });

            if (childrenToRemove.length > 0) {
                e.preventDefault();
                var msg = "Je kiest nu de hoofdgroep '" + data.text + "'.\n" +
                    "Hierdoor vervallen de specifiekere selecties (" + childrenToRemove.join(", ") + ").\n\n" +
                    "Klik OK om door te gaan.";

                setTimeout(function () {
                    if (confirm(msg)) {
                        var newSelection = currentSelection.filter(function (val) {
                            return !childrenToRemove.includes(val);
                        });

                        // Zorg dat de optie bestaat
                        if ($el.find("option[value='" + parentId + "']").length === 0) {
                            var newOption = new Option(data.text, parentId, true, true);
                            $el.append(newOption);
                        }

                        if (!newSelection.includes(parentId)) {
                            newSelection.push(parentId);
                        }

                        $el.val(newSelection).trigger('change');
                        $el.select2('close');
                    }
                }, 0);
            }
        });

        // ============================================================
        // FIXES: BACKSPACE & PLACEHOLDER
        // ============================================================
        // Check of select2 data beschikbaar is (voor veiligheid)
        if ($el.data('select2')) {
            var $selection = $el.data('select2').$selection;

            $selection.on('keydown', '.select2-search__field', function (e) {
                if (e.which === 8 && $(this).val() === '') {
                    e.stopPropagation();
                    return false;
                }
            });

            function fixPlaceholder() {
                var $input = $selection.find('.select2-search__field');
                // Pas placeholder aan op basis van type
                var txt = limitLen ? 'Zoek...' : 'Zoek ATC code of naam...';
                $input.attr('placeholder', txt);
                $input.css('min-width', '150px');
            }

            fixPlaceholder();
            $el.on('select2:select select2:unselect select2:open', fixPlaceholder);
        }
    });
}

/**
 * Voegt een nieuwe Vraag toe aan de pagina.
 */
function addNewQuestion() {
    const qId = Date.now();
    let html = document.getElementById('tpl-question').innerHTML;
    html = html.replace(/__QID__/g, qId);
    
    const $newNode = $(html).hide();
    $('#questions-container').append($newNode);
    $newNode.fadeIn(300);
    
    // Initialiseer Select2 op de nieuwe elementen
    const $selects = $newNode.find('.atc-select-init');
    initSelect2($selects);
    $selects.removeClass('atc-select-init').addClass('atc-select');

    // Voeg direct de standaard regels toe (AND en NOT)
    addRule(qId, 'AND', false);
    addRule(qId, 'AND_NOT', false);
}

/**
 * Voegt een logica regel toe (AND of AND_NOT).
 */
function addRule(qId, type, animate=true) {
    const rId = Math.floor(Math.random() * 1000000);
    const tplId = type === 'AND' ? 'tpl-rule-AND' : 'tpl-rule-AND_NOT';
    
    let html = document.getElementById(tplId).innerHTML;
    html = html.replace(/__QID__/g, qId).replace(/__RID__/g, rId);
    
    const $container = $(`#container-${type}-${qId}`);
    const $newNode = $(html);
    
    if (animate) $newNode.hide();
    $container.append($newNode);
    if (animate) $newNode.slideDown(200);

    // Initialiseer Select2
    const $select = $newNode.find('.atc-select-init');
    initSelect2($select);
    $select.removeClass('atc-select-init').addClass('atc-select');
}

function removeRow(id) {
    if(confirm("Weet je zeker dat je deze vraag wilt verwijderen?")) {
        $(`#row-${id}`).slideUp(200, function(){ $(this).remove(); });
    }
}

function removeRule(qId, rId) {
    $(`#rule-${qId}-${rId}`).slideUp(200, function(){ $(this).remove(); });
}