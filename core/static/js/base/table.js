// core/static/js/base/table.js

(function () {
  function initOne(wrapper) {
    const pageSize = Number(wrapper.dataset.pageSize || 10);
    const btn = wrapper.querySelector("[data-crud-more]");
    const tableSel = wrapper.dataset.table;
    if (!btn || !tableSel) return;

    const table = document.querySelector(tableSel);
    const tbody = table?.querySelector("tbody");
    if (!table || !tbody) return;

    // welke rows pagineren we?
    const rowSelector = wrapper.dataset.rows || "tbody tr";
    const getRows = () => Array.from(table.querySelectorAll(rowSelector));

    let visible = pageSize;

    function apply() {
      const rows = getRows().filter(r => r.style.display !== "none"); // respecteer jouw search
      // Eerst alles tonen (search bepaalt al welke er mogen), daarna limiteren we
      rows.forEach((r, idx) => {
        if (idx < visible) r.classList.remove("is-hidden-row");
        else r.classList.add("is-hidden-row");
      });

      const hiddenCount = rows.filter(r => r.classList.contains("is-hidden-row")).length;
      btn.style.display = hiddenCount > 0 ? "" : "none";
    }

    // init
    apply();

    btn.addEventListener("click", () => {
      visible += pageSize;
      apply();
    });

    // laat search ons resetten
    wrapper.addEventListener("crud:reset", () => {
      visible = pageSize;
      apply();
    });
  }

  function initAll() {
    document.querySelectorAll("[data-crud]").forEach(initOne);
  }

  document.addEventListener("DOMContentLoaded", initAll);
})();
