/* core/static/js/nazendingen/nazendingen.js */

document.addEventListener("DOMContentLoaded", function () {

    // Helper: haal ZI + naam uit repo.text ("ZI - Naam") met fallback op repo.id
    function parseZiNaam(repo) {
        const raw = (repo && repo.text) ? String(repo.text) : "";
        const parts = raw.split(" - ");
        const zi = (parts[0] && parts[0].trim()) || (repo && repo.id) || "";
        const naam = parts.slice(1).join(" - ").trim();
        return { zi, naam };
    }

    /**
     * Format functie voor de resultatenlijst (Dropdown items).
     * ZI-nummer links, muted kleur, streepje, naam normaal (niet bold).
     */
    function formatRepo(repo) {
        if (repo.loading) return repo.text;

        const { zi, naam } = parseZiNaam(repo);

        return $(
            "<div class='select2-result-repository clearfix'>" +
                "<div class='select2-result-repository__meta'>" +
                    "<div class='select2-result-repository__title' style='font-size:1.1em;'>" +
                        "<span style='font-size:0.8em; color:var(--muted);'>ZI-nummer:</span> " +
                        "<span'>" + zi + "</span>" +
                        (naam ? "<span'> - " + naam + "</span>" : "") +
                    "</div>" +
                "</div>" +
            "</div>"
        );
    }

    /**
     * Geselecteerde waarde (input zelf)
     */
    function formatRepoSelection(repo) {
        if (!repo) return "";
        const { zi, naam } = parseZiNaam(repo);
        if (zi && naam) return `ZI: ${zi} - ${naam}`;
        return repo.text || repo.id || "";
    }

    // 1. Configuratie object
    const select2AjaxConfig = {
        width: '100%',
        placeholder: "Zoek medicijn op ZI-nummer of naam...",
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
        templateResult: formatRepo,
        templateSelection: formatRepoSelection,
        escapeMarkup: function (m) { return m; }
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
    if (filterInput) {
        filterInput.addEventListener('keyup', function () {
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

    const isHidden = window.getComputedStyle(section).display === 'none';

    if (isHidden) {
        section.style.display = 'block';
    } else {
        section.style.display = 'none';
    }
}

function toggleEditRow(id) {
    const viewRow = document.getElementById('row-' + id);
    const editRow = document.getElementById('edit-row-' + id);

    // Lokale helper
    function parseZiNaam(repo) {
        const raw = (repo && repo.text) ? String(repo.text) : "";
        const parts = raw.split(" - ");
        const zi = (parts[0] && parts[0].trim()) || (repo && repo.id) || "";
        const naam = parts.slice(1).join(" - ").trim();
        return { zi, naam };
    }

    if (editRow.style.display === 'none') {
        viewRow.style.display = 'none';
        editRow.style.display = 'table-row';

        const $select = $(editRow).find('.select2-edit');

        if (!$select.hasClass("select2-hidden-accessible")) {
            $select.select2({
                width: '100%',
                placeholder: "Zoek medicijn op ZI-nummer of naam...",
                minimumInputLength: 2,
                closeOnSelect: true,
                dropdownParent: $(editRow),
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
                templateResult: function (repo) {
                    if (repo.loading) return repo.text;

                    const { zi, naam } = parseZiNaam(repo);

                    return $(
                        "<div class='select2-result-repository clearfix'>" +
                            "<div class='select2-result-repository__meta'>" +
                                "<div class='select2-result-repository__title' style='font-size:1.1em;'>" +
                                    "<span style='font-size:0.8em; color:var(--muted);'>ZI-nummer:</span> " +
                                    "<span'>" + zi + "</span>" +
                                    (naam ?"<span'> - " + naam + "</span>" : "") +
                                "</div>" +
                            "</div>" +
                        "</div>"
                    );
                },
                templateSelection: function (repo) {
                    if (!repo) return "";
                    const { zi, naam } = parseZiNaam(repo);
                    if (zi && naam) return `ZI: ${zi} - ${naam}`;
                    return repo.text || repo.id || "";
                },
                escapeMarkup: function (m) { return m; }
            });
        }

    } else {
        viewRow.style.display = 'table-row';
        editRow.style.display = 'none';
    }
}