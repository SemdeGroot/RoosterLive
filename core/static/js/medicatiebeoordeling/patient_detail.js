document.addEventListener("DOMContentLoaded", function () {
    let formDirty = false;

    // 1. Luister op document-niveau naar ELKE input
    // Dit werkt altijd, zelfs als de selector 'form' faalt
    document.addEventListener('input', function (e) {
        if (e.target.closest('form')) {
            formDirty = true;
        }
    });

    // 2. Vlag uitzetten bij verzenden
    document.addEventListener('submit', function (e) {
        formDirty = false;
    });

    // 3. Specifieke afvanging voor de Terug-knop via de class of ID
    document.addEventListener('click', function (e) {
        // We kijken of de klik op de terug-knop was (via ID of de btn-danger class)
        const isBackBtn = e.target.id === 'backBtn' || e.target.closest('#backBtn');
        
        if (isBackBtn && formDirty) {
            const confirmLeave = confirm("Je hebt onopgeslagen wijzigingen. Wil je de pagina verlaten?");
            if (!confirmLeave) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        }
    });

    // 4. Tab sluiten / Browser navigatie
    window.addEventListener('beforeunload', function (e) {
        if (formDirty) {
            e.preventDefault();
            e.returnValue = ''; 
        }
    });
    
  // ==========================================
  // 1. BUILD TEXT (per Jansen categorie)
  //    - met medicatie: (optioneel titel) + middelen + opmerkingen
  //    - zonder medicatie: titel + opmerkingen
  // ==========================================
  function buildMedimoTextFromGroup(groupEl, groupId, includeTitle = false) {
    // Medicatie + gebruik
    const rows = groupEl.querySelectorAll("table.med-table tbody tr");
    const lines = [];

    rows.forEach((tr) => {
      const tds = tr.querySelectorAll("td");
      if (tds.length >= 2) {
        const middel = (tds[0].innerText || "").trim();
        const gebruik = (tds[1].innerText || "").trim();
        if (middel || gebruik) lines.push(`${middel}: ${gebruik}`);
      }
    });

    // Titel
    const titleEl = groupEl.querySelector(".jansen-title");
    const title = (titleEl?.innerText || "").trim();

    // Opmerkingen (textarea)
    const commentTa = groupEl.querySelector(`textarea[name="comment_${groupId}"]`);
    const commentVal = commentTa ? (commentTa.value || "").trim() : "";

    // GEEN MEDICATIE: titel + opmerkingen
    if (lines.length === 0) {
      let text = title || "";
      if (commentVal) {
        text += `\n\nOpmerkingen:\n${commentVal}`;
      }
      return text.trim();
    }

    // WEL MEDICATIE
    let text = "";

    if (includeTitle && title) {
      // harde enter tussen titel en geneesmiddelen
      text += `${title}\n\n`;
    }

    text += lines.join("\n");

    if (commentVal) {
      text += `\n\nOpmerkingen:\n${commentVal}`;
    }

    return text.trim();
  }

  // ==========================================
  // 2. CLIPBOARD HELPER
  // ==========================================
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

  // ==========================================
  // 3. COPY PER CATEGORIE
  // ==========================================
  document.querySelectorAll(".btn-copy-medimo").forEach((btn) => {
    // skip de copy-all knop (die gebruikt dezelfde styling class)
    if (btn.classList.contains("btn-copy-all-medimo")) return;

    btn.addEventListener("click", async () => {
      const groupId = btn.getAttribute("data-group-id");
      const groupEl = btn.closest(".med-group");
      if (!groupEl || !groupId) return;

      // per-categorie: geen titel, behalve als je dat ooit wil veranderen
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

  // ==========================================
  // 4. COPY ALL FOR MEDIMO
  //    - altijd titel
  //    - harde enter tussen titel en middelen
  //    - bij geen medicatie: titel + opmerkingen
  // ==========================================
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
