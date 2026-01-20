// static/js/urendoorgeven/urendoorgeven.js
(function () {
  // --------------------------
  // Config
  // --------------------------
  const AUTOSAVE_DEBOUNCE_MS = 2000; // pas autosave als user X sec stopt met typen

  // --------------------------
  // Helpers
  // --------------------------
  function pad2(n) { return String(n).padStart(2, "0"); }

  function timeStrToMinutes(hhmm) {
    const m = /^(\d{2}):(\d{2})$/.exec(String(hhmm || "").trim());
    if (!m) return null;
    const hh = parseInt(m[1], 10);
    const mm = parseInt(m[2], 10);
    if (!Number.isFinite(hh) || !Number.isFinite(mm)) return null;
    return hh * 60 + mm;
  }

  // dagdeelMeta start/end -> geschatte uren (1 decimaal)
  function estimatedHoursForDagdeelId(dagdeelId) {
    const meta = dagdeelMeta[String(dagdeelId)];
    if (!meta) return null;

    const s = timeStrToMinutes(meta.start);
    const e = timeStrToMinutes(meta.end);
    if (s == null || e == null) return null;

    let mins = 0;
    if (e === s) mins = 0;
    else if (e > s) mins = e - s;
    else mins = (1440 - s) + e; // over midnight

    const hrs = mins / 60;
    return Math.round(hrs * 10) / 10; // 1 dec
  }

  function showHoursWarning(warnEl, text) {
    if (!warnEl) return;
    if (!text) {
      warnEl.textContent = "";
      warnEl.style.display = "none";
      return;
    }
    warnEl.textContent = text;
    warnEl.style.display = "block";
  }

  function formatCountdown(ms) {
    if (ms <= 0) return "Deadline verstreken";
    const totalMinutes = Math.floor(ms / 60000);
    const days = Math.floor(totalMinutes / (60 * 24));
    const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
    const minutes = totalMinutes % 60;
    return `${days} dagen ${pad2(hours)}:${pad2(minutes)}`;
  }

  function dateToISO(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }

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

  function isoToDMY(iso) {
    const dt = parseISODate(iso);
    if (!dt) return iso;
    return `${pad2(dt.getDate())}-${pad2(dt.getMonth() + 1)}-${dt.getFullYear()}`;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function toNumberHours(v) {
    if (v == null) return 0;
    let s = String(v).trim();
    if (!s) return 0;
    s = s.replace(",", ".");
    s = s.replace(/[^\d.]/g, "");
    if (!s) return 0;
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : 0;
  }

  function format1(n) {
    const x = Math.round(n * 10) / 10;
    return x.toFixed(1).replace(".", ",");
  }

  function validateHoursVsEstimated({ inputEl, dagdeelId, warnEl, mode }) {
    // mode: "table" of "modal" (alleen tekstverschil)
    if (!inputEl || !dagdeelId) return;

    const v = (inputEl.value || "").trim();
    if (!v) {
      showHoursWarning(warnEl, "");
      return;
    }

    const entered = toNumberHours(v); // al in jouw file aanwezig
    const est = estimatedHoursForDagdeelId(dagdeelId);

    if (est == null) {
      showHoursWarning(warnEl, "");
      return;
    }

    // vergelijking op 0.1 nauwkeurig
    const diff = Math.round((entered - est) * 10) / 10;
    if (diff === 0) {
      showHoursWarning(warnEl, "");
      return;
    }

    const estLabel = format1(est);
    const enteredLabel = format1(entered);

    const txt =
      mode === "modal"
        ? `Ingevuld ${enteredLabel} uur, geschat ${estLabel} uur. Klopt dit?`
        : `Ingevuld ${enteredLabel} uur, geschat ${estLabel} uur. Klopt dit?`;

    showHoursWarning(warnEl, txt);
  }


  // --------------------------
  // CSRF + Fetch helpers
  // --------------------------
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

  function loadJsonScript(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent || "null"); } catch (e) { return null; }
  }

  // --------------------------
  // Window bounds
  // --------------------------
  function getWindowBounds() {
    const form = document.getElementById("urenForm");
    const startIso = form ? form.getAttribute("data-window-start") : null;
    const endIso = form ? form.getAttribute("data-window-end") : null; // exclusive
    return { startIso, endIso };
  }

  function isDateInWindow(iso) {
    const { startIso, endIso } = getWindowBounds();
    if (!startIso || !endIso) return true;
    return iso >= startIso && iso < endIso;
  }

  // --------------------------
  // Deadline countdown
  // --------------------------
  function setupCountdown() {
    const bar = document.querySelector(".uren-deadline-bar");
    const timerEl = document.getElementById("deadlineTimer");
    if (!bar || !timerEl) return;

    const iso = bar.getAttribute("data-deadline");
    if (!iso) { timerEl.textContent = "—"; return; }
    const deadline = new Date(iso);
    if (Number.isNaN(deadline.getTime())) { timerEl.textContent = "—"; return; }

    const tick = () => {
      const now = new Date();
      timerEl.textContent = formatCountdown(deadline.getTime() - now.getTime());
    };

    tick();
    setInterval(tick, 30000);
  }

  // --------------------------
  // Decimal input behavior (max 1 dec)
  // --------------------------
  function allowDecimalTyping(input) {
    let v = input.value;
    v = v.replace(/[^\d,\.]/g, "");

    const firstSep = v.search(/[,.]/);
    if (firstSep !== -1) {
      const before = v.slice(0, firstSep + 1);
      const after = v.slice(firstSep + 1).replace(/[,.]/g, "");
      v = before + after;
    }

    const parts = v.split(/[,.]/);
    if (parts.length === 2) {
      const sep = v.includes(",") ? "," : ".";
      v = parts[0] + sep + (parts[1] || "").slice(0, 1);
    }
    input.value = v;
  }

  function normalizeOneDecimal(input) {
    let v = (input.value || "").trim();
    if (v === "") return;

    v = v.replace(",", ".");
    v = v.replace(/[^\d.]/g, "");

    const parts = v.split(".");
    if (parts.length > 2) v = parts[0] + "." + parts.slice(1).join("");

    if (v.includes(".")) {
      const [a, b] = v.split(".");
      v = a + "." + (b || "").slice(0, 1);
    }
    input.value = v.replace(".", ",");
  }

  // --------------------------
  // Totals
  // --------------------------
  function recalcTotals() {
    const rows = document.querySelectorAll("tr.uren-row");
    let sumHours = 0;
    let sumWeighted = 0;

    rows.forEach((row) => {
      const allowancePct = parseFloat(row.getAttribute("data-allowance-pct") || "100");
      const mult = (Number.isFinite(allowancePct) ? allowancePct : 100) / 100;

      const inp = row.querySelector('input[name="row_hours"]');
      const hours = toNumberHours(inp ? inp.value : 0);
      const weighted = hours * mult;

      sumHours += hours;
      sumWeighted += weighted;

      const wEl = row.querySelector(".weighted-value");
      if (wEl) wEl.textContent = format1(weighted);
    });

    const sumHoursEl = document.getElementById("sumHours");
    const sumWeightedEl = document.getElementById("sumWeighted");
    if (sumHoursEl) sumHoursEl.textContent = format1(sumHours);
    if (sumWeightedEl) sumWeightedEl.textContent = format1(sumWeighted);
  }

  function renumberRows() {
    document.querySelectorAll("tr.uren-row").forEach((row, i) => {
      const idxCell = row.querySelector("td.center-col");
      if (idxCell) idxCell.textContent = String(i + 1);
    });
  }

  function ensureEmptyRow() {
    const tbody = document.getElementById("urenTbody");
    if (!tbody) return;
    const any = tbody.querySelector("tr.uren-row");
    const empty = document.getElementById("emptyRow");
    if (!any && !empty) {
      const tr = document.createElement("tr");
      tr.id = "emptyRow";
      tr.innerHTML = `<td colspan="6" class="muted">Nog geen regels. Klik op “Diensten toevoegen”.</td>`;
      tbody.appendChild(tr);
    }
    if (any && empty) empty.remove();
  }

  // --------------------------
  // Autosave: only POST when changed + debounce
  // --------------------------
  let autosaveTimer = null;
  let lastSnapshot = null;

  function setAutosaveOk(isOk) {
    const el = document.getElementById("autosaveStatus");
    if (!el) return;
    el.classList.toggle("autosave-ok", !!isOk);
    el.classList.toggle("autosave-bad", isOk === false);
  }

  function setAutosaveStatus(text, okState /* true/false/null */) {
    const el = document.getElementById("autosaveStatus");
    if (!el) return;
    el.textContent = text;
    if (okState === true) setAutosaveOk(true);
    else if (okState === false) setAutosaveOk(false);
  }

  function buildSnapshot() {
    const form = document.getElementById("urenForm");
    if (!form) return "";

    const parts = [];

    form.querySelectorAll("tr.uren-row").forEach((row) => {
      const date = row.getAttribute("data-date") || "";
      const did = row.getAttribute("data-dagdeel-id") || "";
      const inp = row.querySelector('input[name="row_hours"]');
      const hours = inp ? (inp.value || "").trim() : "";
      parts.push(`${date}|${did}|${hours}`);
    });

    const km = form.querySelector('input[name="kilometers"]');
    parts.push(`km|${km ? (km.value || "").trim() : ""}`);

    return parts.join(";");
  }

  function buildAutosaveFormData() {
    const form = document.getElementById("urenForm");
    const fd = new FormData();

    fd.append("action", "autosave");

    const rowDates = form.querySelectorAll('input[name="row_date"]');
    const rowDagdeel = form.querySelectorAll('input[name="row_dagdeel_id"]');
    const rowHours = form.querySelectorAll('input[name="row_hours"]');

    const n = Math.min(rowDates.length, rowDagdeel.length, rowHours.length);
    for (let i = 0; i < n; i++) {
      fd.append("row_date", rowDates[i].value);
      fd.append("row_dagdeel_id", rowDagdeel[i].value);
      fd.append("row_hours", rowHours[i].value);
    }

    const km = form.querySelector('input[name="kilometers"]');
    if (km) fd.append("kilometers", km.value);

    return fd;
  }

  function scheduleAutosave() {
    if (autosaveTimer) clearTimeout(autosaveTimer);

    setAutosaveStatus("Wijzigingen...", null);

    autosaveTimer = setTimeout(async () => {
      const snapshot = buildSnapshot();
      if (snapshot === lastSnapshot) {
        setAutosaveStatus("Opgeslagen ✅", true);
        return;
      }

      setAutosaveStatus("Opslaan...", null);

      try {
        const resp = await postForm(window.location.href, buildAutosaveFormData());
        const data = await resp.json().catch(() => null);

        if (!resp.ok || !data || !data.ok) {
          setAutosaveStatus((data && data.error) ? data.error : "Auto-save fout", false);
          return;
        }

        lastSnapshot = snapshot;
        setAutosaveStatus("Opgeslagen ✅", true);
      } catch (e) {
        setAutosaveStatus("Netwerkfout", false);
      }
    }, AUTOSAVE_DEBOUNCE_MS);
  }

  // --------------------------
  // Bind main table inputs + delete confirm
  // --------------------------
  function bindHoursInput(input) {
    if (!input) return;

    const tr = input.closest("tr.uren-row");
    const dagdeelId = tr ? tr.getAttribute("data-dagdeel-id") : null;
    const warnEl = tr ? tr.querySelector(".hours-warning") : null;

    input.addEventListener("input", () => {
      allowDecimalTyping(input);
      validateHoursVsEstimated({ inputEl: input, dagdeelId, warnEl, mode: "table" });
      recalcTotals();
      scheduleAutosave();
    });

    input.addEventListener("blur", () => {
      normalizeOneDecimal(input);
      validateHoursVsEstimated({ inputEl: input, dagdeelId, warnEl, mode: "table" });
      recalcTotals();
      scheduleAutosave();
    });

    // initial validation on bind
    validateHoursVsEstimated({ inputEl: input, dagdeelId, warnEl, mode: "table" });
  }


  function setupExistingInputs() {
    document.querySelectorAll('input[name="row_hours"]').forEach((inp) => bindHoursInput(inp));

    const km = document.querySelector('input[name="kilometers"]');
    if (km) {
      km.addEventListener("input", () => scheduleAutosave());
      km.addEventListener("blur", () => scheduleAutosave());
    }

    const form = document.getElementById("urenForm");
    if (form) {
      form.addEventListener("submit", () => {
        document.querySelectorAll('input[name="row_hours"]').forEach((inp) => normalizeOneDecimal(inp));
      });
    }
  }

  function setupRemoveButtons() {
    document.querySelectorAll(".js-remove-row").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (!confirm("Weet je zeker dat je deze regel wilt verwijderen?")) return;
        const tr = btn.closest("tr");
        if (!tr) return;
        tr.remove();
        renumberRows();
        recalcTotals();
        ensureEmptyRow();
        scheduleAutosave();
      });
    });
  }

  // --------------------------
  // Upsert rows in main table from modal response
  // --------------------------
  function upsertRowInTable(rowData) {
    const tbody = document.getElementById("urenTbody");
    if (!tbody) return;

    ensureEmptyRow();

    const iso = rowData.date;
    const did = String(rowData.dagdeel_id);

    const existing = tbody.querySelector(`tr.uren-row[data-date="${iso}"][data-dagdeel-id="${did}"]`);
    if (existing) {
      const inp = existing.querySelector('input[name="row_hours"]');
      if (inp) inp.value = rowData.actual_hours || "";
      if (inp) normalizeOneDecimal(inp);
      recalcTotals();
      return;
    }

    const tr = document.createElement("tr");
    tr.className = "uren-row";
    tr.setAttribute("data-date", iso);
    tr.setAttribute("data-dagdeel-id", did);
    tr.setAttribute("data-allowance-pct", String(rowData.allowance_pct || 100));

    tr.innerHTML = `
      <td class="center-col" style="color:var(--muted);">—</td>
      <td><strong>${escapeHtml(rowData.date_label || isoToDMY(iso))}</strong></td>
      <td>
        ${escapeHtml(rowData.dagdeel_label || "Dagdeel")}
        <div class="muted" style="font-size:.85rem;">
          ${escapeHtml(rowData.start || "")}–${escapeHtml(rowData.end || "")}
        </div>
      </td>
      <td>
        <input type="hidden" name="row_date" value="${escapeHtml(iso)}">
        <input type="hidden" name="row_dagdeel_id" value="${escapeHtml(did)}">
        <input
          type="text"
          name="row_hours"
          value="${escapeHtml(rowData.actual_hours || "")}"
          class="admin-input uren-hours-input"
          inputmode="decimal"
          placeholder="0,0"
          autocomplete="off"
        >
        <div class="hours-warning" style="margin-top:4px; display:none;"></div>
      </td>
      <td class="weighted-cell">
        <strong class="weighted-value">0,0</strong>
      </td>
      <td class="center-col">
        <button type="button" class="icon-btn danger js-remove-row" aria-label="Verwijderen">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            <line x1="10" y1="11" x2="10" y2="17"/>
            <line x1="14" y1="11" x2="14" y2="17"/>
          </svg>
        </button>
      </td>
    `;

    tbody.appendChild(tr);

    const inp = tr.querySelector('input[name="row_hours"]');
    bindHoursInput(inp);

    const removeBtn = tr.querySelector(".js-remove-row");
    if (removeBtn) {
      removeBtn.addEventListener("click", () => {
        if (!confirm("Weet je zeker dat je deze regel wilt verwijderen?")) return;
        tr.remove();
        renumberRows();
        recalcTotals();
        ensureEmptyRow();
        scheduleAutosave();
      });
    }

    renumberRows();
    recalcTotals();
  }

  // --------------------------
  // Modal: planned dots + existing hours prefill + UNSAVED confirm
  // --------------------------
  let plannedByDate = {};
  let existingByDate = {};
  let dagdeelMeta = {};

  let modalFp = null;
  let modalCurrentIso = null;
  let modalDirty = false;
  let modalSnapshotByIso = {};

  function getModalSelectedISO() {
    const input = document.getElementById("modalDate");
    const val = input ? (input.value || "").trim() : "";
    const dt = parseISODate(val);
    if (dt) return dateToISO(dt);
    // flatpickr may format differently, but we set alt off -> should be ISO
    return val && val.length === 10 ? val : null;
  }

  function buildModalSnapshot() {
    const iso = modalCurrentIso || getModalSelectedISO();
    const container = document.getElementById("modalDagdeelList");
    if (!iso || !container) return "";
    const parts = [];
    container.querySelectorAll(".modal-hours-input").forEach((inp) => {
      const did = inp.getAttribute("data-dagdeel-id") || "";
      const val = (inp.value || "").trim();
      parts.push(`${did}=${val}`);
    });
    return parts.join("|");
  }

  function setModalDirtyFromInputs() {
    if (!modalCurrentIso) return;
    const snap = buildModalSnapshot();
    const base = modalSnapshotByIso[modalCurrentIso] || "";
    modalDirty = (snap !== base);
  }

  function setModalMsg(text, isError) {
    const el = document.getElementById("modalMsg");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = isError ? "var(--danger)" : "var(--muted)";
  }

  function buildDagdeelOptions(forIsoDate) {
    const container = document.getElementById("modalDagdeelList");
    if (!container) return;

    container.innerHTML = "";

    const plannedSet = new Set((plannedByDate[forIsoDate] || []).map(String));
    const existingMap = existingByDate[forIsoDate] || {};

    const entries = Object.entries(dagdeelMeta); // [id, {label, allowance_pct, start, end}]
    entries.forEach(([id, meta]) => {
      const isPlanned = plannedSet.has(String(id));
      const existingVal = (existingMap[String(id)] || "").trim();

      const row = document.createElement("div");
      row.className = "uren-dagdeel-option";
      row.setAttribute("data-dagdeel-id", String(id));

      row.innerHTML = `
      <div class="uren-dagdeel-top">
        <div class="uren-dagdeel-left">
          <span class="planned-dot ${isPlanned ? "" : "muted"}"></span>
          <div>
            <div style="font-weight:700;">${escapeHtml(meta.label || "Dagdeel")}</div>
            <div class="muted" style="font-size:.85rem;">
              ${escapeHtml(meta.start || "")}–${escapeHtml(meta.end || "")}
            </div>
          </div>
        </div>

        <div style="display:flex; align-items:center; gap:10px;">
          <input
            type="text"
            class="admin-input uren-hours-input modal-hours-input"
            data-dagdeel-id="${escapeHtml(String(id))}"
            value="${escapeHtml(existingVal)}"
            inputmode="decimal"
            placeholder="0,0"
            autocomplete="off"
            style="width:110px;"
          />
          <button type="button" class="icon-btn danger modal-clear-btn" title="Leegmaken" aria-label="Leegmaken">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              <line x1="10" y1="11" x2="10" y2="17"/>
              <line x1="14" y1="11" x2="14" y2="17"/>
            </svg>
          </button>
        </div>
      </div>

      <div class="hours-warning modal-warning" style="margin-top:6px; display:none;"></div>
    `;

      container.appendChild(row);

      const hoursInput = row.querySelector(".modal-hours-input");
      const clearBtn = row.querySelector(".modal-clear-btn");
      const warnEl = row.querySelector(".modal-warning");

      if (hoursInput) {
        hoursInput.addEventListener("input", () => {
          allowDecimalTyping(hoursInput);
          validateHoursVsEstimated({ inputEl: hoursInput, dagdeelId: id, warnEl, mode: "modal" });
          setModalDirtyFromInputs();
        });
        hoursInput.addEventListener("blur", () => {
          normalizeOneDecimal(hoursInput);
          validateHoursVsEstimated({ inputEl: hoursInput, dagdeelId: id, warnEl, mode: "modal" });
          setModalDirtyFromInputs();
        });

        // initial check
        validateHoursVsEstimated({ inputEl: hoursInput, dagdeelId: id, warnEl, mode: "modal" });
      }

      if (clearBtn) {
        clearBtn.addEventListener("click", () => {
          if (!confirm("Weet je zeker dat je deze uren wilt leegmaken?")) return;
          if (hoursInput) hoursInput.value = "";
          validateHoursVsEstimated({ inputEl: hoursInput, dagdeelId: id, warnEl, mode: "modal" });
          setModalDirtyFromInputs();
        });
      }
    });

    // baseline snapshot after render
    modalSnapshotByIso[forIsoDate] = buildModalSnapshot();
    modalDirty = false;
  }

  async function saveModalForIso(iso) {
    const container = document.getElementById("modalDagdeelList");
    if (!container) return { ok: false, error: "Modal niet beschikbaar." };

    const inputs = Array.from(container.querySelectorAll(".modal-hours-input"));
    const chosen = [];
    inputs.forEach((inp) => {
      const did = inp.getAttribute("data-dagdeel-id");
      const val = (inp.value || "").trim();
      if (did && val !== "") chosen.push({ did, val });
    });

    // niets ingevuld -> markeer clean
    if (chosen.length === 0) {
      modalSnapshotByIso[iso] = buildModalSnapshot();
      modalDirty = false;
      return { ok: true, rows: [] };
    }

    // normalize to 1 decimal (comma)
    chosen.forEach((x) => {
      let v = String(x.val || "").trim();
      v = v.replace(",", ".");
      v = v.replace(/[^\d.]/g, "");
      const parts = v.split(".");
      if (parts.length > 2) v = parts[0] + "." + parts.slice(1).join("");
      if (v.includes(".")) {
        const [a, b] = v.split(".");
        v = a + "." + (b || "").slice(0, 1);
      }
      x.val = v.replace(".", ",");
    });

    const fd = new FormData();
    fd.append("action", "modal_batch_upsert");
    fd.append("date", iso);
    chosen.forEach((x) => {
      fd.append("dagdeel_id", x.did);
      fd.append("hours", x.val);
    });

    const resp = await postForm(window.location.href, fd);
    const data = await resp.json().catch(() => null);

    if (!resp.ok || !data || !data.ok) {
      return { ok: false, error: (data && data.error) ? data.error : "Opslaan mislukt." };
    }

    const rows = data.rows || [];
    rows.forEach((r) => upsertRowInTable(r));

    // update local cache
    existingByDate[iso] = existingByDate[iso] || {};
    rows.forEach((r) => {
      existingByDate[iso][String(r.dagdeel_id)] = r.actual_hours || "";
    });

    // baseline snapshot
    modalSnapshotByIso[iso] = buildModalSnapshot();
    modalDirty = false;

    // main snapshot refresh + green tick
    lastSnapshot = buildSnapshot();
    setAutosaveStatus("Opgeslagen ✅", true);

    return { ok: true, rows };
  }

  async function maybeSaveBeforeLeavingModal(nextActionLabel) {
    // returns true if it's ok to continue (either saved, or user chose discard)
    if (!modalCurrentIso) return true;

    setModalDirtyFromInputs();
    if (!modalDirty) return true;

    const dmy = isoToDMY(modalCurrentIso);
    const ok = confirm(`Je hebt onopgeslagen wijzigingen voor ${dmy}. Wil je opslaan?`);
    if (ok) {
      setModalMsg("Opslaan...", false);
      try {
        const res = await saveModalForIso(modalCurrentIso);
        if (!res.ok) {
          setModalMsg(res.error || "Opslaan mislukt.", true);
          return false; // block leaving
        }
        setModalMsg("Opgeslagen.", false);
        return true;
      } catch (e) {
        setModalMsg("Netwerkfout.", true);
        return false;
      }
    }

    // discard changes
    setModalMsg("", false);
    modalDirty = false;
    modalSnapshotByIso[modalCurrentIso] = buildModalSnapshot(); // treat current as baseline now
    return true;
  }

  // --------------------------
  // Modal open/close
  // --------------------------
  function openModal() {
    const modal = document.getElementById("addModal");
    if (!modal) return;
    modal.style.display = "block";
    document.body.style.overflow = "hidden";
    setModalMsg("", false);

    const input = document.getElementById("modalDate");
    if (!input) return;

    const bounds = getWindowBounds();
    const minDate = bounds.startIso || null;
    const maxDate = bounds.endIso ? parseISODate(bounds.endIso) : null;
    const maxIso = maxDate ? dateToISO(new Date(maxDate.getFullYear(), maxDate.getMonth(), maxDate.getDate() - 1)) : null;

    // choose initial date
    let initialIso = null;
    const existingIso = getModalSelectedISO();
    if (existingIso && isDateInWindow(existingIso)) initialIso = existingIso;
    else if (plannedByDate && Object.keys(plannedByDate).length > 0) initialIso = Object.keys(plannedByDate)[0];
    else if (minDate) initialIso = minDate;

    if (!initialIso) initialIso = dateToISO(new Date());

    // init flatpickr once
    if (!modalFp && window.flatpickr) {
      modalFp = window.flatpickr(input, {
        dateFormat: "Y-m-d",
        defaultDate: initialIso,
        minDate: minDate || undefined,
        maxDate: maxIso || undefined,
        disableMobile: true,
        onDayCreate: function (dObj, dStr, fp, dayElem) {
          const iso = dayElem.dateObj ? dateToISO(dayElem.dateObj) : null;
          if (iso && plannedByDate[iso] && plannedByDate[iso].length > 0) {
            dayElem.classList.add("has-shift");
          }
        },
        onChange: async function (selectedDates) {
          if (!selectedDates || !selectedDates[0]) return;
          const nextIso = dateToISO(selectedDates[0]);

          if (!isDateInWindow(nextIso)) {
            setModalMsg("Datum valt buiten de periode.", true);
            return;
          }

          // first selection
          if (!modalCurrentIso) {
            modalCurrentIso = nextIso;
            buildDagdeelOptions(nextIso);
            modalSnapshotByIso[nextIso] = buildModalSnapshot();
            modalDirty = false;
            setModalMsg("", false);
            return;
          }

          // same date: nothing
          if (nextIso === modalCurrentIso) return;

          // confirm unsaved changes for current date
          const canLeave = await maybeSaveBeforeLeavingModal("datum wisselen");
          if (!canLeave) {
            // revert selection back
            if (modalFp) modalFp.setDate(modalCurrentIso, false, "Y-m-d");
            return;
          }

          // switch
          modalCurrentIso = nextIso;
          buildDagdeelOptions(nextIso);
          modalSnapshotByIso[nextIso] = buildModalSnapshot();
          modalDirty = false;
          setModalMsg("", false);
        },
      });
    } else {
      // already exists -> just set date
      if (modalFp) modalFp.setDate(initialIso, true, "Y-m-d");
    }

    // ensure day list rendered for current date
    modalCurrentIso = getModalSelectedISO() || initialIso;
    buildDagdeelOptions(modalCurrentIso);
    modalSnapshotByIso[modalCurrentIso] = buildModalSnapshot();
    modalDirty = false;
  }

  async function closeModalWithConfirm() {
    const modal = document.getElementById("addModal");
    if (!modal) return;

    const okToClose = await maybeSaveBeforeLeavingModal("sluiten");
    if (!okToClose) return;

    modal.style.display = "none";
    document.body.style.overflow = "";
    setModalMsg("", false);
  }

  // --------------------------
  // Modal submit button
  // --------------------------
  function setupModalActions() {
    const openBtn = document.getElementById("openAddModalBtn");
    const closeBtn = document.getElementById("closeAddModalBtn");
    const cancelBtn = document.getElementById("modalCancelBtn");
    const addBtn = document.getElementById("modalAddBtn");
    const modal = document.getElementById("addModal");

    if (openBtn) openBtn.addEventListener("click", openModal);

    if (closeBtn) closeBtn.addEventListener("click", closeModalWithConfirm);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModalWithConfirm);

    // click outside content closes too (with confirm)
    if (modal) {
      modal.addEventListener("click", async (e) => {
        if (e.target === modal) {
          await closeModalWithConfirm();
        }
      });
    }

    // ESC to close (with confirm)
    document.addEventListener("keydown", async (e) => {
      if (e.key === "Escape") {
        const m = document.getElementById("addModal");
        if (m && m.style.display === "block") {
          await closeModalWithConfirm();
        }
      }
    });

    if (addBtn) {
      addBtn.addEventListener("click", async () => {
        const iso = modalCurrentIso || getModalSelectedISO();
        if (!iso) { setModalMsg("Kies eerst een datum.", true); return; }
        if (!isDateInWindow(iso)) { setModalMsg("Datum valt buiten de periode.", true); return; }

        setModalMsg("Opslaan...", false);

        try {
          const res = await saveModalForIso(iso);
          if (!res.ok) {
            setModalMsg(res.error || "Opslaan mislukt.", true);
            return;
          }

          // after save, refresh modal baseline/dirty
          modalCurrentIso = iso;
          buildDagdeelOptions(iso);
          modalSnapshotByIso[iso] = buildModalSnapshot();
          modalDirty = false;

          // recalc totals & ensure empty row removed
          recalcTotals();
          ensureEmptyRow();

          setModalMsg("Opgeslagen. Je kunt nog een dienst toevoegen.", false);
        } catch (e) {
          setModalMsg("Netwerkfout.", true);
        }
      });
    }
  }

  // --------------------------
  // Init JSON data
  // --------------------------
  function initData() {
    dagdeelMeta = loadJsonScript("dagdeelMeta") || {};
    plannedByDate = loadJsonScript("plannedByDateJson") || {};
    existingByDate = loadJsonScript("existingByDateJson") || {};
  }

  // --------------------------
  // Init
  // --------------------------
  document.addEventListener("DOMContentLoaded", function () {
    initData();
    setupCountdown();
    setupExistingInputs();
    setupRemoveButtons();
    recalcTotals();
    ensureEmptyRow();

    // autosave baseline snapshot
    lastSnapshot = buildSnapshot();
    setAutosaveStatus("—", null);

    setupModalActions();
  });
})();