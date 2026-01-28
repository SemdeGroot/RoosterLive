(function () {
  const AUTOSAVE_DEBOUNCE_MS = 2000;

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
    if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return null;
    return hh * 60 + mm;
  }

  function format1(n) {
    const x = Math.round(n * 10) / 10;
    return x.toFixed(1).replace(".", ",");
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

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
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

  function dateToISO(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }

  function isoToDMY(iso) {
    const dt = parseISODate(iso);
    if (!dt) return iso;
    return `${pad2(dt.getDate())}-${pad2(dt.getMonth() + 1)}-${dt.getFullYear()}`;
  }

  // --------------------------
  // iMask
  // --------------------------
  function applyTimeMask(input) {
    if (!input || !window.IMask) return;
    window.IMask(input, {
      mask: 'H{:}M',
      blocks: {
        H: { mask: window.IMask.MaskedRange, from: 0, to: 23, maxLength: 2 },
        M: { mask: window.IMask.MaskedRange, from: 0, to: 59, maxLength: 2 }
      }
    });
  }

  function applyBreakMask(input) {
    if (!input || !window.IMask) return;
    window.IMask(input, {
      mask: Number,
      scale: 1,
      signed: false,
      thousandsSeparator: '',
      padFractionalZeros: false,
      normalizeZeros: true,
      radix: ',',
      mapToRadix: ['.'],
      min: 0
    });
  }

  // --------------------------
  // CSRF + fetch
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
  // Countdown
  // --------------------------
  function formatCountdown(ms) {
    if (ms <= 0) return "Deadline verstreken";
    const totalMinutes = Math.floor(ms / 60000);
    const days = Math.floor(totalMinutes / (60 * 24));
    const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
    const minutes = totalMinutes % 60;
    return `${days} dagen ${pad2(hours)}:${pad2(minutes)}`;
  }

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
  // Weighted calculation per day (overlap with dagdelen)
  // --------------------------
  let dagdeelMeta = {};
  function computeDayTotals({ startHHMM, endHHMM, breakHours }) {
    const s0 = timeStrToMinutes(startHHMM);
    const e0 = timeStrToMinutes(endHHMM);
    if (s0 == null || e0 == null) return { total: 0, weighted: 0 };

    let s = s0;
    let e = e0;
    if (e <= s) e += 1440;

    const rawSegments = []; // { mins, allowancePct }
    let totalMins = 0;

    Object.entries(dagdeelMeta).forEach(([id, meta]) => {
      const ds0 = timeStrToMinutes(meta.start);
      const de0 = timeStrToMinutes(meta.end);
      if (ds0 == null || de0 == null) return;

      let ds = ds0;
      let de = de0;
      if (de <= ds) de += 1440;

      let mins = Math.max(0, Math.min(e, de) - Math.max(s, ds));
      mins = Math.max(mins, Math.max(0, Math.min(e, de + 1440) - Math.max(s, ds + 1440)));

      if (mins > 0) {
        rawSegments.push({ mins, allowancePct: Number(meta.allowance_pct || 100) });
        totalMins += mins;
      }
    });

    if (totalMins <= 0) return { total: 0, weighted: 0 };

    const br = Math.max(0, toNumberHours(breakHours));
    const breakMins = Math.round(br * 60);

    if (breakMins >= totalMins) {
      return { total: 0, weighted: 0, error: "Pauze is groter dan of gelijk aan de gewerkte tijd." };
    }

    let remainingBreak = breakMins;
    const adjusted = rawSegments.map((seg, idx) => {
      let red = 0;
      if (breakMins > 0) {
        if (idx === rawSegments.length - 1) {
          red = remainingBreak;
        } else {
          red = Math.round((seg.mins / totalMins) * breakMins);
          red = Math.min(red, seg.mins);
          remainingBreak -= red;
        }
      }
      return { ...seg, mins: Math.max(0, seg.mins - red) };
    });

    const totalAdjMins = adjusted.reduce((a, x) => a + x.mins, 0);
    const totalHours = totalAdjMins / 60;

    const weightedHours = adjusted.reduce((a, x) => {
      const mult = (Number.isFinite(x.allowancePct) ? x.allowancePct : 100) / 100;
      return a + (x.mins / 60) * mult;
    }, 0);

    return { total: totalHours, weighted: weightedHours };
  }

  function recalcTotals() {
    const rows = document.querySelectorAll("tr.uren-row");
    let sumHours = 0;
    let sumWeighted = 0;

    rows.forEach((row) => {
      const start = row.querySelector('input[name="row_start"]')?.value || "";
      const end = row.querySelector('input[name="row_end"]')?.value || "";
      const br = row.querySelector('input[name="row_break"]')?.value || "";

      const res = computeDayTotals({ startHHMM: start, endHHMM: end, breakHours: br });

      const totalEl = row.querySelector(".total-value");
      const weightedEl = row.querySelector(".weighted-value");
      const warnEl = row.querySelector(".hours-warning");

      if (res.error) showHoursWarning(warnEl, res.error);
      else showHoursWarning(warnEl, "");

      if (totalEl) totalEl.textContent = format1(res.total || 0);
      if (weightedEl) weightedEl.textContent = format1(res.weighted || 0);

      sumHours += (res.total || 0);
      sumWeighted += (res.weighted || 0);
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
      tr.innerHTML = `<td colspan="8" class="muted">Nog geen regels. Klik op “Diensten toevoegen”.</td>`;
      tbody.appendChild(tr);
    }
    if (any && empty) empty.remove();
  }

  // --------------------------
  // Autosave
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
      const s = row.querySelector('input[name="row_start"]')?.value?.trim() || "";
      const e = row.querySelector('input[name="row_end"]')?.value?.trim() || "";
      const b = row.querySelector('input[name="row_break"]')?.value?.trim() || "";
      parts.push(`${date}|${s}|${e}|${b}`);
    });

    const km = form.querySelector('input[name="kilometers"]');
    parts.push(`km|${km ? (km.value || "").trim() : ""}`);

    return parts.join(";");
  }

  function buildAutosaveFormData() {
    const form = document.getElementById("urenForm");
    const fd = new FormData();

    fd.append("action", "autosave_day");

    const rowDates = form.querySelectorAll('input[name="row_date"]');
    const rowStarts = form.querySelectorAll('input[name="row_start"]');
    const rowEnds = form.querySelectorAll('input[name="row_end"]');
    const rowBreaks = form.querySelectorAll('input[name="row_break"]');

    const n = Math.min(rowDates.length, rowStarts.length, rowEnds.length, rowBreaks.length);
    for (let i = 0; i < n; i++) {
      fd.append("row_date", rowDates[i].value);
      fd.append("row_start", rowStarts[i].value);
      fd.append("row_end", rowEnds[i].value);
      fd.append("row_break", rowBreaks[i].value);
    }

    const km = form.querySelector('input[name="kilometers"]');
    if (km) fd.append("kilometers", km.value);

    return fd;
  }

  function scheduleAutosave() {
    if (autosaveTimer) clearTimeout(autosaveTimer);

    setAutosaveStatus("Opslaan...", null);

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
  // Bind rows
  // --------------------------
  function bindDayRow(tr) {
    if (!tr) return;

    const startInp = tr.querySelector('input[name="row_start"]');
    const endInp = tr.querySelector('input[name="row_end"]');
    const breakInp = tr.querySelector('input[name="row_break"]');

    if (startInp) applyTimeMask(startInp);
    if (endInp) applyTimeMask(endInp);
    if (breakInp) applyBreakMask(breakInp);

    // normalize existing break dots -> commas
    if (breakInp && breakInp.value && breakInp.value.includes(".")) {
      breakInp.value = breakInp.value.replace(".", ",");
    }

    const onChange = () => {
      recalcTotals();
      scheduleAutosave();
    };

    [startInp, endInp, breakInp].forEach((inp) => {
      if (!inp) return;
      inp.addEventListener("input", onChange);
      inp.addEventListener("blur", onChange);
    });
  }

  function setupExistingInputs() {
    document.querySelectorAll("tr.uren-row").forEach((tr) => bindDayRow(tr));

    const km = document.querySelector('input[name="kilometers"]');
    if (km) {
      km.addEventListener("input", () => scheduleAutosave());
      km.addEventListener("blur", () => scheduleAutosave());
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
  // Modal
  // --------------------------
  let plannedByDate = {};
  let existingByDate = {};
  let modalFp = null;
  let modalCurrentIso = null;

  function setModalMsg(text, isError) {
    const el = document.getElementById("modalMsg");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = isError ? "var(--danger)" : "var(--muted)";
  }

  function fillModalFieldsForIso(iso) {
    const ex = existingByDate[iso] || {};
    const s = document.getElementById("modalStart");
    const e = document.getElementById("modalEnd");
    const b = document.getElementById("modalBreak");
    if (s) s.value = ex.start || "";
    if (e) e.value = ex.end || "";
    if (b) b.value = (ex.break || "0,0").replace(".", ",");
  }

  function getModalSelectedISO() {
    const input = document.getElementById("modalDate");
    const val = input ? (input.value || "").trim() : "";
    const dt = parseISODate(val);
    if (dt) return dateToISO(dt);
    return val && val.length === 10 ? val : null;
  }

  async function saveModalForIso(iso) {
    const start = (document.getElementById("modalStart")?.value || "").trim();
    const end = (document.getElementById("modalEnd")?.value || "").trim();
    const br = (document.getElementById("modalBreak")?.value || "").trim();

    const fd = new FormData();
    fd.append("action", "modal_day_upsert");
    fd.append("date", iso);
    fd.append("start_time", start);
    fd.append("end_time", end);
    fd.append("break_hours", br);

    const resp = await postForm(window.location.href, fd);
    const data = await resp.json().catch(() => null);

    if (!resp.ok || !data || !data.ok) {
      return { ok: false, error: (data && data.error) ? data.error : "Opslaan mislukt." };
    }

    const row = data.row;
    upsertDayRowInTable(row);

    existingByDate[iso] = { start: row.start, end: row.end, break: row.break };

    lastSnapshot = buildSnapshot();
    setAutosaveStatus("Opgeslagen ✅", true);

    return { ok: true, row };
  }

  function upsertDayRowInTable(rowData) {
    const tbody = document.getElementById("urenTbody");
    if (!tbody) return;

    ensureEmptyRow();

    const iso = rowData.date;

    let tr = tbody.querySelector(`tr.uren-row[data-date="${iso}"]`);
    if (tr) {
      tr.querySelector('input[name="row_start"]').value = rowData.start || "";
      tr.querySelector('input[name="row_end"]').value = rowData.end || "";
      tr.querySelector('input[name="row_break"]').value = (rowData.break || "0,0").replace(".", ",");
      bindDayRow(tr);
      recalcTotals();
      scheduleAutosave();
      return;
    }

    tr = document.createElement("tr");
    tr.className = "uren-row";
    tr.setAttribute("data-date", iso);

    tr.innerHTML = `
      <td class="center-col" style="color:var(--muted);">—</td>
      <td><strong>${escapeHtml(rowData.date_label || isoToDMY(iso))}</strong></td>

      <td>
        <input type="hidden" name="row_date" value="${escapeHtml(iso)}">
        <input type="text" name="row_start" value="${escapeHtml(rowData.start || "")}"
               class="admin-input uren-time-input js-time" inputmode="numeric" placeholder="uu:mm" autocomplete="off">
      </td>

      <td>
        <input type="text" name="row_end" value="${escapeHtml(rowData.end || "")}"
               class="admin-input uren-time-input js-time" inputmode="numeric" placeholder="uu:mm" autocomplete="off">
      </td>

      <td>
        <input type="text" name="row_break" value="${escapeHtml((rowData.break || "0,0").replace(".", ","))}"
               class="admin-input uren-break-input js-break" inputmode="decimal" placeholder="0,0" autocomplete="off">
        <div class="hours-warning" style="margin-top:4px; display:none;"></div>
      </td>

      <td class="total-cell"><strong class="total-value">0,0</strong></td>
      <td class="weighted-cell"><strong class="weighted-value">0,0</strong></td>

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

    bindDayRow(tr);

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
    scheduleAutosave();
  }

  function openModal() {
    const modal = document.getElementById("addModal");
    if (!modal) return;

    modal.style.display = "block";
    document.body.style.overflow = "hidden";
    setModalMsg("", false);

    const input = document.getElementById("modalDate");
    if (!input) return;

    applyTimeMask(document.getElementById("modalStart"));
    applyTimeMask(document.getElementById("modalEnd"));
    applyBreakMask(document.getElementById("modalBreak"));

    const bounds = getWindowBounds();
    const minDate = bounds.startIso || null;
    const endIso = bounds.endIso || null;

    const maxDateObj = endIso ? parseISODate(endIso) : null;
    const maxIso = maxDateObj
      ? dateToISO(new Date(maxDateObj.getFullYear(), maxDateObj.getMonth(), maxDateObj.getDate() - 1))
      : null;

    let initialIso = null;
    const existingIso = getModalSelectedISO();
    if (existingIso && isDateInWindow(existingIso)) initialIso = existingIso;
    else if (plannedByDate && Object.keys(plannedByDate).length > 0) initialIso = Object.keys(plannedByDate)[0];
    else if (minDate) initialIso = minDate;
    if (!initialIso) initialIso = dateToISO(new Date());

    if (!modalFp && window.flatpickr) {
      modalFp = window.flatpickr(input, {
        locale: "nl",
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
        onChange: function (selectedDates) {
          if (!selectedDates || !selectedDates[0]) return;
          const nextIso = dateToISO(selectedDates[0]);
          if (!isDateInWindow(nextIso)) {
            setModalMsg("Datum valt buiten de periode.", true);
            return;
          }
          modalCurrentIso = nextIso;
          fillModalFieldsForIso(nextIso);
          setModalMsg("", false);
        },
      });
    } else {
      if (modalFp) modalFp.setDate(initialIso, true, "Y-m-d");
    }

    modalCurrentIso = getModalSelectedISO() || initialIso;
    fillModalFieldsForIso(modalCurrentIso);
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
          setModalMsg("Opgeslagen. Je kunt nog een dienst toevoegen.", false);
          recalcTotals();
          ensureEmptyRow();
        } catch (e) {
          setModalMsg("Netwerkfout.", true);
        }
      });
    }
  }

  // --------------------------
  // Init JSON
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

    lastSnapshot = buildSnapshot();
    setAutosaveStatus("—", null);

    setupModalActions();
  });
})();
