(function () {
  const AUTOSAVE_DEBOUNCE_MS = 1500;

  function loadJsonScript(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent || "null"); } catch (e) { return null; }
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }

  function csrfToken() {
    return getCookie("csrftoken");
  }

  function postForm(url, formData) {
    return fetch(url, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken() || "",
      },
      body: formData,
      credentials: "same-origin",
    });
  }

  // --------------------------
  // Date helpers
  // --------------------------
  function parseISODate(s) {
    const p = (s || "").split("-");
    if (p.length !== 3) return null;
    const y = parseInt(p[0], 10);
    const m = parseInt(p[1], 10);
    const d = parseInt(p[2], 10);
    if (!y || !m || !d) return null;
    const dt = new Date(y, m - 1, d);
    if (dt.getFullYear() !== y || dt.getMonth() !== (m - 1) || dt.getDate() !== d) return null;
    return dt;
  }

  function parseDMY(s) {
    const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec((s || "").trim());
    if (!m) return null;
    const dd = parseInt(m[1], 10);
    const mm = parseInt(m[2], 10);
    const yy = parseInt(m[3], 10);
    const d = new Date(yy, mm - 1, dd);
    if (d.getFullYear() !== yy || d.getMonth() !== (mm - 1) || d.getDate() !== dd) return null;
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function todayFromForm() {
    const form = document.getElementById("reviewPlannerForm");
    const iso = form ? form.getAttribute("data-today") : null;
    const dt = parseISODate(iso);
    return dt ? new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()) : null;
  }

  function cutoffFromForm() {
    const form = document.getElementById("reviewPlannerForm");
    const iso = form ? form.getAttribute("data-cutoff") : null;
    const dt = parseISODate(iso);
    return dt ? new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()) : null;
  }

  function validateNotPast(dmy) {
    const d = parseDMY(dmy);
    if (!d) return { ok: true };
    const today = todayFromForm();
    if (today && d < today) return { ok: false, error: "Datum mag niet in het verleden liggen." };
    const cutoff = cutoffFromForm();
    if (cutoff && d < cutoff) return { ok: false, error: "Datum mag niet verder dan 8 weken terug liggen." };
    return { ok: true };
  }

  // --------------------------
  // iMask
  // --------------------------
  function applyTimeMask(input) {
    if (!input || !window.IMask) return;
    window.IMask(input, {
      mask: "H{:}M",
      blocks: {
        H: { mask: window.IMask.MaskedRange, from: 0, to: 23, maxLength: 2 },
        M: { mask: window.IMask.MaskedRange, from: 0, to: 59, maxLength: 2 },
      },
    });
  }

  function applyDateMask(input) {
    if (!input || !window.IMask) return;
    const minYear = 1900;
    const maxYear = 2100;

    window.IMask(input, {
      mask: "d-m-Y",
      lazy: true,
      overwrite: true,
      autofix: false,
      blocks: {
        d: { mask: IMask.MaskedRange, from: 1, to: 31, maxLength: 2 },
        m: { mask: IMask.MaskedRange, from: 1, to: 12, maxLength: 2 },
        Y: { mask: IMask.MaskedRange, from: minYear, to: maxYear, maxLength: 4 },
      },
    });
  }

  // --------------------------
  // Select2 init
  // --------------------------
  function initSelect2(el, opts) {
    if (!el) return;
    const $ = window.jQuery;
    if (!$ || !$.fn || !$.fn.select2) return;

    const $el = $(el);

    if ($el.hasClass("select2-hidden-accessible")) {
      try { $el.select2("destroy"); } catch (e) {}
    }

    const config = Object.assign(
      {
        placeholder: "Klik om te zoeken...",
        allowClear: true,
        width: "100%",
      },
      opts || {}
    );

    $el.select2(config);

    $el.on("select2:open", function () {
      const searchField = document.querySelector(".select2-search__field");
      if (searchField) {
        searchField.placeholder = "Typ om te zoeken...";
        searchField.focus();
      }
    });
  }

  // --------------------------
  // Status pill
  // --------------------------
  function applyStatusPill(selectEl) {
    if (!selectEl) return;
    selectEl.classList.remove("rp-status--prep", "rp-status--sent", "rp-status--done");
    const v = (selectEl.value || "prep").trim();
    selectEl.classList.add(`rp-status--${v}`);
  }

  // --------------------------
  // Autosave
  // --------------------------
  let autosaveTimer = null;
  let lastSnapshot = null;

  function buildSnapshot() {
    const form = document.getElementById("reviewPlannerForm");
    if (!form) return "";

    const parts = [];
    form.querySelectorAll("tr.rp-row").forEach((row) => {
      const rid = row.querySelector('input[name="row_id"]')?.value || "";
      const datum = row.querySelector('input[name="row_datum"]')?.value?.trim() || "";
      const afd = row.querySelector('select[name="row_afdeling"]')?.value || "";
      const st = row.querySelector('select[name="row_status"]')?.value || "";
      const arts = row.querySelector('input[name="row_arts"]')?.value?.trim() || "";
      const tijd = row.querySelector('input[name="row_tijd"]')?.value?.trim() || "";
      const voorbereid = row.querySelector('select[name="row_voorbereid_door"]')?.value || "";
      const uitgevoerd = row.querySelector('select[name="row_uitgevoerd_door"]')?.value || "";
      const bijz = row.querySelector('input[name="row_bijzonderheden"]')?.value?.trim() || "";
      parts.push([rid, datum, afd, st, arts, tijd, voorbereid, uitgevoerd, bijz].join("|"));
    });

    return parts.join(";");
  }

  function buildAutosaveFormData() {
    const form = document.getElementById("reviewPlannerForm");
    const fd = new FormData();
    fd.append("action", "autosave");

    const rows = form.querySelectorAll("tr.rp-row");
    rows.forEach((row) => {
      fd.append("row_id", row.querySelector('input[name="row_id"]')?.value || "");
      fd.append("row_datum", row.querySelector('input[name="row_datum"]')?.value || "");
      fd.append("row_afdeling", row.querySelector('select[name="row_afdeling"]')?.value || "");
      fd.append("row_status", row.querySelector('select[name="row_status"]')?.value || "prep");
      fd.append("row_arts", row.querySelector('input[name="row_arts"]')?.value || "");
      fd.append("row_tijd", row.querySelector('input[name="row_tijd"]')?.value || "");
      fd.append("row_voorbereid_door", row.querySelector('select[name="row_voorbereid_door"]')?.value || "");
      fd.append("row_uitgevoerd_door", row.querySelector('select[name="row_uitgevoerd_door"]')?.value || "");
      fd.append("row_bijzonderheden", row.querySelector('input[name="row_bijzonderheden"]')?.value || "");
    });

    return fd;
  }

  function scheduleAutosave() {
    const form = document.getElementById("reviewPlannerForm");
    if (!form) return;

    const canEdit = form.getAttribute("data-can-edit") === "1";
    if (!canEdit) return;

    if (autosaveTimer) clearTimeout(autosaveTimer);

    autosaveTimer = setTimeout(async () => {
      const snapshot = buildSnapshot();
      if (snapshot === lastSnapshot) return;

      try {
        const resp = await postForm(window.location.href, buildAutosaveFormData());
        const data = await resp.json().catch(() => null);

        if (!resp.ok || !data || !data.ok) {
          console.warn("Autosave fout:", (data && data.error) ? data.error : "onbekend");
          return;
        }

        lastSnapshot = snapshot;
      } catch (e) {
        console.warn("Autosave netwerkfout");
      }
    }, AUTOSAVE_DEBOUNCE_MS);
  }

  // --------------------------
  // Table helpers
  // --------------------------
  function ensureEmptyRow() {
    const tbody = document.getElementById("reviewPlannerTbody");
    if (!tbody) return;

    const any = tbody.querySelector("tr.rp-row");
    const empty = document.getElementById("emptyRow");

    if (!any && !empty) {
      const tr = document.createElement("tr");
      tr.id = "emptyRow";
      tr.innerHTML = `<td colspan="9" class="muted">Nog geen items.</td>`;
      tbody.appendChild(tr);
    }
    if (any && empty) empty.remove();
  }

  function bindRow(tr) {
    if (!tr) return;

    const dateInp = tr.querySelector('input[name="row_datum"]');
    const timeInp = tr.querySelector('input[name="row_tijd"]');
    const afdSel = tr.querySelector('select[name="row_afdeling"]');
    const stSel = tr.querySelector('select[name="row_status"]');
    const voorbereidSel = tr.querySelector('select[name="row_voorbereid_door"]');
    const uitgevoerdSel = tr.querySelector('select[name="row_uitgevoerd_door"]');

    if (dateInp) applyDateMask(dateInp);
    if (timeInp) applyTimeMask(timeInp);
    if (afdSel) initSelect2(afdSel);

    if (stSel) applyStatusPill(stSel);

    const onChange = () => {
      if (stSel) applyStatusPill(stSel);

      if (dateInp && dateInp.value) {
        const v = validateNotPast(dateInp.value);
        dateInp.classList.toggle("is-invalid", !v.ok);
      }

      scheduleAutosave();
    };

    [dateInp, timeInp].forEach((inp) => {
      if (!inp) return;
      inp.addEventListener("input", onChange);
      inp.addEventListener("blur", onChange);
    });

    [afdSel, stSel].forEach((sel) => {
      if (!sel) return;
      const $ = window.jQuery;
      if ($ && $(sel).hasClass("select2-hidden-accessible")) {
        $(sel).off("change.rp_autosave").on("change.rp_autosave", onChange);
      } else {
        sel.addEventListener("change", onChange);
      }
    });

    [voorbereidSel, uitgevoerdSel].forEach((sel) => {
      if (!sel) return;
      sel.addEventListener("change", onChange);
    });

    const arts = tr.querySelector('input[name="row_arts"]');
    const bijz = tr.querySelector('input[name="row_bijzonderheden"]');
    [arts, bijz].forEach((inp) => {
      if (!inp) return;
      inp.addEventListener("input", onChange);
      inp.addEventListener("blur", onChange);
    });
  }

  function setupRemoveButtons() {
    document.querySelectorAll(".js-remove-row").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (!confirm("Weet je zeker dat je deze regel wilt verwijderen?")) return;
        const tr = btn.closest("tr");
        if (!tr) return;

        tr.querySelector('input[name="row_datum"]').value = "";

        const afd = tr.querySelector('select[name="row_afdeling"]');
        if (afd) {
          afd.value = "";
          try { window.jQuery(afd).trigger("change"); } catch (e) {}
        }

        tr.querySelector('input[name="row_arts"]').value = "";
        tr.querySelector('input[name="row_tijd"]').value = "";

        const voorbereid = tr.querySelector('select[name="row_voorbereid_door"]');
        if (voorbereid) voorbereid.value = "";

        const uitgevoerd = tr.querySelector('select[name="row_uitgevoerd_door"]');
        if (uitgevoerd) uitgevoerd.value = "";

        tr.querySelector('input[name="row_bijzonderheden"]').value = "";

        scheduleAutosave();

        tr.remove();
        ensureEmptyRow();
      });
    });
  }

  // --------------------------
  // Modal
  // --------------------------
  function setModalMsg(text, isError) {
    const el = document.getElementById("modalMsg");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = isError ? "var(--danger)" : "var(--muted)";
  }

  async function modalSave() {
    const datum = (document.getElementById("modalDatum")?.value || "").trim();
    const v = validateNotPast(datum);
    if (!v.ok) return { ok: false, error: v.error };

    const fd = new FormData();
    fd.append("action", "modal_upsert");
    fd.append("datum", datum);
    fd.append("afdeling_id", (document.getElementById("modalAfdeling")?.value || "").trim());
    fd.append("status", (document.getElementById("modalStatus")?.value || "prep").trim());
    fd.append("arts", (document.getElementById("modalArts")?.value || "").trim());
    fd.append("tijd", (document.getElementById("modalTijd")?.value || "").trim());
    fd.append("voorbereid_door", (document.getElementById("modalVoorbereidDoor")?.value || "").trim());
    fd.append("uitgevoerd_door", (document.getElementById("modalUitgevoerdDoor")?.value || "").trim());
    fd.append("bijzonderheden", (document.getElementById("modalBijzonderheden")?.value || "").trim());

    const resp = await postForm(window.location.href, fd);
    const data = await resp.json().catch(() => null);

    if (!resp.ok || !data || !data.ok) {
      return { ok: false, error: (data && data.error) ? data.error : "Opslaan mislukt." };
    }
    return { ok: true, row: data.row };
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function buildAfdelingOptionsHtml(afdelingen, selectedId) {
    const sel = String(selectedId || "");
    let html = `<option value=""></option>`;
    (afdelingen || []).forEach((a) => {
      const id = String(a.id);
      const isSel = (id === sel) ? " selected" : "";
      html += `<option value="${escapeHtml(id)}"${isSel}>${escapeHtml(a.label)}</option>`;
    });
    return html;
  }

  function buildUserOptionsHtml(users, selectedId) {
    const sel = String(selectedId || "");
    let html = `<option value=""></option>`;
    (users || []).forEach((u) => {
      const id = String(u.id);
      const isSel = (id === sel) ? " selected" : "";
      html += `<option value="${escapeHtml(id)}"${isSel}>${escapeHtml(u.label)}</option>`;
    });
    return html;
  }

  function upsertRowInTable(rowData) {
    const tbody = document.getElementById("reviewPlannerTbody");
    if (!tbody) return;

    ensureEmptyRow();

    let tr = tbody.querySelector(`tr.rp-row[data-id="${rowData.id}"]`);

    if (!tr) {
      tr = document.createElement("tr");
      tr.className = "rp-row";
      tr.setAttribute("data-id", String(rowData.id));
      tr.innerHTML = `
        <td>
          <input type="hidden" name="row_id" value="${escapeHtml(rowData.id)}">
          <input type="text" name="row_datum" value=""
                 class="admin-input rp-date js-date" placeholder="dd-mm-jjjj" inputmode="numeric" autocomplete="off">
        </td>

        <td>
          <select name="row_afdeling" class="select2-single rp-afdeling js-afdeling" style="width:100%;"></select>
        </td>

        <td>
          <select name="row_status" class="admin-input rp-status js-status">
            <option value="prep">In voorbereiding</option>
            <option value="sent">Verstuurd</option>
            <option value="done">Uitgevoerd</option>
          </select>
        </td>

        <td>
          <input type="text" name="row_arts" value=""
                 class="admin-input rp-arts js-arts" placeholder="Naam van arts..." autocomplete="off">
        </td>

        <td>
          <input type="text" name="row_tijd" value=""
                 class="admin-input rp-time js-time" placeholder="uu:mm" inputmode="numeric" autocomplete="off">
        </td>

        <td>
          <select name="row_voorbereid_door" class="admin-input"></select>
        </td>

        <td>
          <select name="row_uitgevoerd_door" class="admin-input"></select>
        </td>

        <td class="wrap">
          <input type="text" name="row_bijzonderheden" value=""
                 class="admin-input rp-notes js-notes" placeholder="Bijzonderheden..." autocomplete="off">
        </td>

        <td class="center-col">
          <button type="button" class="icon-btn danger js-remove-row" aria-label="Verwijderen">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1 2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              <line x1="10" y1="11" x2="10" y2="17"/>
              <line x1="14" y1="11" x2="14" y2="17"/>
            </svg>
          </button>
        </td>
      `;
      tbody.prepend(tr);
    }

    tr.querySelector('input[name="row_datum"]').value = rowData.datum || "";

    const afdSel = tr.querySelector('select[name="row_afdeling"]');
    if (afdSel) afdSel.innerHTML = buildAfdelingOptionsHtml(afdelingenCache, rowData.afdeling_id);

    const stSel = tr.querySelector('select[name="row_status"]');
    if (stSel) {
      stSel.value = rowData.status || "prep";
      applyStatusPill(stSel);
    }

    tr.querySelector('input[name="row_arts"]').value = rowData.arts || "";
    tr.querySelector('input[name="row_tijd"]').value = rowData.tijd || "";

    const voorbereidSel = tr.querySelector('select[name="row_voorbereid_door"]');
    if (voorbereidSel) voorbereidSel.innerHTML = buildUserOptionsHtml(usersCache, rowData.voorbereid_door_id);

    const uitgevoerdSel = tr.querySelector('select[name="row_uitgevoerd_door"]');
    if (uitgevoerdSel) uitgevoerdSel.innerHTML = buildUserOptionsHtml(usersCache, rowData.uitgevoerd_door_id);

    tr.querySelector('input[name="row_bijzonderheden"]').value = rowData.bijzonderheden || "";

    bindRow(tr);
    setupRemoveButtons();
    ensureEmptyRow();

    lastSnapshot = buildSnapshot();
  }

  function openModal() {
    const modal = document.getElementById("addModal");
    if (!modal) return;

    modal.style.display = "block";
    document.body.style.overflow = "hidden";
    setModalMsg("", false);

    applyDateMask(document.getElementById("modalDatum"));
    applyTimeMask(document.getElementById("modalTijd"));

    const modalAfd = document.getElementById("modalAfdeling");
    initSelect2(modalAfd, { dropdownParent: window.jQuery("#addModal .modal-content") });
    try { window.jQuery(modalAfd).val("").trigger("change"); } catch (e) {}

    const st = document.getElementById("modalStatus");
    if (st) {
      st.value = "prep";
      applyStatusPill(st);
      st.addEventListener("change", () => applyStatusPill(st));
    }

    const vd = document.getElementById("modalVoorbereidDoor");
    if (vd) vd.value = "";

    const ud = document.getElementById("modalUitgevoerdDoor");
    if (ud) ud.value = "";

    const bz = document.getElementById("modalBijzonderheden");
    if (bz) bz.value = "";
  }

  function closeModal() {
    const modal = document.getElementById("addModal");
    if (!modal) return;
    modal.style.display = "none";
    document.body.style.overflow = "";
    setModalMsg("", false);
  }

  function setupModalActions() {
    const openBtn = document.getElementById("openAddModalBtn");
    const closeBtn = document.getElementById("closeAddModalBtn");
    const cancelBtn = document.getElementById("modalCancelBtn");
    const addBtn = document.getElementById("modalAddBtn");
    const modal = document.getElementById("addModal");

    if (openBtn) openBtn.addEventListener("click", openModal);
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
      });
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const m = document.getElementById("addModal");
        if (m && m.style.display === "block") closeModal();
      }
    });

    if (addBtn) {
      addBtn.addEventListener("click", async () => {
        setModalMsg("Opslaan...", false);
        const res = await modalSave();
        if (!res.ok) {
          setModalMsg(res.error || "Opslaan mislukt.", true);
          return;
        }
        upsertRowInTable(res.row);
        closeModal();
      });
    }
  }

  // --------------------------
  // Init
  // --------------------------
  let afdelingenCache = [];
  let usersCache = [];

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("reviewPlannerForm");
    if (!form) return;

    afdelingenCache = loadJsonScript("afdelingenJson") || [];
    usersCache = loadJsonScript("eligibleUsersJson") || [];

    document.querySelectorAll("tr.rp-row").forEach((tr) => bindRow(tr));
    setupRemoveButtons();
    ensureEmptyRow();

    lastSnapshot = buildSnapshot();

    setupModalActions();

    document.addEventListener("change", (e) => {
      if (e.target && e.target.matches('select[name="row_status"]')) {
        applyStatusPill(e.target);
        scheduleAutosave();
      }
    });
  });
})();
