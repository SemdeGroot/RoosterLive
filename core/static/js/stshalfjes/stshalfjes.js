/* core/static/js/stshalfjes/stshalfjes.js */

document.addEventListener("DOMContentLoaded", function () {
  // 1) Live search (werkt samen met table.js)
  liveSearch("stsSearch", "stsTable", "sts-row");

  // 2) Date masks (IMask)
  initDateMasks(document);

  // 3) Select2 apotheken (ADD)
  initApotheekSelect2($("#id_apotheek"));

  // 4) Select2 geneesmiddelen (ADD) - AJAX zoeken (zoals nazendingen)
  // Django geeft meestal id_item_gehalveerd / id_item_alternatief
  initGeneesmiddelSelect2($("#id_item_gehalveerd"));
  initGeneesmiddelSelect2($("#id_item_alternatief"));

  // 5) Email modal select2 multiple
  initEmailSelect2();
});

/* -------------------------------------------------------
   ADD SECTION
------------------------------------------------------- */

window.toggleAddSection = function () {
  const section = document.getElementById("addSection");
  if (!section) return;

  const open = section.style.display !== "block";
  section.style.display = open ? "block" : "none";

  if (open) {
    // Re-init voor zekerheid (width/masks)
    initDateMasks(section);
    initApotheekSelect2($("#id_apotheek"));
    initGeneesmiddelSelect2($("#id_item_gehalveerd"));
    initGeneesmiddelSelect2($("#id_item_alternatief"));
  }
};

/* -------------------------------------------------------
   EDIT ROW TOGGLE
------------------------------------------------------- */

window.toggleEdit = function (id) {
  const viewRow = document.getElementById("row-" + id);
  const editRow = document.getElementById("edit-row-" + id);

  if (!viewRow || !editRow) return;

  if (editRow.style.display === "none" || editRow.style.display === "") {
    // Open edit
    viewRow.style.display = "none";
    editRow.style.display = "table-row";

    // Date masks in deze rij
    initDateMasks(editRow);

    // Apotheek select2 (edit row) - zoeken in options
    const $apo = $(editRow).find(".select2-apotheek-edit");
    $apo.each(function () {
      const $el = $(this);
      if (!$el.hasClass("select2-hidden-accessible")) {
        // dropdownParent op body zodat tabel niet verspringt
        initApotheekSelect2($el, $("body"));
      }
    });

    // Geneesmiddelen select2 (edit row) - AJAX zoeken
    const $meds = $(editRow).find(".select2-edit");
    $meds.each(function () {
      const $el = $(this);
      if (!$el.hasClass("select2-hidden-accessible")) {
        initGeneesmiddelSelect2($el, $("body"));
      }
    });
  } else {
    // Close edit
    viewRow.style.display = "table-row";
    editRow.style.display = "none";

    // optioneel: dropdowns sluiten
    try {
      $(editRow).find("select").select2("close");
    } catch (e) {}
  }
};

/* -------------------------------------------------------
   EMAIL MODAL (zelfde gedrag als nazendingen)
------------------------------------------------------- */

window.toggleEmailModal = function () {
  const modal = document.getElementById("emailModal");
  if (!modal) return;

  if (modal.style.display === "block") {
    modal.style.display = "none";
  } else {
    modal.style.display = "block";
    // re-init voor zekerheid (breedteberekening)
    initEmailSelect2();
  }
};

// Klik op backdrop sluit modal (zoals nazendingen)
window.onclick = function (event) {
  const modal = document.getElementById("emailModal");
  if (modal && event.target === modal) {
    modal.style.display = "none";
  }
};

window.selectAllApotheken = function () {
  $("#id_recipients > option").prop("selected", true);
  $("#id_recipients").trigger("change");
};

window.deselectAllApotheken = function () {
  $("#id_recipients").val(null).trigger("change");
};

function initEmailSelect2() {
  const $select = $("#id_recipients");
  if (!$select.length) return;

  // voorkom dubbele init
  if ($select.hasClass("select2-hidden-accessible")) return;

  $select.select2({
    width: "100%",
    placeholder: "Zoek en selecteer apotheken...",
    allowClear: false,
    dropdownParent: $("#emailModal"),
    closeOnSelect: false,
    language: {
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
    },
  });
}

/* -------------------------------------------------------
   HELPERS
------------------------------------------------------- */

// Live Search + reset table.js pagination
function liveSearch(inputId, tableId, rowClass) {
  const input = document.getElementById(inputId);
  if (!input) return;

  input.addEventListener("input", function () {
    const q = (this.value || "").toLowerCase();
    const rows = document.querySelectorAll(`#${tableId} .${rowClass}`);

    rows.forEach((row) => {
      const text = (row.innerText || "").toLowerCase();
      row.style.display = text.includes(q) ? "" : "none";
    });

    const wrapper = document.querySelector(`[data-table="#${tableId}"]`);
    if (wrapper) wrapper.dispatchEvent(new Event("crud:reset"));
  });
}

// IMask op velden met .js-date
function initDateMasks(container) {
  const root = container || document;
  const inputs = root.querySelectorAll ? root.querySelectorAll(".js-date") : [];
  inputs.forEach(function (input) {
    // voorkom dubbele init
    if (input._imask) return;

    input._imask = IMask(input, {
      mask: "d-m-Y",
      lazy: true,
      overwrite: true,
      blocks: {
        d: { mask: IMask.MaskedRange, from: 1, to: 31, maxLength: 2 },
        m: { mask: IMask.MaskedRange, from: 1, to: 12, maxLength: 2 },
        Y: { mask: IMask.MaskedRange, from: 1900, to: 2100, maxLength: 4 },
      },
    });
  });
}

/* -------------------------------------------------------
   SELECT2: APOTHEKEN (geen API, zoekt in bestaande opties)
------------------------------------------------------- */

function initApotheekSelect2($element, $dropdownParent) {
  if (!$element || !$element.length) return;

  // voorkom dubbele init
  if ($element.hasClass("select2-hidden-accessible")) return;

  $element.select2({
    width: "100%",
    placeholder: $element.data("placeholder") || "Zoek apotheek...",
    allowClear: true,
    minimumResultsForSearch: 0, // altijd zoekveld tonen
    dropdownParent: $dropdownParent || null,
    language: {
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
    },
  });
}

/* -------------------------------------------------------
   SELECT2: GENEESMIDDELEN (AJAX zoals nazendingen)
   Werkt ook in edit row waar maar 1 option initieel staat.
------------------------------------------------------- */

function initGeneesmiddelSelect2($element, $dropdownParent) {
  if (!$element || !$element.length) return;

  // voorkom dubbele init
  if ($element.hasClass("select2-hidden-accessible")) return;

  $element.select2({
    width: "100%",
    placeholder: "Zoek medicijn op ZI-nummer of naam...",
    allowClear: true,
    minimumInputLength: 2,
    closeOnSelect: true,
    dropdownParent: $dropdownParent || null,
    language: {
      inputTooShort: () => "Typ min. 2 tekens...",
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
      errorLoading: () => "Resultaten konden niet worden geladen.",
    },
    ajax: {
      url: "/api/voorraad-zoeken/",
      dataType: "json",
      delay: 250,
      data: (params) => ({ q: params.term }),
      processResults: (data) => ({ results: data.results || [] }),
      cache: true,
    },
    // Optioneel: als je de mooie layout van nazendingen wil, kun je templateResult gebruiken.
    templateResult: formatRepo,
    templateSelection: formatRepoSelection,
    escapeMarkup: (m) => m,
  });
}

// Helpers voor weergave "ZI - Naam"
function parseZiNaam(repo) {
  const raw = repo && repo.text ? String(repo.text) : "";
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
        <div class='select2-result-repository__title' style='font-size:1.05em;'>
          <span style='font-size:0.8em; color:var(--muted);'>ZI-nummer:</span> <span>${zi}</span>
          ${naam ? `<span> - ${naam}</span>` : ""}
        </div>
      </div>
    </div>`;
}

function formatRepoSelection(repo) {
  if (!repo) return "";
  const { zi, naam } = parseZiNaam(repo);
  if (zi && naam) return `ZI-nummer: ${zi} - ${naam}`;
  return repo.text || repo.id || "";
}
