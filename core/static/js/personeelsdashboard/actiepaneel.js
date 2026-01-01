(() => {
  function $(sel, root=document){ return root.querySelector(sel); }
  function $all(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  const PERIODS = ["morning", "afternoon", "evening"];

  function periodLabel(p){
    if (p === "morning") return "Ochtend";
    if (p === "afternoon") return "Middag";
    if (p === "evening") return "Avond";
    return p;
  }

  function keyOf({user_id, date, period}){
    return `${user_id}|${date}|${period}`;
  }

  function parsePdData(){
    const el = document.getElementById("pd-data");
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch(e) { return null; }
  }

  function pop(node){
    if (!node) return;
    node.animate(
      [{ transform: "scale(.98)", opacity: .65 }, { transform: "scale(1)", opacity: 1 }],
      { duration: 220, easing: "cubic-bezier(.2,.8,.2,1)" }
    );
  }

  const DELETE_SVG = `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none"
         stroke="currentColor" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
      <line x1="10" y1="11" x2="10" y2="17"/>
      <line x1="14" y1="11" x2="14" y2="17"/>
    </svg>
  `;

  const pd = parsePdData();
  if (!pd) return;

  const locations = pd.locations || [];
  let existingShifts = pd.existingShifts || [];
  const saveConceptUrl = pd.saveConceptUrl;
  const deleteShiftUrl = pd.deleteShiftUrl;

  // DOM
  const selectionListEl = $("#pdSelectionList");
  const selectionEmptyEl = $("#pdSelectionEmpty");
  const selectionMetaEl = $("#pdSelectionMeta");
  const selectedCountEl = $("#pdSelectedCount");
  const saveBtn = $("#pdSaveConceptBtn");

  const locPillsEl = $("#pdLocationPills");
  const locPanelsEl = $("#pdLocationPanels");

  if (!selectionListEl || !locPillsEl || !locPanelsEl || !saveBtn) return;

  // index tasks by location (for selects)
  const tasksByLocation = new Map();
  locations.forEach(loc => {
    tasksByLocation.set(String(loc.id), (loc.tasks || []).map(t => ({ id: String(t.id), name: t.name })));
  });

  function buildExistingMap(){
    const m = new Map();
    existingShifts.forEach(s => {
      m.set(`${s.user_id}|${s.date}|${s.period}`, s);
    });
    return m;
  }

  function getExistingByKey(k){
    return buildExistingMap().get(k);
  }

  function findRectByKey(k){
    const [user_id, date, period] = k.split("|");
    return document.querySelector(`.avail-rect[data-user-id="${user_id}"][data-date="${date}"][data-period="${period}"]`);
  }

  function markMatrixFromExisting(){
    existingShifts.forEach(s => {
      const sel = `.avail-rect[data-user-id="${s.user_id}"][data-date="${s.date}"][data-period="${s.period}"]`;
      const rect = document.querySelector(sel);
      if (!rect) return;

      rect.dataset.shiftId = String(s.id);
      rect.dataset.shiftStatus = String(s.status || "concept");
      rect.dataset.taskId = String(s.task_id);
      rect.dataset.locationId = String(s.location_id);

      rect.classList.remove("is-accepted", "is-concept");
      const st = String(s.status || "concept");
      rect.classList.add((st === "active" || st === "accepted") ? "is-accepted" : "is-concept");
      rect.classList.add("has-shift");
      rect.tabIndex = 0;
      rect.removeAttribute("aria-disabled");
    });
  }

  function clearMatrixShiftMark(shift){
    const k = `${shift.user_id}|${shift.date}|${shift.period}`;
    const rect = findRectByKey(k);
    if (!rect) return;

    delete rect.dataset.shiftId;
    delete rect.dataset.shiftStatus;
    delete rect.dataset.taskId;
    delete rect.dataset.locationId;

    rect.classList.remove("is-accepted", "is-concept", "has-shift", "is-selected");
  }

  // state
  const state = {
    selected: new Map(),
    assigned: new Map(),
    dirty: new Set(),
    ui: {
      activeLocId: locations.length ? String(locations[0].id) : "",
      activePeriodByLoc: new Map(), // locId -> "morning"/...
    }
  };

  // init periods: default morning open for every loc
  locations.forEach(loc => state.ui.activePeriodByLoc.set(String(loc.id), "morning"));

  function setActiveLocation(locId){
    state.ui.activeLocId = String(locId || "");

    $all('button[data-loc-pill="1"]', locPillsEl).forEach(btn => {
      const isActive = btn.dataset.locId === state.ui.activeLocId;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    $all(".pd-loc-panel", locPanelsEl).forEach(p => {
      p.hidden = p.dataset.locId !== state.ui.activeLocId;
    });

    // ensure period visibility applied for this loc
    applyPeriodVisibility(state.ui.activeLocId);
  }

  function setActivePeriod(locId, period){
    const locIdStr = String(locId || "");
    if (!locIdStr) return;
    if (!PERIODS.includes(period)) return;

    state.ui.activePeriodByLoc.set(locIdStr, period);
    applyPeriodVisibility(locIdStr);
  }

  // used for syncing from left grid sorting:
  function setPeriodForAllLocations(period){
    if (!PERIODS.includes(period)) return;
    locations.forEach(loc => state.ui.activePeriodByLoc.set(String(loc.id), period));
    if (state.ui.activeLocId) applyPeriodVisibility(state.ui.activeLocId);
  }

  /**
   * Niet vertrouwen op `hidden` alleen (kan door CSS overschreven worden),
   * maar expliciet display:none zetten.
   * Daardoor is er per locatie altijd maar 1 dagdeel zichtbaar.
   */
  function applyPeriodVisibility(locId){
    const locIdStr = String(locId || "");
    const activePeriod = state.ui.activePeriodByLoc.get(locIdStr) || "morning";

    const panel = locPanelsEl.querySelector(`.pd-loc-panel[data-loc-id="${locIdStr}"]`);
    if (!panel) return;

    // pills active
    $all(`button[data-period-pill="1"][data-loc-id="${locIdStr}"]`, panel).forEach(btn => {
      const isActive = btn.dataset.period === activePeriod;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    // show only active period panel
    $all(`.pd-period-panel[data-loc-id="${locIdStr}"]`, panel).forEach(sec => {
      const show = sec.dataset.period === activePeriod;

      // hard enforce
      sec.hidden = !show;
      sec.style.display = show ? "" : "none";
    });
  }

  /* -----------------------------
     Status pill
  ------------------------------ */
  function statusPill(kind){
    const label =
      kind === "available" ? "beschikbaar" :
      kind === "active" ? "actief" :
      "concept";

    return `<span class="pd-status-pill pd-status-pill--${kind}">${label}</span>`;
  }

  function deleteButtonHtml(){
    return `
      <button class="icon-btn danger" type="button" data-action="delete" aria-label="Verwijderen">
        ${DELETE_SVG}
      </button>
    `;
  }

  function removeButtonHtml(){
    return `
      <button type="button" class="btn pd-icon-btn" data-action="remove" aria-label="Verwijderen">
        ✕
      </button>
    `;
  }

  /* -----------------------------
     Build Location UI (loc pills + loc panels + period tabs)
  ------------------------------ */
  function buildLocationUI(){
    locPillsEl.innerHTML = "";
    locPanelsEl.innerHTML = "";

    locations.forEach((loc, idx) => {
      const locId = String(loc.id);

      // location pill
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "pd-pill pd-pill-btn";
      pill.dataset.locPill = "1";
      pill.dataset.locId = locId;
      pill.role = "tab";
      pill.setAttribute("aria-selected", idx === 0 ? "true" : "false");
      pill.innerHTML = `
        <span class="pd-pill-label">${loc.name}</span>
        <span class="pd-pill-value" id="pdLocPillCount-${locId}">0/0</span>
      `;
      locPillsEl.appendChild(pill);

      // panel
      const panel = document.createElement("div");
      panel.className = "pd-loc-panel";
      panel.dataset.locId = locId;
      panel.hidden = idx !== 0;

      const periodPills = PERIODS.map(p => `
        <button type="button"
                class="pd-pill pd-pill-btn"
                data-period-pill="1"
                data-loc-id="${locId}"
                data-period="${p}"
                role="tab"
                aria-selected="${p === "morning" ? "true" : "false"}">
          <span class="pd-pill-label">${periodLabel(p)}</span>
          <span class="pd-pill-value" id="pdLocPeriodPill-${locId}-${p}">0/0</span>
        </button>
      `).join("");

      const periodPanels = PERIODS.map(p => {
        const tasksHtml = (loc.tasks || []).map(t => `
          <div class="pd-task-block">
            <div class="pd-task-block-head">
              <div class="pd-task-block-name">${t.name}</div>
              <div class="pd-task-block-count" id="pdTaskCount-${locId}-${t.id}-${p}">0/${(t.min?.[p] ?? 0)}</div>
            </div>
            <div class="pd-task-items" id="pdTaskItems-${locId}-${t.id}-${p}"></div>
          </div>
        `).join("");

        // init: non-morning panels display:none (hard)
        const displayStyle = (p === "morning") ? "" : "display:none;";

        return `
          <section class="pd-period-panel"
                   data-loc-id="${locId}"
                   data-period="${p}"
                   id="pdPeriodPanel-${locId}-${p}"
                   style="${displayStyle}">

            <div class="pd-period-head">
              <div class="pd-period-title">${periodLabel(p)}</div>
              <div class="pd-period-count" id="pdLocPeriodHeader-${locId}-${p}">0/0</div>
            </div>

            <div class="pd-staging" id="pdStaging-${locId}-${p}" style="display:none;">
              <div class="pd-staging-head">
                <div class="pd-staging-title-strong">Nog geen taak gekozen</div>
                <div class="pd-staging-count" id="pdStagingCount-${locId}-${p}">0/0</div>
              </div>
              <div class="pd-task-items" id="pdStagingItems-${locId}-${p}"></div>
            </div>

            ${tasksHtml || `<div class="pd-empty">Geen taken gekoppeld aan deze locatie.</div>`}
          </section>
        `;
      }).join("");

      panel.innerHTML = `
        <div class="pd-loc-top">
          <div class="pd-loc-title">${loc.name}</div>
          <div class="pd-loc-period-pills" role="tablist" aria-label="Dagdelen">
            ${periodPills}
          </div>
        </div>

        ${periodPanels}
      `;

      locPanelsEl.appendChild(panel);
    });

    // bind location pills
    locPillsEl.addEventListener("click", (e) => {
      const btn = e.target.closest('button[data-loc-pill="1"]');
      if (!btn) return;
      setActiveLocation(btn.dataset.locId);
    });

    // bind period pills (per locatie)
    locPanelsEl.addEventListener("click", (e) => {
      const btn = e.target.closest('button[data-period-pill="1"]');
      if (!btn) return;
      setActivePeriod(btn.dataset.locId, btn.dataset.period);
    });

    if (locations.length) setActiveLocation(String(locations[0].id));
  }

  /* -----------------------------
     Selection: matrix click
  ------------------------------ */
  function selectRect(rect){
    const user_id = Number(rect.dataset.userId);
    const group = rect.dataset.group;
    const firstname = rect.dataset.firstname;
    const date = rect.dataset.date;
    const period = rect.dataset.period;

    const k = `${user_id}|${date}|${period}`;
    if (state.selected.has(k)) return;

    const ex = getExistingByKey(k);
    if (ex){
      state.selected.set(k, { user_id, group, firstname, date, period, existing: true, shift_id: ex.id, status: ex.status });
      state.assigned.set(k, { location_id: String(ex.location_id ?? ""), task_id: String(ex.task_id ?? "") });
    } else {
      state.selected.set(k, { user_id, group, firstname, date, period, existing: false });
      state.assigned.set(k, { location_id: "", task_id: "" });
    }

    rect.classList.add("is-selected");
    renderAll();
  }

  function deselectByKey(k){
    state.selected.delete(k);
    state.assigned.delete(k);
    state.dirty.delete(k);

    const rect = findRectByKey(k);
    rect?.classList.remove("is-selected");
    renderAll();
  }

  function toggleRect(rect){
    const k = `${rect.dataset.userId}|${rect.dataset.date}|${rect.dataset.period}`;
    if (state.selected.has(k)) deselectByKey(k);
    else selectRect(rect);
  }

  function bindMatrix(){
    const rects = $all(".avail-rect.available, .avail-rect.has-shift");
    rects.forEach(rect => {
      rect.addEventListener("click", () => toggleRect(rect));
      rect.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleRect(rect);
        }
      });
    });
  }

  /* -----------------------------
     Select builders
  ------------------------------ */
  function buildLocationSelect(current){
    return `
      <select class="admin-select pd-mini-select" data-action="location">
        <option value="">Kies locatie…</option>
        ${locations.map(l => `<option value="${l.id}" ${String(current ?? "")===String(l.id)?"selected":""}>${l.name}</option>`).join("")}
      </select>
    `;
  }

  function buildTaskSelect(locId, currentTaskId){
    const tasks = tasksByLocation.get(String(locId)) || [];
    return `
      <select class="admin-select pd-mini-select" data-action="task" ${locId ? "" : "disabled"}>
        <option value="">Kies taak…</option>
        ${tasks.map(t => `<option value="${t.id}" ${String(currentTaskId ?? "")===String(t.id)?"selected":""}>${t.name}</option>`).join("")}
      </select>
    `;
  }

  /* -----------------------------
     Shift card header
  ------------------------------ */
  function shiftCardHeader(item){
    let kind = "available";
    if (item.existing){
      const st = String(item.status || "concept");
      kind = (st === "active" || st === "accepted") ? "active" : "concept";
    }
    const pill = statusPill(kind);

    const line1 = `${item.firstname} – ${item.group}`;
    const line2 = `${periodLabel(item.period)} – ${item.date}`;

    return `
      <div class="pd-shift-card">
        <div class="pd-shift-top">
          ${pill}
        </div>
        <div class="pd-shift-line1">${line1}</div>
        <div class="pd-shift-line2">${line2}</div>
      </div>
    `;
  }

  function selectionCard(item){
    const k = keyOf(item);
    const a = state.assigned.get(k) || { location_id: "", task_id: "" };

    const card = document.createElement("div");
    card.className = "pd-item pd-item--selection";
    card.dataset.key = k;

    const rightButtons = item.existing
      ? `${deleteButtonHtml()}${removeButtonHtml()}`
      : `${removeButtonHtml()}`;

    card.innerHTML = `
      <div class="pd-item-main">
        ${shiftCardHeader(item)}
      </div>

      <div class="pd-item-actions">
        ${buildLocationSelect(a.location_id)}
        ${buildTaskSelect(a.location_id, a.task_id)}
        ${rightButtons}
      </div>
    `;

    const locSel = card.querySelector('select[data-action="location"]');
    const taskSel = card.querySelector('select[data-action="task"]');

    locSel.addEventListener("change", () => {
      const locId = locSel.value;
      state.assigned.set(k, { location_id: String(locId || ""), task_id: "" });

      if (item.existing) state.dirty.add(k);

      if (locId){
        setActiveLocation(String(locId));
        setActivePeriod(String(locId), item.period); // open dagdeel van die dienst
      }

      renderAll();
      pop(card);
    });

    taskSel.addEventListener("change", () => {
      const taskId = taskSel.value;
      const cur = state.assigned.get(k) || { location_id: "", task_id: "" };
      state.assigned.set(k, { ...cur, task_id: String(taskId || "") });
      state.dirty.add(k);
      renderAll();
      pop(card);
    });

    const delBtn = card.querySelector('[data-action="delete"]');
    if (delBtn){
      delBtn.addEventListener("click", async () => {
        await deleteExistingByKey(k);
      });
    }

    const rmBtn = card.querySelector('[data-action="remove"]');
    if (rmBtn){
      rmBtn.addEventListener("click", () => deselectByKey(k));
    }

    return card;
  }

  function panelShiftCard(shiftLike){
    const isExisting = !!shiftLike.shift_id || !!shiftLike.id;
    const shiftId = shiftLike.shift_id || shiftLike.id || null;

    const user_id = shiftLike.user_id;
    const date = shiftLike.date;
    const period = shiftLike.period;
    const group = shiftLike.group;
    const firstname = shiftLike.firstname;

    const k = `${user_id}|${date}|${period}`;
    const status = shiftLike.status || (isExisting ? "concept" : "");

    const a = {
      location_id: String(shiftLike.location_id ?? ""),
      task_id: String(shiftLike.task_id ?? ""),
    };

    const card = document.createElement("div");
    card.className = `pd-item pd-item--assigned ${isExisting ? "pd-item--existing" : ""}`;
    card.dataset.key = k;

    card.innerHTML = `
      <div class="pd-item-main">
        ${shiftCardHeader({
          existing: isExisting,
          status,
          period,
          date,
          firstname,
          group
        })}
      </div>

      <div class="pd-item-actions">
        ${buildLocationSelect(a.location_id)}
        ${buildTaskSelect(a.location_id, a.task_id)}
        ${isExisting ? deleteButtonHtml() : ""}
      </div>
    `;

    const locSel = card.querySelector('select[data-action="location"]');
    const taskSel = card.querySelector('select[data-action="task"]');

    locSel.addEventListener("change", () => {
      const locId = String(locSel.value || "");

      if (isExisting){
        if (!state.selected.has(k)){
          state.selected.set(k, { user_id, group, firstname, date, period, existing: true, shift_id: shiftId, status });
        }
        state.assigned.set(k, { location_id: locId, task_id: "" });
        state.dirty.add(k);
      } else {
        state.assigned.set(k, { location_id: locId, task_id: "" });
        state.dirty.add(k);
      }

      if (locId){
        setActiveLocation(locId);
        setActivePeriod(locId, period);
      }

      renderAll();
      pop(card);
    });

    taskSel.addEventListener("change", () => {
      const locId = String(locSel.value || "");
      const taskId = String(taskSel.value || "");

      if (isExisting){
        if (!state.selected.has(k)){
          state.selected.set(k, { user_id, group, firstname, date, period, existing: true, shift_id: shiftId, status });
        }
        state.assigned.set(k, { location_id: locId, task_id: taskId });
        state.dirty.add(k);
      } else {
        state.assigned.set(k, { location_id: locId, task_id: taskId });
        state.dirty.add(k);
      }

      renderAll();
      pop(card);
    });

    const delBtn = card.querySelector('[data-action="delete"]');
    if (delBtn && isExisting){
      delBtn.addEventListener("click", async () => {
        await deleteShiftById(shiftId);
      });
    }

    return card;
  }

  /* -----------------------------
     Delete helpers
  ------------------------------ */
  async function deleteShiftById(shiftId){
    if (!shiftId) return;

    const ok = confirm("Weet je zeker dat je deze dienst wilt verwijderen?");
    if (!ok) return;

    try{
      const res = await fetch(deleteShiftUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken") || "",
        },
        body: JSON.stringify({ shift_id: Number(shiftId) }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Verwijderen mislukt.");

      const removed = existingShifts.find(s => s.id === Number(shiftId));
      existingShifts = existingShifts.filter(s => s.id !== Number(shiftId));

      if (removed){
        const k = `${removed.user_id}|${removed.date}|${removed.period}`;
        state.selected.delete(k);
        state.assigned.delete(k);
        state.dirty.delete(k);
        clearMatrixShiftMark(removed);
      }

      renderAll();
      markMatrixFromExisting();
    } catch(err){
      alert(err.message || "Verwijderen mislukt.");
    }
  }

  async function deleteExistingByKey(k){
    const ex = getExistingByKey(k);
    if (!ex) return;
    await deleteShiftById(ex.id);
  }

  /* -----------------------------
     Render: selection list
  ------------------------------ */
  function renderSelection(){
    selectionListEl.innerHTML = "";

    const items = Array.from(state.selected.values());
    items.sort((a,b) => {
      if (!!b.existing !== !!a.existing) return (b.existing ? 1 : 0) - (a.existing ? 1 : 0);
      const ag = (a.group||"").toLowerCase();
      const bg = (b.group||"").toLowerCase();
      if (ag !== bg) return ag.localeCompare(bg);
      const af = (a.firstname||"").toLowerCase();
      const bf = (b.firstname||"").toLowerCase();
      return af.localeCompare(bf);
    });

    if (!items.length){
      selectionListEl.appendChild(selectionEmptyEl);
      selectionEmptyEl.style.display = "";
      selectionMetaEl.textContent = "0";
      return;
    }

    selectionEmptyEl.style.display = "none";
    items.forEach(it => selectionListEl.appendChild(selectionCard(it)));
    selectionMetaEl.textContent = String(items.length);
  }

  function clearAllPanelContainers(){
    locations.forEach(loc => {
      PERIODS.forEach(p => {
        const stagingItems = document.getElementById(`pdStagingItems-${loc.id}-${p}`);
        if (stagingItems) stagingItems.innerHTML = "";
      });
      (loc.tasks || []).forEach(t => {
        PERIODS.forEach(p => {
          const el = document.getElementById(`pdTaskItems-${loc.id}-${t.id}-${p}`);
          if (el) el.innerHTML = "";
        });
      });
    });
  }

  function renderPanels(){
    clearAllPanelContainers();

    // 1) existing shifts
    existingShifts.forEach(s => {
      const locId = String(s.location_id ?? "");
      const taskId = String(s.task_id ?? "");
      const per = String(s.period);

      if (!locId || !PERIODS.includes(per)) return;

      if (taskId){
        const container = document.getElementById(`pdTaskItems-${locId}-${taskId}-${per}`);
        container?.appendChild(panelShiftCard({
          id: s.id,
          user_id: s.user_id,
          group: s.group,
          firstname: s.firstname,
          date: s.date,
          period: s.period,
          status: s.status,
          location_id: s.location_id,
          task_id: s.task_id,
        }));
      } else {
        const staging = document.getElementById(`pdStagingItems-${locId}-${per}`);
        staging?.appendChild(panelShiftCard({
          id: s.id,
          user_id: s.user_id,
          group: s.group,
          firstname: s.firstname,
          date: s.date,
          period: s.period,
          status: s.status,
          location_id: s.location_id,
          task_id: null,
        }));
      }
    });

    // 2) previews (new + dirty existing)
    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      const locId = String(a.location_id);
      const per = String(it.period);
      if (!PERIODS.includes(per)) continue;

      if (it.existing && !state.dirty.has(k)) continue;

      const taskId = String(a.task_id || "");

      if (!taskId){
        const staging = document.getElementById(`pdStagingItems-${locId}-${per}`);
        staging?.appendChild(panelShiftCard({
          user_id: it.user_id,
          group: it.group,
          firstname: it.firstname,
          date: it.date,
          period: it.period,
          status: it.existing ? it.status : "",
          location_id: Number(locId),
          task_id: null,
          shift_id: it.shift_id || null,
        }));
      } else {
        const container = document.getElementById(`pdTaskItems-${locId}-${taskId}-${per}`);
        container?.appendChild(panelShiftCard({
          user_id: it.user_id,
          group: it.group,
          firstname: it.firstname,
          date: it.date,
          period: it.period,
          status: it.existing ? it.status : "",
          location_id: Number(locId),
          task_id: Number(taskId),
          shift_id: it.shift_id || null,
        }));
      }
    }

    // 3) staging visible only if it has items
    locations.forEach(loc => {
      PERIODS.forEach(p => {
        const wrap = document.getElementById(`pdStaging-${loc.id}-${p}`);
        const items = document.getElementById(`pdStagingItems-${loc.id}-${p}`);
        if (!wrap || !items) return;
        wrap.style.display = items.children.length ? "" : "none";
      });
    });

    // keep period visibility correct
    if (state.ui.activeLocId) applyPeriodVisibility(state.ui.activeLocId);
  }

  /* -----------------------------
     Counts + save enable (ongewijzigd)
  ------------------------------ */
  function renderCounts(){
    const overrideByKey = new Map();
    for (const it of state.selected.values()){
      const k = keyOf(it);
      if (!it.existing) continue;
      if (!state.dirty.has(k)) continue;

      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      overrideByKey.set(k, {
        location_id: String(a.location_id),
        task_id: String(a.task_id || ""),
      });
    }

    const locPeriodCounts = new Map();
    const taskPeriodCounts = new Map();

    locations.forEach(loc => {
      locPeriodCounts.set(String(loc.id), { morning:0, afternoon:0, evening:0 });
      (loc.tasks || []).forEach(t => {
        taskPeriodCounts.set(`${loc.id}|${t.id}`, { morning:0, afternoon:0, evening:0 });
      });
    });

    function bumpLoc(locId, period){
      if (!locId || !PERIODS.includes(period)) return;
      const lp = locPeriodCounts.get(String(locId));
      if (lp) lp[period] += 1;
    }

    function bumpTask(locId, taskId, period){
      if (!locId || !taskId || !PERIODS.includes(period)) return;
      const tp = taskPeriodCounts.get(`${locId}|${taskId}`);
      if (tp) tp[period] += 1;
    }

    existingShifts.forEach(s => {
      const k = `${s.user_id}|${s.date}|${s.period}`;
      if (overrideByKey.has(k)) return;

      const locId = String(s.location_id ?? "");
      const taskId = String(s.task_id ?? "");
      const per = String(s.period);

      bumpLoc(locId, per);
      if (taskId) bumpTask(locId, taskId, per);
    });

    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      if (it.existing && !state.dirty.has(k)) continue;

      const locId = String(a.location_id);
      const taskId = String(a.task_id || "");
      const per = String(it.period);

      bumpLoc(locId, per);
      if (taskId) bumpTask(locId, taskId, per);
    }

    function locMinTotal(locId){
      const loc = locations.find(x => String(x.id)===String(locId));
      const m = loc?.min || {};
      return (m.morning ?? 0) + (m.afternoon ?? 0) + (m.evening ?? 0);
    }
    function locMinPeriod(locId, p){
      const loc = locations.find(x => String(x.id)===String(locId));
      return (loc?.min?.[p] ?? 0);
    }
    function taskMinPeriod(locId, taskId, p){
      const loc = locations.find(x => String(x.id)===String(locId));
      const t = (loc?.tasks || []).find(tt => String(tt.id)===String(taskId));
      return (t?.min?.[p] ?? 0);
    }

    locations.forEach(loc => {
      const locId = String(loc.id);
      const lp = locPeriodCounts.get(locId) || {morning:0,afternoon:0,evening:0};
      const x = (lp.morning||0) + (lp.afternoon||0) + (lp.evening||0);
      const y = locMinTotal(locId);

      const el = document.getElementById(`pdLocPillCount-${locId}`);
      if (el) el.textContent = `${x}/${y}`;

      PERIODS.forEach(p => {
        const xp = lp[p] ?? 0;
        const yp = locMinPeriod(locId, p);

        const pillEl = document.getElementById(`pdLocPeriodPill-${locId}-${p}`);
        if (pillEl) pillEl.textContent = `${xp}/${yp}`;

        const headEl = document.getElementById(`pdLocPeriodHeader-${locId}-${p}`);
        if (headEl) headEl.textContent = `${xp}/${yp}`;

        const stEl = document.getElementById(`pdStagingCount-${locId}-${p}`);
        if (stEl) stEl.textContent = `${xp}/${yp}`;
      });

      (loc.tasks || []).forEach(t => {
        const tid = String(t.id);
        const tp = taskPeriodCounts.get(`${locId}|${tid}`) || {morning:0,afternoon:0,evening:0};

        PERIODS.forEach(p => {
          const xp = tp[p] ?? 0;
          const yp = taskMinPeriod(locId, tid, p);
          const tEl = document.getElementById(`pdTaskCount-${locId}-${tid}-${p}`);
          if (tEl) tEl.textContent = `${xp}/${yp}`;
        });
      });
    });
  }

  function computeReadyToSaveCount(){
    let n = 0;
    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id || !a.task_id) continue;

      if (!it.existing) { n += 1; continue; }
      if (state.dirty.has(k)) n += 1;
    }
    return n;
  }

  function ensureSaveEnabled(){
    selectedCountEl.textContent = String(state.selected.size);
    saveBtn.disabled = !(computeReadyToSaveCount() > 0);
  }

  function renderAll(){
    renderSelection();
    renderPanels();
    renderCounts();
    ensureSaveEnabled();
  }

  /* -----------------------------
     Save concept (ongewijzigd)
  ------------------------------ */
  async function saveConcept(){
    const items = [];

    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id || !a.task_id) continue;

      if (!it.existing){
        items.push({ user_id: it.user_id, date: it.date, period: it.period, task_id: Number(a.task_id) });
        continue;
      }
      if (state.dirty.has(k)){
        items.push({ user_id: it.user_id, date: it.date, period: it.period, task_id: Number(a.task_id) });
      }
    }

    if (!items.length) return;

    saveBtn.disabled = true;
    const oldText = saveBtn.textContent;
    saveBtn.textContent = "Opslaan…";

    try{
      const res = await fetch(saveConceptUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken") || "",
        },
        body: JSON.stringify({ items }),
      });

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Opslaan mislukt.");

      (data.saved || []).forEach(s => {
        const k = `${s.user_id}|${s.date}|${s.period}`;
        const idx = existingShifts.findIndex(x => `${x.user_id}|${x.date}|${x.period}` === k);

        const rect = findRectByKey(k);
        const group = rect?.dataset.group || state.selected.get(k)?.group || "—";
        const firstname = rect?.dataset.firstname || state.selected.get(k)?.firstname || "—";

        const merged = {
          id: s.shift_id,
          user_id: s.user_id,
          group,
          firstname,
          date: s.date,
          period: s.period,
          status: s.status || "concept",
          task_id: s.task_id,
          task_name: s.task_name,
          location_id: s.location_id,
          location_name: s.location_name,
        };

        if (idx >= 0) existingShifts[idx] = merged;
        else existingShifts.push(merged);

        if (rect){
          rect.dataset.shiftId = String(merged.id);
          rect.dataset.shiftStatus = String(merged.status);
          rect.dataset.taskId = String(merged.task_id);
          rect.dataset.locationId = String(merged.location_id);

          rect.classList.remove("is-accepted", "is-concept");
          const st = String(merged.status || "concept");
          rect.classList.add((st === "active" || st === "accepted") ? "is-accepted" : "is-concept");
          rect.classList.add("has-shift");
          rect.classList.remove("is-selected");
        }

        state.selected.delete(k);
        state.assigned.delete(k);
        state.dirty.delete(k);
      });

      markMatrixFromExisting();
      renderAll();
    } catch(err){
      alert(err.message || "Opslaan mislukt.");
    } finally {
      saveBtn.textContent = oldText;
      ensureSaveEnabled();
    }
  }

  saveBtn.addEventListener("click", (e) => {
    e.preventDefault();
    saveConcept();
  });
    // -----------------------------
  // Publish week (save selection + publish concept->accepted)
  // -----------------------------
  function buildItemsForPublish(){
    const items = [];

    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id || !a.task_id) continue; // alleen complete items

      if (!it.existing){
        items.push({ user_id: it.user_id, date: it.date, period: it.period, task_id: Number(a.task_id) });
        continue;
      }
      if (state.dirty.has(k)){
        items.push({ user_id: it.user_id, date: it.date, period: it.period, task_id: Number(a.task_id) });
      }
    }

    return items;
  }

  const publishBtn = $("#pdPublishWeekBtn");
  if (publishBtn) {
    publishBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      if (!pd?.publishUrl) return;

    const msg =
      "Weet je zeker dat je wilt publiceren?\n\n" +
      "Na publiceren krijgen medewerkers een melding en worden de diensten zichtbaar in de Jansen app en de gesynchroniseerde agenda app.\n" +
      "Publiceer bij voorkeur pas als je het rooster voor deze week volledig hebt ingepland en als concept hebt opgeslagen.\n\n" +
      "Dit publiceert alle conceptdiensten van deze week (en slaat je huidige selectie eerst op als je dit nog niet hebt gedaan).";

      const ok = confirm(msg);
      if (!ok) return;

      publishBtn.disabled = true;
      const oldText = publishBtn.textContent;
      publishBtn.textContent = "Publiceren…";

      try {
        const res = await fetch(pd.publishUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken") || "",
          },
          body: JSON.stringify({
            week_start: pd.weekStart,
            week_end: pd.weekEnd,
            items: buildItemsForPublish(),
          }),
        });

        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "Publiceren mislukt.");

        window.location.reload(); // Django message zichtbaar + alles vers
      } catch (err) {
        alert(err.message || "Publiceren mislukt.");
      } finally {
        publishBtn.textContent = oldText;
        publishBtn.disabled = false;
      }
    });
  }

  /* -----------------------------
     Sync: left grid sorting -> open same period in action panel
  ------------------------------ */
  window.addEventListener("pd:periodChange", (e) => {
    const p = e?.detail?.period;
    if (!p || !PERIODS.includes(p)) return;
    setPeriodForAllLocations(p);
  });

  /* -----------------------------
     Init
  ------------------------------ */
  buildLocationUI();
  markMatrixFromExisting();
  bindMatrix();
  renderAll();
})();