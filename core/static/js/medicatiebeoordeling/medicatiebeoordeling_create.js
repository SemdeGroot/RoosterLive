// static/js/medicatiebeoordeling/medicatiebeoordeling_create.js

$(document).ready(function() {

    // ==========================================
    // 1. SELECT2: AFDELING DROPDOWN
    // ==========================================
    const $afdelingSelect = $('.django-select2').select2({
        placeholder: "Klik om een afdeling te zoeken...",
        allowClear: true,
        width: '100%'
    });

    $afdelingSelect.on('select2:open', function() {
        const searchField = document.querySelector('.select2-search__field');
        if (searchField) {
            searchField.placeholder = "Typ om te zoeken...";
            searchField.focus();
        }
    });

    // ==========================================
    // 2. SELECT2: BESTAANDE PATIENT DROPDOWN
    // ==========================================
    const $existingPatientSelect = $('#id_existing_patient_select').select2({
        placeholder: "Zoek een patient...",
        allowClear: true,
        width: '100%',
        ajax: {
            url: window.PATIENT_SELECT_URL || '/medicatiebeoordeling/api/patient-select/',
            dataType: 'json',
            delay: 250,
            data: function(params) {
                return {
                    q: params.term || '',
                    afdeling_id: $('#id_afdeling_id').val() || ''
                };
            },
            processResults: function(data) {
                return { results: data.results };
            },
            cache: true
        },
        minimumInputLength: 0
    });

    $existingPatientSelect.on('change', function() {
        var val = $(this).val();
        $('#id_existing_patient_id').val(val || '');
    });

    // ==========================================
    // 3. DYNAMISCHE INSTRUCTIES
    // ==========================================
    const instructions = {
        'medimo_afdeling': `
        1. Controleer rechtsboven of de juiste zorginstelling geselecteerd is.<br>
        2. Ga naar <em>Alle overzichten</em> en kies <em>Overzicht medicatie patient/bewoner/client/gebruiker</em> (verschilt per organisatie).<br>
        3. Selecteer de gewenste afdeling.<br>
        4. Selecteer en kopieer alles vanaf de kop <em>Overzicht medicatie Afdeling</em> t/m de laatste medicatieregel.
            <strong>Let op:</strong> als je niet het volledige overzicht van de hele afdeling kopieert, kan er data verloren gaan. Het systeem verwijdert namelijk patienten die niet meer in het overzicht staan.
            Wil je slechts een patient beoordelen? Kies dan <em>Individueel</em> bij <em>Type Review</em> in het formulier.<br>
        5. Plak de tekst in het vak hieronder en start de analyse.
        `,
        'medimo_patient': `
        1. Controleer rechtsboven of de juiste zorginstelling geselecteerd is.<br>
        2. Zoek rechtsboven de patient die je wilt beoordelen.<br>
        3. Selecteer hierboven de afdeling die onder de naam van de patient staat.<br>
        4. Vul de naam en geboortedatum van de patient exact in zoals in Medimo.<br>
        5. Kopieer de gegevens door op de knop <em>Medicatie</em> te klikken.<br>
        6. Plak het overzicht in het tekstvak hieronder en start de analyse.
        `,
        'pharmacom_patient': `
        1. Zoek patient via receptverwerking.<br>
        2. Open de Medicatiestatus (F3).<br>
        3. Klik op het Download icoontje (Ctrl + D).<br>
        4. Klik op <em>Actueel Medicatie Overzicht</em>.<br>
        5. Vink <em>inclusief laboratorium waarden vermelden</em> aan.<br>
        6. Klik op <em>downloaden</em>.<br>
        7. Sla het bestand op.<br>
        8. Upload de PDF hieronder.
        `
    };

    // ==========================================
    // 4. UI STATE MANAGEMENT
    // ==========================================
    function updateUI() {
        var source = $('#id_source').val();
        var scope = $('#id_scope').val();
        var patientType = $('#id_patient_type').val();
        var isPharmacon = source === 'pharmacom';
        var isPatientScope = isPharmacon || scope === 'patient';

        // Pharmacom forceert scope=patient
        if (isPharmacon) {
            scope = 'patient';
            $('#id_scope').val('patient');
        }

        // Afdeling: verberg bij pharmacom
        if (isPharmacon) {
            $('#afdeling-wrapper').slideUp(200);
        } else {
            $('#afdeling-wrapper').slideDown(200);
        }

        // Scope: verberg bij pharmacom (altijd patient)
        if (isPharmacon) {
            $('#scope-wrapper').slideUp(200);
        } else {
            $('#scope-wrapper').slideDown(200);
        }

        // Patient type segmented control: toon bij individueel
        if (isPatientScope) {
            $('#patient-type-wrapper').slideDown(200);
        } else {
            $('#patient-type-wrapper').slideUp(200);
        }

        // Nieuwe patient velden vs bestaande patient dropdown
        if (isPatientScope && patientType === 'new' && !isPharmacon) {
            // Medimo nieuw: handmatig naam + geboortedatum
            $('#single-patient-fields').slideDown(200);
            $('#existing-patient-wrapper').slideUp(200);
        } else if (isPatientScope && patientType === 'existing') {
            // Bestaande patient selecteren
            $('#single-patient-fields').slideUp(200);
            $('#existing-patient-wrapper').slideDown(200);
            // Herlaad select2 data bij wissel
            $existingPatientSelect.val(null).trigger('change');
        } else if (isPharmacon && patientType === 'new') {
            // Pharmacom nieuw: naam komt uit parser
            $('#single-patient-fields').slideUp(200);
            $('#existing-patient-wrapper').slideUp(200);
        } else {
            $('#single-patient-fields').slideUp(200);
            $('#existing-patient-wrapper').slideUp(200);
        }

        // Medimo tekstveld: verberg bij pharmacom
        if (isPharmacon) {
            $('#medimo-text-wrapper').slideUp(200);
        } else {
            $('#medimo-text-wrapper').slideDown(200);
        }

        // PDF upload: toon bij pharmacom
        if (isPharmacon) {
            $('#pdf-upload-wrapper').slideDown(200);
        } else {
            $('#pdf-upload-wrapper').slideUp(200);
        }

        // Instructies
        var key = source + '_' + scope;
        var $wrapper = $('#instruction-wrapper');
        var $content = $('#instruction-content');
        if (instructions[key]) {
            $content.html(instructions[key]);
            if ($wrapper.is(':hidden')) $wrapper.slideDown(200);
        } else {
            $wrapper.slideUp(200);
        }

        // Lege velden bij scope-wissel
        if (!isPatientScope) {
            $('#id_patient').val('');
            $('#id_patient_geboortedatum').val('');
            $('#id_existing_patient_id').val('');
        }
    }

    $('#id_source, #id_scope, #id_patient_type').on('change', updateUI);
    // Bij afdeling-wissel: herlaad patient select
    $afdelingSelect.on('change', function() {
        if ($('#id_patient_type').val() === 'existing') {
            $existingPatientSelect.val(null).trigger('change');
        }
    });
    updateUI();

    // ==========================================
    // 5. PDF DROPZONE
    // ==========================================
    (function() {
        var $dz = $('#pdfDropzone');
        var $input = $('#id_pdf_file');
        var $meta = $('#pdfFileMeta');
        var $name = $('#pdfFileName');

        if (!$dz.length) return;

        $dz.on('click', function() { $input.trigger('click'); });

        $input.on('change', function() {
            var file = this.files && this.files[0];
            if (file) {
                $name.text(file.name);
                $meta.addClass('is-visible');
            } else {
                $meta.removeClass('is-visible');
            }
        });

        $dz.on('dragover', function(e) {
            e.preventDefault();
            $dz.addClass('is-dragover');
        });
        $dz.on('dragleave drop', function() {
            $dz.removeClass('is-dragover');
        });
        $dz.on('drop', function(e) {
            e.preventDefault();
            var files = e.originalEvent.dataTransfer.files;
            if (files.length && files[0].name.toLowerCase().endsWith('.pdf')) {
                $input[0].files = files;
                $input.trigger('change');
            }
        });
    })();

    // ==========================================
    // 6. IMASK: GEBOORTEDATUM
    // ==========================================
    (function () {
    var dobEl = document.getElementById('id_patient_geboortedatum');
    if (!dobEl || !window.IMask) return;

    if (!dobEl.getAttribute('placeholder')) {
        dobEl.setAttribute('placeholder', 'dd-mm-jjjj');
    }

    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var minYear = 1900;
    var maxYear = today.getFullYear();

    var dobMask = IMask(dobEl, {
        mask: 'd-m-Y',
        lazy: true,
        overwrite: true,
        autofix: false,
        blocks: {
        d: { mask: IMask.MaskedRange, from: 1, to: 31, maxLength: 2 },
        m: { mask: IMask.MaskedRange, from: 1, to: 12, maxLength: 2 },
        Y: { mask: IMask.MaskedRange, from: minYear, to: maxYear, maxLength: 4 }
        }
    });

    function parseDMY(value) {
        var parts = (value || '').split('-');
        if (parts.length !== 3) return null;

        var dd = parseInt(parts[0], 10);
        var mm = parseInt(parts[1], 10);
        var yyyy = parseInt(parts[2], 10);

        if (!dd || !mm || !yyyy) return null;
        if (yyyy < minYear || yyyy > maxYear) return null;

        var d = new Date(yyyy, mm - 1, dd);
        if (d.getFullYear() !== yyyy || d.getMonth() !== (mm - 1) || d.getDate() !== dd) return null;

        var dateOnly = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        if (dateOnly > today) return null;

        return dateOnly;
    }

    function setInvalid(isInvalid) {
        dobEl.classList.toggle('is-invalid', !!isInvalid);
    }

    dobEl.addEventListener('blur', function () {
        var v = dobEl.value.trim();
        if (!v) return setInvalid(false);
        if (!dobMask.masked.isComplete) return setInvalid(true);
        var parsed = parseDMY(v);
        setInvalid(!parsed);
    });

    dobEl.addEventListener('input', function () {
        setInvalid(false);
    });
    })();

    // ==========================================
    // 7. TABEL FILTER
    // ==========================================
    $('#manageSearchInput').on('keyup', function() {
        var filter = $(this).val().toLowerCase();
        $('.manage-row').each(function() {
            var $row = $(this);
            var text = $row.text().toLowerCase();
            $row.toggle(text.indexOf(filter) > -1);
        });
    });

    // ==========================================
    // 8. REVIEW LOADING OVERLAY
    // ==========================================
    var $reviewForm = $('form').filter(function() {
        return $(this).find('input[name="btn_start_review"]').length > 0;
    });

    if ($reviewForm.length) {
        $reviewForm.on('submit', function() {
            var $overlay = $('#review-loading-overlay');
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
// GLOBALE FUNCTIES
// ==========================================
window.toggleEditRow = function(id) {
    var row = document.getElementById('edit-row-' + id);
    if (row) {
        row.style.display = (row.style.display === 'none' || row.style.display === '') ? 'table-row' : 'none';
    }
};
