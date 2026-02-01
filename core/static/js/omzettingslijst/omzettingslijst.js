document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("omzettingslijstSearch")) {
    liveSearch("omzettingslijstSearch", "omzettingslijstTable", "ol-row");
  }

  initDateMasks(document);

  initApotheekSelect2($("#id_apotheek_list"));
  initListPickerSelect2($("#id_list_picker"));

  // gevraagd + geleverd (add form)
  initGeneesmiddelSelect2($("#id_gevraagd_geneesmiddel"));
  initGeneesmiddelSelect2($("#id_geleverd_geneesmiddel"));

  initEmailSelect2();
});

window.toggleAddListSection = function () {
  const section = document.getElementById("addListSection");
  if (!section) return;

  const open = section.style.display !== "block";
  section.style.display = open ? "block" : "none";

  if (open) {
    initApotheekSelect2($("#id_apotheek_list"), $(section));
  }
};

window.toggleAddEntrySection = function () {
  const section = document.getElementById("addEntrySection");
  if (!section) return;

  const open = section.style.display !== "block";
  section.style.display = open ? "block" : "none";

  if (open) {
    initDateMasks(section);

    initGeneesmiddelSelect2($("#id_gevraagd_geneesmiddel"), $(section));
    initGeneesmiddelSelect2($("#id_geleverd_geneesmiddel"), $(section));
  }
};

window.toggleEdit = function (id) {
  const viewRow = document.getElementById("row-" + id);
  const editRow = document.getElementById("edit-row-" + id);

  if (!viewRow || !editRow) return;

  if (editRow.style.display === "none" || editRow.style.display === "") {
    viewRow.style.display = "none";
    editRow.style.display = "table-row";

    initDateMasks(editRow);

    const $gevraagd = $(editRow).find(".select2-edit-gevraagd");
    $gevraagd.each(function () {
      const $el = $(this);
      if (!$el.hasClass("select2-hidden-accessible")) {
        initGeneesmiddelSelect2($el, $(editRow));
      }
    });

    const $geleverd = $(editRow).find(".select2-edit-geleverd");
    $geleverd.each(function () {
      const $el = $(this);
      if (!$el.hasClass("select2-hidden-accessible")) {
        initGeneesmiddelSelect2($el, $(editRow));
      }
    });
  } else {
    viewRow.style.display = "table-row";
    editRow.style.display = "none";

    try {
      $(editRow).find("select").select2("close");
    } catch (e) {}
  }
};

// --------------------
// EMAIL MODAL
// --------------------
window.toggleEmailModal = function () {
  const modal = document.getElementById("emailModal");
  if (!modal) return;

  const open = modal.style.display !== "block";
  modal.style.display = open ? "block" : "none";

  if (open) {
    initEmailSelect2();
  } else {
    try {
      $("#id_recipients").select2("close");
    } catch (e) {}
  }
};

window.addEventListener("click", function (event) {
  const modal = document.getElementById("emailModal");
  if (modal && event.target === modal) {
    modal.style.display = "none";
    try {
      $("#id_recipients").select2("close");
    } catch (e) {}
  }
});

window.deselectAllLists = function () {
  $("#id_recipients").val(null).trigger("change");
};

function initEmailSelect2() {
  const $select = $("#id_recipients");
  if (!$select.length) return;
  if ($select.hasClass("select2-hidden-accessible")) return;

  const $modal = $("#emailModal");

  $select.select2({
    width: "100%",
    placeholder: "Zoek en selecteer omzettingslijsten...",
    allowClear: false,
    dropdownParent: $modal,
    closeOnSelect: false,
    minimumInputLength: 0,
    ajax: {
      url: "/api/omzettingslijsten/",
      dataType: "json",
      delay: 200,
      data: (params) => ({ q: params.term || "" }),
      processResults: (data) => ({ results: data.results || [] }),
      cache: true,
    },
    language: {
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
      errorLoading: () => "Resultaten konden niet worden geladen.",
    },
  });
}

// --------------------
// Helpers (zelfde als no-delivery)
// --------------------
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

function initDateMasks(container) {
  const root = container || document;
  const inputs = root.querySelectorAll ? root.querySelectorAll(".js-date") : [];
  inputs.forEach(function (input) {
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

function initApotheekSelect2($element, $dropdownParent) {
  if (!$element || !$element.length) return;
  if ($element.hasClass("select2-hidden-accessible")) return;

  $element.select2({
    width: "100%",
    placeholder: $element.data("placeholder") || "Zoek organisatie...",
    allowClear: true,
    minimumResultsForSearch: 0,
    dropdownParent: $dropdownParent || null,
    language: {
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
    },
  });
}

function initListPickerSelect2($element) {
  if (!$element || !$element.length) return;
  if ($element.hasClass("select2-hidden-accessible")) return;

  $element.select2({
    width: "100%",
    placeholder: $element.data("placeholder") || "Zoek lijst...",
    allowClear: true,
    minimumInputLength: 0,
    ajax: {
      url: "/api/omzettingslijsten/",
      dataType: "json",
      delay: 200,
      data: (params) => ({ q: params.term || "" }),
      processResults: (data) => ({ results: data.results || [] }),
      cache: true,
    },
    language: {
      searching: () => "Zoeken...",
      noResults: () => "Geen resultaten",
      errorLoading: () => "Resultaten konden niet worden geladen.",
    },
  });
}

function initGeneesmiddelSelect2($element, $dropdownParent) {
  if (!$element || !$element.length) return;
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
    templateResult: formatRepo,
    templateSelection: formatRepoSelection,
    escapeMarkup: (m) => m,
  });
}

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
