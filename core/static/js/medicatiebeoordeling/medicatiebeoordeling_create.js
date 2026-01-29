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
    const instructions = {
        'medimo_afdeling': `
        1. Controleer rechtsboven of de juiste zorginstelling geselecteerd is.<br>
        2. Ga naar <em>Alle overzichten</em> en kies <em>Overzicht medicatie patiënt/bewoner/cliënt/gebruiker</em> (verschilt per organisatie).<br>
        3. Selecteer de gewenste afdeling.<br>
        4. Selecteer en kopieer alles vanaf de kop <em>Overzicht medicatie Afdeling</em> t/m de laatste medicatieregel.
            <strong>Let op:</strong> als je niet het volledige overzicht van de hele afdeling kopieert, kan er data verloren gaan. Het systeem verwijdert namelijk patiënten die niet meer in het overzicht staan.
            Wil je slechts één patiënt beoordelen? Kies dan <em>Individueel</em> bij <em>Type Review</em> in het formulier.<br>
        5. Plak de tekst in het vak hieronder en start de analyse.
        `,
        'medimo_patient': `
        1. Controleer rechtsboven of de juiste zorginstelling geselecteerd is.<br>
        2. Zoek rechtsboven de patiënt die je wilt beoordelen.<br>
        3. Selecteer hierboven de afdeling die onder de naam van de patiënt staat.<br>
        4. Vul de naam en geboortedatum van de patiënt exact in zoals in Medimo.<br>
        5. Kopieer de gegevens door op de knop <em>Medicatie</em> te klikken.<br>
        6. Plak het overzicht in het tekstvak hieronder en start de analyse.
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
    // 3. SINGLE PATIENT: SHOW/HIDE EXTRA FIELDS
    // ==========================================
    function toggleSinglePatientFields() {
        const scope = $('#id_scope').val();
        const $block = $('#single-patient-fields');

        if (scope === 'patient') {
            $block.slideDown(200);
        } else {
            $block.slideUp(200);
            // optioneel: velden leegmaken als je terugschakelt
            $('#id_patient').val('');
            $('#id_patient_geboortedatum').val('');
        }
    }

    $('#id_scope').on('change', toggleSinglePatientFields);
    toggleSinglePatientFields();

    // ==========================================
    // 4. IMASK: GEBOORTEDATUM (dd-mm-jjjj) agenda-style + min/max
    // ==========================================
    (function () {
    const dobEl = document.getElementById('id_patient_geboortedatum');
    if (!dobEl || !window.IMask) return;

    // placeholder komt uit HTML; hier alleen als fallback
    if (!dobEl.getAttribute('placeholder')) {
        dobEl.setAttribute('placeholder', 'dd-mm-jjjj');
    }

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const minYear = 1900;
    const maxYear = today.getFullYear();

    const dobMask = IMask(dobEl, {
        mask: 'd-m-Y',
        lazy: true,        // geen underscores
        overwrite: true,
        autofix: false,    // agenda gebruikt false; ranges blokkeren al veel
        blocks: {
        d: { mask: IMask.MaskedRange, from: 1, to: 31, maxLength: 2 },
        m: { mask: IMask.MaskedRange, from: 1, to: 12, maxLength: 2 },
        Y: { mask: IMask.MaskedRange, from: minYear, to: maxYear, maxLength: 4 }
        }
    });

    function parseDMY(value) {
        const parts = (value || '').split('-');
        if (parts.length !== 3) return null;

        const dd = parseInt(parts[0], 10);
        const mm = parseInt(parts[1], 10);
        const yyyy = parseInt(parts[2], 10);

        if (!dd || !mm || !yyyy) return null;
        if (yyyy < minYear || yyyy > maxYear) return null;

        // echte kalenderdatum check (31-02 mag niet)
        const d = new Date(yyyy, mm - 1, dd);
        if (
        d.getFullYear() !== yyyy ||
        d.getMonth() !== (mm - 1) ||
        d.getDate() !== dd
        ) return null;

        // niet in de toekomst
        const dateOnly = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        if (dateOnly > today) return null;

        return dateOnly;
    }

    function setInvalid(isInvalid) {
        dobEl.classList.toggle('is-invalid', !!isInvalid);
    }

    // Blur = valideren
    dobEl.addEventListener('blur', function () {
        const v = dobEl.value.trim();

        // als dit veld optioneel is: leeg is ok
        if (!v) return setInvalid(false);

        // IMask compleet?
        if (!dobMask.masked.isComplete) return setInvalid(true);

        // min/max + echte datum
        const parsed = parseDMY(v);
        setInvalid(!parsed);
    });

    // Tijdens typen: haal error weg
    dobEl.addEventListener('input', function () {
        setInvalid(false);
    });
    })();


    // ==========================================
    // 5. TABEL FILTER (ZOEKFUNCTIE)
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
    // 6. REVIEW LOADING OVERLAY (Start Analyse)
    // ==========================================
    const $reviewForm = $('form').filter(function() {
        return $(this).find('input[name="btn_start_review"]').length > 0;
    });

    if ($reviewForm.length) {
        $reviewForm.on('submit', function() {
            const $overlay = $('#review-loading-overlay');
            if (!$overlay.length) return;

            $('#review-loading-main').text('Applicatie opstarten...');
            $overlay.removeClass('is-long-wait').addClass('is-visible');

            if (window.reviewLoadingTimers && window.reviewLoadingTimers.length) {
                window.reviewLoadingTimers.forEach(function(id) { clearTimeout(id); });
            }
            window.reviewLoadingTimers = [];

            window.reviewLoadingTimers.push(
                setTimeout(function() {
                    $('#review-loading-main').text('Medicatiereview uitvoeren...');
                }, 5000)
            );

            window.reviewLoadingTimers.push(
                setTimeout(function() {
                    $overlay.addClass('is-long-wait');
                }, 20000)
            );
        });
    }
});

// ==========================================
// GLOBALE FUNCTIES (Voor onclick="" attributes)
// ==========================================
window.toggleEditRow = function(id) {
    const row = document.getElementById('edit-row-' + id);
    if (row) {
        row.style.display = (row.style.display === 'none' || row.style.display === '') ? 'table-row' : 'none';
    }
};
