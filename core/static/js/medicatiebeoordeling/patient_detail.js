// static/js/medicatiebeoordeling/patient_detail.js

$(document).ready(function () {
  // ==========================================
  // 0. SELECT2 (NIET OPTIONEEL) voor Jansen dropdowns
  // ==========================================
  const $jansenSelects = $(".django-select2-jansen").select2({
    placeholder: "Kies een Jansen categorie...",
    allowClear: true,
    width: "100%",
  });

  $jansenSelects.on("select2:open", function () {
    const searchField = document.querySelector(".select2-search__field");
    if (searchField) {
      searchField.placeholder = "Typ om te zoeken...";
      searchField.focus();
    }
  });

  // Preselect values die vanuit template in window.__jansenPreselect komen
  if (window.__jansenPreselect && Array.isArray(window.__jansenPreselect)) {
    window.__jansenPreselect.forEach(function (item) {
      const sel = document.querySelector(`select[name="${item.selectName}"]`);
      if (!sel) return;

      // Als value leeg is: laat op standaard staan
      if (item.value && item.value !== "") {
        $(sel).val(item.value).trigger("change");
      }
    });
  }

  // ==========================================
  // 1. DIRTY CHECK (jouw bestaande gedrag)
  // ==========================================
  let formDirty = false;

  document.addEventListener("input", function (e) {
    if (e.target.closest("form")) {
      formDirty = true;
    }
  });

  document.addEventListener("submit", function () {
    formDirty = false;
  });

  document.addEventListener("click", function (e) {
    const isBackBtn = e.target.id === "backBtn" || e.target.closest("#backBtn");
    if (isBackBtn && formDirty) {
      const confirmLeave = confirm("Je hebt onopgeslagen wijzigingen. Wil je de pagina verlaten?");
      if (!confirmLeave) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    }
  });

  window.addEventListener("beforeunload", function (e) {
    if (formDirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  // ==========================================
  // 2. MEDIMO COPY (jouw bestaande functies)
  // ==========================================
  function buildMedimoTextFromGroup(groupEl, groupId, includeTitle = false) {
    const rows = groupEl.querySelectorAll("table tbody tr");
    const lines = [];

    // alleen “echte” med rows meenemen: edit-rows overslaan
    rows.forEach((tr) => {
      if (tr.classList.contains("edit-row")) return;

      const tds = tr.querySelectorAll("td");
      if (tds.length >= 2) {
        const middel = (tds[0].innerText || "").trim();
        const gebruik = (tds[1].innerText || "").trim();
        if (middel || gebruik) lines.push(`${middel}: ${gebruik}`);
      }
    });

    const titleEl = groupEl.querySelector(".jansen-title");
    const title = (titleEl?.innerText || "").trim();

    const commentTa = groupEl.querySelector(`textarea[name="comment_${groupId}"]`);
    const commentVal = commentTa ? (commentTa.value || "").trim() : "";

    if (lines.length === 0) {
      let text = title || "";
      if (commentVal) {
        text += `\n\nOpmerkingen:\n${commentVal}`;
      }
      return text.trim();
    }

    let text = "";

    if (includeTitle && title) {
      text += `${title}\n\n`;
    }

    text += lines.join("\n");

    if (commentVal) {
      text += `\n\nOpmerkingen:\n${commentVal}`;
    }

    return text.trim();
  }

  async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();

    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  }

  function setCopyFeedback(btn, success, defaultLabel) {
    const labelEl = btn.querySelector(".copy-label");
    if (!labelEl) return;

    labelEl.innerText = success ? "Gekopieerd!" : "Kopiëren mislukt";
    btn.classList.toggle("is-copied", success);

    setTimeout(() => {
      labelEl.innerText = defaultLabel;
      btn.classList.remove("is-copied");
    }, 1200);
  }

  document.querySelectorAll(".btn-copy-medimo").forEach((btn) => {
    if (btn.classList.contains("btn-copy-all-medimo")) return;

    btn.addEventListener("click", async () => {
      const groupId = btn.getAttribute("data-group-id");
      const groupEl = btn.closest(".med-group");
      if (!groupEl || !groupId) return;

      const text = buildMedimoTextFromGroup(groupEl, groupId, false);

      try {
        const ok = await copyTextToClipboard(text);
        if (!ok) throw new Error("Copy failed");
        setCopyFeedback(btn, true, "Kopieer voor Medimo");
      } catch (e) {
        console.error("Kopiëren mislukt:", e);
        setCopyFeedback(btn, false, "Kopieer voor Medimo");
      }
    });
  });

  function buildAllMedimoText() {
    const groups = document.querySelectorAll(".med-group");
    const parts = [];

    groups.forEach((groupEl) => {
      const groupId = groupEl.getAttribute("data-group-id");
      if (!groupId) return;

      const text = buildMedimoTextFromGroup(groupEl, groupId, true);
      if (text) parts.push(text);
    });

    return parts.join("\n\n----------------------------------------\n\n").trim();
  }

  const copyAllBtn = document.querySelector(".btn-copy-all-medimo");
  if (copyAllBtn) {
    copyAllBtn.addEventListener("click", async () => {
      const text = buildAllMedimoText();

      try {
        const ok = await copyTextToClipboard(text);
        if (!ok) throw new Error("Copy failed");
        setCopyFeedback(copyAllBtn, true, "Kopieer alles voor Medimo");
      } catch (e) {
        console.error("Kopiëren mislukt:", e);
        setCopyFeedback(copyAllBtn, false, "Kopieer alles voor Medimo");
      }
    });
  }
});

// ==========================================
// GLOBALE FUNCTIE: inline edit row toggle
// ==========================================
window.toggleEditRow = function (id) {
  const row = document.getElementById("edit-row-" + id);
  if (row) {
    row.style.display = (row.style.display === "none" || row.style.display === "") ? "table-row" : "none";
  }
};
