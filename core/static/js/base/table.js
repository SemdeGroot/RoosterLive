// core/static/js/base/table.js
(function () {
  function initOne(wrapper) {
    const pageSize = Number(wrapper.dataset.pageSize || 10);
    const btn = wrapper.querySelector("[data-crud-more]");
    const tableSel = wrapper.dataset.table;

    // Houd je huidige contract aan: zonder btn of table selector doen we niks
    if (!btn || !tableSel) return;

    const table = document.querySelector(tableSel);
    const tbody = table?.querySelector("tbody");
    if (!table || !tbody) return;

    // welke rows pagineren we?
    const rowSelector = wrapper.dataset.rows || "tbody tr";
    const getRows = () => Array.from(table.querySelectorAll(rowSelector));

    let visible = pageSize;

    // =========================
    // SORT STATE
    // =========================
    let sortIndex = null;   // kolom index
    let sortDir = "asc";    // "asc" | "desc"

    // helper: cell value ophalen
    function getCellValue(tr, idx) {
      const td = tr.children?.[idx];
      return (td?.textContent || "").trim();
    }

    function parseNumber(s) {
      // ondersteunt "12", "12,5", "12.5", "1.234,56"
      const cleaned = String(s || "")
        .trim()
        .replace(/\s/g, "")
        .replace(/\./g, "")
        .replace(",", ".");
      const n = Number(cleaned);
      return Number.isFinite(n) ? n : null;
    }

    function parseDate(s) {
      // ondersteunt:
      // - "28-01-2026"
      // - "28-01-2026 14:05"
      // - "28-01-2026 14:05:33"
      // - "2026-01-28"
      // - "2026-01-28 14:05"
      // - "2026-01-28T14:05:33"
      s = (s || "").trim();
      if (!s || s === "-") return null;

      // ISO yyyy-mm-dd (optioneel tijd)
      const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
      if (iso) {
        const y = Number(iso[1]), m = Number(iso[2]), d = Number(iso[3]);
        const hh = Number(iso[4] || 0), mm = Number(iso[5] || 0), ss = Number(iso[6] || 0);
        return new Date(y, m - 1, d, hh, mm, ss).getTime();
      }

      // NL dd-mm-yyyy (optioneel tijd)
      const nl = s.match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
      if (nl) {
        const d = Number(nl[1]), m = Number(nl[2]), y = Number(nl[3]);
        const hh = Number(nl[4] || 0), mm = Number(nl[5] || 0), ss = Number(nl[6] || 0);
        return new Date(y, m - 1, d, hh, mm, ss).getTime();
      }

      return null;
    }

    function compare(a, b, type) {
      // lege waarden altijd onderaan (bij asc), bovenaan (bij desc) regelen we later via direction
      if (type === "number") {
        const na = parseNumber(a);
        const nb = parseNumber(b);

        const aEmpty = (a === "" || a === "-" || na === null);
        const bEmpty = (b === "" || b === "-" || nb === null);
        if (aEmpty && bEmpty) return 0;
        if (aEmpty) return 1;
        if (bEmpty) return -1;

        return na - nb;
      }

      if (type === "date") {
        const ta = parseDate(a);
        const tb = parseDate(b);

        const aEmpty = (a === "" || a === "-" || ta === null);
        const bEmpty = (b === "" || b === "-" || tb === null);
        if (aEmpty && bEmpty) return 0;
        if (aEmpty) return 1;
        if (bEmpty) return -1;

        return ta - tb;
      }

      // default string
      const aEmpty = (a === "" || a === "-");
      const bEmpty = (b === "" || b === "-");
      if (aEmpty && bEmpty) return 0;
      if (aEmpty) return 1;
      if (bEmpty) return -1;

      // localeCompare met numeric:true sorteert ook "2" vóór "10"
      return String(a).localeCompare(String(b), "nl", { numeric: true, sensitivity: "base" });
    }

    function updateHeaderIndicators() {
      const ths = table.querySelectorAll("thead th");
      ths.forEach((th, i) => {
        th.classList.remove("is-sorted-asc", "is-sorted-desc");
        th.removeAttribute("aria-sort");
        if (sortIndex === i) {
          th.classList.add(sortDir === "asc" ? "is-sorted-asc" : "is-sorted-desc");
          th.setAttribute("aria-sort", sortDir === "asc" ? "ascending" : "descending");
        }
      });
    }

    function applySort() {
      if (sortIndex === null) return;

      const th = table.querySelectorAll("thead th")[sortIndex];
      const type = (th?.dataset.sort || "string").toLowerCase();

      // Alleen sorteren op de rows die “meedoen” (dus niet display:none door search)
      const rows = getRows();
      const visibleRows = rows.filter(r => r.style.display !== "none");

      visibleRows.sort((ra, rb) => {
        const va = getCellValue(ra, sortIndex);
        const vb = getCellValue(rb, sortIndex);

        let c = compare(va, vb, type);
        if (sortDir === "desc") c *= -1;
        return c;
      });

      // Re-append alleen de zichtbare rows in gesorteerde volgorde
      visibleRows.forEach(tr => tbody.appendChild(tr));

      updateHeaderIndicators();
    }

    // =========================
    // PAGINATION APPLY
    // =========================
    function applyPagination() {
      const rows = getRows().filter(r => r.style.display !== "none"); // respecteer search
      rows.forEach((r, idx) => {
        if (idx < visible) r.classList.remove("is-hidden-row");
        else r.classList.add("is-hidden-row");
      });

      const hiddenCount = rows.filter(r => r.classList.contains("is-hidden-row")).length;
      btn.style.display = hiddenCount > 0 ? "" : "none";
    }

    function applyAll() {
      applySort();
      applyPagination();
    }

    // init
    applyAll();

    btn.addEventListener("click", () => {
      visible += pageSize;
      applyPagination();
    });

    // laat search ons resetten
    wrapper.addEventListener("crud:reset", () => {
      visible = pageSize;
      applyAll();
    });

    // =========================
    // WIRE SORT CLICK ON HEADERS
    // =========================
    const headers = table.querySelectorAll("thead th");
    headers.forEach((th, idx) => {
      // Zet sort uit voor actie-kolommen etc.
      if (th.hasAttribute("data-nosort")) return;

      th.classList.add("is-sortable");
      th.style.cursor = "pointer";

      th.addEventListener("click", () => {
        if (sortIndex === idx) {
          sortDir = (sortDir === "asc") ? "desc" : "asc";
        } else {
          sortIndex = idx;
          sortDir = "asc";
        }

        // na sorteren wil je meestal weer “vanaf boven” kijken
        visible = pageSize;
        applyAll();
      });
    });
  }

  function initAll() {
    document.querySelectorAll("[data-crud]").forEach(initOne);
  }

  document.addEventListener("DOMContentLoaded", initAll);
})();
