/* core/static/js/nazendingen/nazendingen.js */

document.addEventListener("DOMContentLoaded", function () {
  
  // 1. Initialiseer Select2 op het 'Toevoegen' formulier (statisch aanwezig)
  initSelect2($('#id_voorraad_item'));

  // 2. Initialiseer datum maskers (IMask)
  initDateMasks();

  // 3. Activeer live search die samenwerkt met table.js
  liveSearch("nazendingSearch", "nazendingTable", "nazending-row");

});

/* -------------------------------------------------------
   FUNCTIES
------------------------------------------------------- */

// Toggle het "Toevoegen" paneel
window.toggleAddSection = function() {
  const section = document.getElementById('addSection');
  if (!section) return;
  section.style.display = (section.style.display === 'none') ? 'block' : 'none';
};

// Toggle de Edit-rij + Init Select2 binnen die rij
window.toggleEdit = function(id) {
  const viewRow = document.getElementById('row-' + id);
  const editRow = document.getElementById('edit-row-' + id);

  if (!viewRow || !editRow) return;

  if (editRow.style.display === 'none') {
    // Openen
    viewRow.style.display = 'none';
    editRow.style.display = 'table-row';

    // Zoek de select binnen deze edit-rij en initialiseer Select2 als dat nog niet gebeurd is
    const $select = $(editRow).find('.select2-edit');
    if ($select.length && !$select.hasClass("select2-hidden-accessible")) {
      initSelect2($select, $(editRow));
    }

  } else {
    // Sluiten
    viewRow.style.display = 'table-row';
    editRow.style.display = 'none';
  }
};

/* -------------------------------------------------------
   HELPERS
------------------------------------------------------- */

// Generic Live Search (Kopieert logica van admin_panel, maar triggert table.js pagination)
function liveSearch(inputId, tableId, rowClass) {
  const input = document.getElementById(inputId);
  if (!input) return;

  input.addEventListener("input", function() {
    const q = this.value.toLowerCase();
    const rows = document.querySelectorAll(`#${tableId} .${rowClass}`);
    
    rows.forEach(row => {
      // Zoek in alle tekst van de rij
      const text = row.innerText.toLowerCase();
      row.style.display = text.includes(q) ? "" : "none";
    });

    // Reset de paginering (table.js luistert hiernaar)
    const wrapper = document.querySelector(`[data-table="#${tableId}"]`);
    if (wrapper) {
      wrapper.dispatchEvent(new Event("crud:reset"));
    }
  });
}

// Initialiseer IMask op velden met class .js-date
function initDateMasks() {
  document.querySelectorAll(".js-date").forEach(function (input) {
    IMask(input, {
      mask: 'd-m-Y',
      lazy: true,
      overwrite: true,
      blocks: {
        d: { mask: IMask.MaskedRange, from: 1, to: 31, maxLength: 2 },
        m: { mask: IMask.MaskedRange, from: 1, to: 12, maxLength: 2 },
        Y: { mask: IMask.MaskedRange, from: 1900, to: 2100, maxLength: 4 }
      }
    });
  });
}

// Select2 Configuratie & Init
function initSelect2($element, $dropdownParent) {
  if (!$element || !$element.length) return;

  $element.select2({
    width: '100%',
    placeholder: "Zoek medicijn op ZI-nummer of naam...",
    allowClear: true,
    minimumInputLength: 2,
    closeOnSelect: true,
    dropdownParent: $dropdownParent || null, // Belangrijk voor modals/tabellen
    language: {
      inputTooShort: () => "Typ min. 2 tekens...",
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
      errorLoading: () => "Resultaten konden niet worden geladen."
    },
    ajax: {
      url: '/api/voorraad-zoeken/',
      dataType: 'json',
      delay: 250,
      data: params => ({ q: params.term }),
      processResults: data => ({ results: data.results }),
      cache: true
    },
    templateResult: formatRepo,
    templateSelection: formatRepoSelection,
    escapeMarkup: m => m
  });
}

// Select2 Opmaak Helpers
function parseZiNaam(repo) {
  const raw = (repo && repo.text) ? String(repo.text) : "";
  const parts = raw.split(" - ");
  const zi = (parts[0] && parts[0].trim()) || (repo && repo.id) || "";
  const naam = parts.slice(1).join(" - ").trim();
  return { zi, naam };
}

function formatRepo(repo) {
  if (repo.loading) return repo.text;
  const { zi, naam } = parseZiNaam(repo);
  return `
    <div class='select2-result-repository clearfix'>
      <div class='select2-result-repository__meta'>
        <div class='select2-result-repository__title' style='font-size:1.1em;'>
          <span style='font-size:0.8em; color:var(--muted);'>ZI:</span> <span>${zi}</span>
          ${naam ? `<span> - ${naam}</span>` : ""}
        </div>
      </div>
    </div>`;
}

function formatRepoSelection(repo) {
  if (!repo) return "";
  const { zi, naam } = parseZiNaam(repo);
  if (zi && naam) return `ZI: ${zi} - ${naam}`;
  return repo.text || repo.id || "";
}