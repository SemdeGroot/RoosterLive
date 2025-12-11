// static/js/medicatiebeoordeling/review_settings.js
let reviewFormDirty = false;

$(document).ready(function () {
    const $form = $('#configForm');

    // 1) Initialiseer Select2 op bestaande velden
    initSelect2($('.atc-select'));

    // 2) Initialiseert alle bestaande vragen (inklapbaar, sync, data-attrs)
    initAllQuestionRows();

    // 3) Groepeer per categorie/subcategorie en sorteer op ATC-code
    groupQuestions();

    // 4) Zoekbalk
    initQuestionSearch();

    // 5) Dirty tracking: markeer formulier als gewijzigd bij input/select/textarea, behalve de zoekbalk
    if ($form.length) {
        $form.on('input change', 'input, select, textarea', function (e) {
            const $target = $(e.target);
            if ($target.is('#question-search')) {
                return; // zoekbalk telt niet als wijziging
            }
            markReviewFormDirty();
        });

        // Bij submit: niet meer dirty, geen waarschuwing
        $form.on('submit', function () {
            reviewFormDirty = false;
            window.onbeforeunload = null;
        });
    }

});

/**
 * Markeer het formulier als "dirty" (onopgeslagen wijzigingen).
 */
function markReviewFormDirty() {
    if (!reviewFormDirty) {
        reviewFormDirty = true;
        // Zorg dat de browser een waarschuwing toont bij verlaten
        window.onbeforeunload = function (e) {
            e.preventDefault();
            e.returnValue = 'Je hebt niet opgeslagen wijzigingen. Weet je zeker dat je deze pagina wilt verlaten?';
        };
    }
}

/**
 * Hoofdfunctie voor Select2 initialisatie.
 */
function initSelect2($elements) {
    $elements.each(function() {
        var $el = $(this);
        
        var limitLen = $el.data('atc-len'); 
        var isMultiple = $el.prop('multiple');

        $el.select2({
            placeholder: 'Zoek ATC code of naam...',
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
                        len: limitLen
                    }; 
                },
                processResults: function (data) { return { results: data.results }; },
                cache: true
            },
            templateResult: function (data) {
                if (data.loading || !data.id) return data.text;

                if (!isMultiple) {
                    return data.text;
                }

                var currentSelection = $el.val() || [];
                if (!Array.isArray(currentSelection)) {
                    currentSelection = [currentSelection];
                }

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
        // LOGICA: KINDEREN VERWIJDEREN BIJ KIEZEN OUDER (alleen multiple)
        // ============================================================
        $el.on('select2:selecting', function (e) {
            if (!isMultiple) return;

            var data = e.params.args.data;
            var currentSelection = $el.val() || [];

            if (!Array.isArray(currentSelection)) {
                currentSelection = [currentSelection];
            }

            var coveredBy = currentSelection.find(function (sel) {
                return data.id.startsWith(sel) && data.id !== sel;
            });

            if (coveredBy) {
                e.preventDefault();
                return;
            }

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
 * Initialiseert alle bestaande vragen.
 */
function initAllQuestionRows() {
    const $rows = $('.question-row');
    $rows.each(function () {
        initSingleQuestionRow($(this));
    });
}

/**
 * Initialiseert één vraag:
 * - header klikbaar (inklappen/uitklappen)
 * - titel + meldingstekst in header syncen met inputs
 * - categorie/subcategorie data-attributen bijwerken
 */
function initSingleQuestionRow($row) {
    const $header = $row.find('[data-question-toggle]');
    const $body   = $row.find('[data-question-body]');

    if ($header.length && $body.length) {
        $header.off('.questionToggle');

        function toggleRow() {
            const isHidden = $body.hasClass('is-hidden');
            $body.toggleClass('is-hidden', !isHidden);
            $row.toggleClass('question-row--expanded', isHidden);
            const $icon = $header.find('.question-toggle-icon');
            if ($icon.length) {
                $icon.text(isHidden ? '▴' : '▾');
            }
        }

        $header.on('click.questionToggle', function (event) {
            // Klik op delete-knop → NIET togglen
            if ($(event.target).closest('.question-delete-btn').length) return;
            toggleRow();
        });

        $header.on('keydown.questionToggle', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleRow();
            }
        });
    }

    // Sync titel in header
    const $titleInput = $row.find('.js-title-input');
    const $titleLabel = $row.find('[data-title-overview]');
    function updateTitleLabel() {
        if ($titleLabel.length && $titleInput.length) {
            const val = $titleInput.val().trim();
            $titleLabel.text(val || '(zonder titel)');
        }
    }
    updateTitleLabel();
    if ($titleInput.length) {
        $titleInput.off('.titleSync').on('input.titleSync', function () {
            updateTitleLabel();
            applySearchFilter();
        });
    }

    // Sync meldingstekst in header
    const $descInput = $row.find('.js-description-input');
    const $descLabel = $row.find('[data-description-overview]');
    function updateDescLabel() {
        if ($descLabel.length && $descInput.length) {
            const val = $descInput.val().trim();
            $descLabel.text(val);
        }
    }
    updateDescLabel();
    if ($descInput.length) {
        $descInput.off('.descSync').on('input.descSync', function () {
            updateDescLabel();
            applySearchFilter();
        });
    }

    // Sync categorie/subcategorie data-attributen (voor grouping)
    const $catSelect  = $row.find('.js-category-select');
    const $subSelect  = $row.find('.js-subcategory-select');

    function updateCategoryData() {
        if ($catSelect.length) {
            const text = $catSelect.find('option:selected').text().trim() || 'Zonder categorie';
            const val  = $catSelect.val() || '';
            $row.attr('data-category-id', val);
            $row.attr('data-category-label', text);
        }
    }

    function updateSubcategoryData() {
        if ($subSelect.length) {
            const text = $subSelect.find('option:selected').text().trim() || 'Zonder subcategorie';
            const val  = $subSelect.val() || '';
            $row.attr('data-subcategory-id', val);
            $row.attr('data-subcategory-label', text);
        }
    }

    updateCategoryData();
    updateSubcategoryData();

    if ($catSelect.length) {
        $catSelect.off('.catSync').on('change.catSync', function () {
            updateCategoryData();
            groupQuestions();
        });
    }

    if ($subSelect.length) {
        $subSelect.off('.subSync').on('change.subSync', function () {
            updateSubcategoryData();
            groupQuestions();
        });
    }
}

/**
 * Groepeert alle questions per categorie en subcategorie,
 * en sorteert op ATC-code (categorie: ATC1, subcategorie: ATC3).
 */
function groupQuestions() {
    const $container = $('#questions-container');
    if (!$container.length) return;

    const $rows = $container.find('.question-row').detach();
    $container.empty();

    const categories = {}; // catKey -> { id, label, subgroups: { subKey -> { id, label, rows: [] } } }

    $rows.each(function () {
        const $row = $(this);
        const rawCatId  = $row.attr('data-category-id') || '';
        const rawSubId  = $row.attr('data-subcategory-id') || '';
        const catLabel  = $row.attr('data-category-label') || 'Zonder categorie';
        const subLabel  = $row.attr('data-subcategory-label') || 'Zonder subcategorie';

        // fallback key voor lege codes zodat die achteraan komen
        const catKey = rawCatId || 'ZZZ_NONE_CAT';
        const subKey = rawSubId || 'ZZZ_NONE_SUB';

        if (!categories[catKey]) {
            categories[catKey] = {
                id: rawCatId,
                label: catLabel,
                subgroups: {}
            };
        }
        if (!categories[catKey].subgroups[subKey]) {
            categories[catKey].subgroups[subKey] = {
                id: rawSubId,
                label: subLabel,
                rows: []
            };
        }
        categories[catKey].subgroups[subKey].rows.push($row);
    });

    // Sorteer categorieën alfabetisch op ATC-code
    const catKeys = Object.keys(categories).sort();

    catKeys.forEach(function (catKey) {
        const cat = categories[catKey];

        const $group = $('<div class="question-group"></div>');
        const $header = $('<div class="question-group-header"></div>');
        const $hCat = $('<h3 class="question-group-category"></h3>').text(cat.label);
        $header.append($hCat);
        $group.append($header);

        const $catContent = $('<div class="question-group-category-content"></div>');

        // Sorteer subcategorieën alfabetisch op ATC3
        const subKeys = Object.keys(cat.subgroups).sort();
        subKeys.forEach(function (subKey) {
            const sub = cat.subgroups[subKey];

            const $subgroup = $('<div class="question-subgroup"></div>');
            const $hSub = $('<h4 class="question-group-subcategory"></h4>').text(sub.label);
            const $list = $('<div class="question-group-list"></div>');

            sub.rows.forEach(function ($row) {
                $list.append($row);
            });

            $subgroup.append($hSub).append($list);
            $catContent.append($subgroup);
        });

        $group.append($catContent);
        $container.append($group);
    });

    // Na hergroeperen: filter opnieuw toepassen
    applySearchFilter();
}

/**
 * Filterfunctie: zoekt op titel + meldingstekst.
 * Lege query → alles tonen.
 */
function applySearchFilter() {
    const $search = $('#question-search');
    const queryRaw = $search.length ? $search.val() : '';
    const query = (queryRaw || '').toLowerCase().trim();

    if (!query) {
        $('#questions-container .question-row').show();
        $('#questions-container .question-subgroup').show();
        $('#questions-container .question-group').show();
        return;
    }

    // Filter rows op titel + description
    $('#questions-container .question-row').each(function () {
        const $row = $(this);
        const $titleInput = $row.find('.js-title-input');
        const $descInput  = $row.find('.js-description-input');

        const title = $titleInput.length ? ($titleInput.val() || '').toLowerCase() : '';
        const desc  = $descInput.length  ? ($descInput.val()  || '').toLowerCase() : '';

        const match = title.includes(query) || desc.includes(query);
        $row.toggle(match);
    });

    // Subgroepen zonder zichtbare vragen verbergen
    $('#questions-container .question-subgroup').each(function () {
        const $sub = $(this);
        const hasVisibleRow = $sub.find('.question-row:visible').length > 0;
        $sub.toggle(hasVisibleRow);
    });

    // Categorieën zonder zichtbare vragen verbergen
    $('#questions-container .question-group').each(function () {
        const $group = $(this);
        const hasVisibleRow = $group.find('.question-row:visible').length > 0;
        $group.toggle(hasVisibleRow);
    });
}

/**
 * Live zoeken op titel + meldingstekst.
 * Enter moet niets doen (geen submit).
 */
function initQuestionSearch() {
    const $search = $('#question-search');
    if (!$search.length) return;

    $search.on('input', function () {
        applySearchFilter();
    });

    $search.on('keydown', function (event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            return false;
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

    // Inklapbare UI + data-attributen
    initSingleQuestionRow($newNode);

    // Markeer als dirty: een nieuwe vraag is een wijziging
    markReviewFormDirty();

    // Opnieuw groeperen (nieuwe vraag komt in de juiste ATC-groep terecht)
    groupQuestions();
}

/**
 * Voegt een logica regel toe (AND of AND_NOT).
 */
function addRule(qId, type, animate) {
    if (typeof animate === 'undefined') animate = true;

    const rId = Math.floor(Math.random() * 1000000);
    const tplId = type === 'AND' ? 'tpl-rule-AND' : 'tpl-rule-AND_NOT';
    
    let html = document.getElementById(tplId).innerHTML;
    html = html.replace(/__QID__/g, qId).replace(/__RID__/g, rId);
    
    const $container = $(`#container-${type}-${qId}`);
    const $newNode = $(html);
    
    if (animate) $newNode.hide();
    $container.append($newNode);
    if (animate) $newNode.slideDown(200);

    const $select = $newNode.find('.atc-select-init');
    initSelect2($select);
    $select.removeClass('atc-select-init').addClass('atc-select');

    // Logica toevoegen is ook een wijziging
    markReviewFormDirty();
}

/**
 * Verwijdert een hele vraag.
 */
function removeRow(id) {
    if(confirm("Weet je zeker dat je deze vraag wilt verwijderen?")) {
        $(`#row-${id}`).slideUp(200, function(){
            $(this).remove();
            groupQuestions();
            markReviewFormDirty();
        });
    }
}

/**
 * Verwijdert een logica-regel.
 */
function removeRule(qId, rId) {
    $(`#rule-${qId}-${rId}`).slideUp(200, function(){ 
        $(this).remove(); 
        markReviewFormDirty();
    });
}