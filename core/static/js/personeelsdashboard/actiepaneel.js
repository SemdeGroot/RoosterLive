(() => {
  function $(sel, root=document){ return root.querySelector(sel); }
  function $all(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

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

  const selectedDate = pd.selectedDate;
  const locations = pd.locations || [];
  let existingShifts = pd.existingShifts || [];
  const saveConceptUrl = pd.saveConceptUrl;
  const deleteShiftUrl = pd.deleteShiftUrl;

  // DOM
  const selectionListEl = $("#pdSelectionList");
  const selectionEmptyEl = $("#pdSelectionEmpty");
  const selectionMetaEl = $("#pdSelectionMeta");
  const tabsEl = $("#pdLocationTabs");
  const panelsEl = $("#pdLocationPanels");

  const selectedCountEl = $("#pdSelectedCount");
  const readyCountEl = $("#pdReadyCount");
  const saveBtn = $("#pdSaveConceptBtn");

  if (!selectionListEl || !tabsEl || !panelsEl || !saveBtn) return;

  // index tasks
  const tasksByLocation = new Map();
  locations.forEach(loc => {
    tasksByLocation.set(String(loc.id), (loc.tasks || []).map(t => ({ id: String(t.id), name: t.name })));
  });

  // existing shift map by key (for quick compare + selection prefill)
  function buildExistingMap(){
    const m = new Map();
    existingShifts.forEach(s => {
      m.set(`${s.user_id}|${s.date}|${s.period}`, s);
    });
    return m;
  }

  // state
  const state = {
    selected: new Map(), // key -> item {user_id, group, firstname, date, period, existing, shift_id, status}
    assigned: new Map(), // key -> { location_id, task_id }
    dirty: new Set(),    // key -> existing item changed OR new item configured
  };

  function isExistingKey(k){
    return buildExistingMap().has(k);
  }

  function getExistingByKey(k){
    return buildExistingMap().get(k);
  }

  function findRectByKey(k){
    const [user_id, date, period] = k.split("|");
    return document.querySelector(`.avail-rect[data-user-id="${user_id}"][data-date="${date}"][data-period="${period}"]`);
  }

  function markMatrixFromExisting(){
    // mark rects green, but keep clickable
    existingShifts.forEach(s => {
      const sel = `.avail-rect[data-user-id="${s.user_id}"][data-date="${s.date}"][data-period="${s.period}"]`;
      const rect = document.querySelector(sel);
      if (!rect) return;

      rect.dataset.shiftId = String(s.id);
      rect.dataset.shiftStatus = String(s.status || "concept");
      rect.dataset.taskId = String(s.task_id);
      rect.dataset.locationId = String(s.location_id);

      rect.classList.remove("is-accepted", "is-concept");
      rect.classList.add(s.status === "accepted" ? "is-accepted" : "is-concept");
      rect.classList.add("has-shift");
      rect.tabIndex = 0; // allow selection
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
    // if availability exists, it stays orange via .available class
  }

  /* -----------------------------
     Tabs/panels build
  ------------------------------ */
  function buildTabs(){
    tabsEl.innerHTML = "";
    panelsEl.innerHTML = "";

    locations.forEach((loc, idx) => {
      const locId = String(loc.id);

      const tab = document.createElement("button");
      tab.className = "pd-tab";
      tab.type = "button";
      tab.role = "tab";
      tab.id = `pd-tab-${locId}`;
      tab.setAttribute("aria-controls", `pd-panel-${locId}`);
      tab.setAttribute("aria-selected", idx === 0 ? "true" : "false");
      tab.dataset.locId = locId;
      tab.innerHTML = `
        <span class="pd-tab-name">${loc.name}</span>
        <span class="pd-tab-count" id="pdLocCount-${locId}">0</span>
      `;
      tabsEl.appendChild(tab);

      const panel = document.createElement("div");
      panel.className = "pd-panel";
      panel.role = "tabpanel";
      panel.id = `pd-panel-${locId}`;
      panel.setAttribute("aria-labelledby", `pd-tab-${locId}`);
      panel.hidden = idx !== 0;
      panel.dataset.locId = locId;

      const tasksHtml = (loc.tasks || []).map(t => `
        <div class="pd-task-row" data-task-id="${t.id}">
          <div class="pd-task-head">
            <div class="pd-task-name">${t.name}</div>
            <div class="pd-task-count" id="pdTaskCount-${locId}-${t.id}">0</div>
          </div>
          <div class="pd-task-items" id="pdTaskItems-${locId}-${t.id}"></div>
        </div>
      `).join("");

      panel.innerHTML = `
        <div class="pd-staging" id="pdStaging-${locId}">
          <div class="pd-staging-title">Nog geen taak gekozen</div>
          <div class="pd-task-items" id="pdStagingItems-${locId}"></div>
        </div>

        <div class="pd-task-grid">
          ${tasksHtml || `<div class="pd-empty">Geen taken gekoppeld aan deze locatie.</div>`}
        </div>
      `;
      panelsEl.appendChild(panel);
    });

    tabsEl.addEventListener("click", (e) => {
      const btn = e.target.closest(".pd-tab");
      if (!btn) return;
      setActiveTab(btn.dataset.locId);
    });
  }

  function setActiveTab(locId){
    $all(".pd-tab", tabsEl).forEach(t => {
      const active = t.dataset.locId === locId;
      t.classList.toggle("is-active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    });
    $all(".pd-panel", panelsEl).forEach(p => {
      p.hidden = p.dataset.locId !== locId;
    });
  }

  /* -----------------------------
     Selection: matrix click -> select/deselect
  ------------------------------ */
  function selectRect(rect){
    const user_id = Number(rect.dataset.userId);
    const group = rect.dataset.group;
    const firstname = rect.dataset.firstname;
    const date = rect.dataset.date;
    const period = rect.dataset.period;

    const k = `${user_id}|${date}|${period}`;
    if (state.selected.has(k)) return;

    // existing?
    const ex = getExistingByKey(k);
    if (ex){
      state.selected.set(k, {
        user_id, group, firstname, date, period,
        existing: true,
        shift_id: ex.id,
        status: ex.status,
      });
      state.assigned.set(k, {
        location_id: String(ex.location_id),
        task_id: String(ex.task_id),
      });
      // not dirty yet
    } else {
      state.selected.set(k, {
        user_id, group, firstname, date, period,
        existing: false,
      });
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
    // bind both available AND existing shift blocks
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
     UI builders
  ------------------------------ */
  function buildLocationSelect(current){
    return `
      <select class="admin-select pd-mini-select" data-action="location">
        <option value="">Kies locatie…</option>
        ${locations.map(l => `<option value="${l.id}" ${String(current||"")===String(l.id)?"selected":""}>${l.name}</option>`).join("")}
      </select>
    `;
  }

  function buildTaskSelect(locId, currentTaskId){
    const tasks = tasksByLocation.get(String(locId)) || [];
    return `
      <select class="admin-select pd-mini-select" data-action="task" ${locId ? "" : "disabled"}>
        <option value="">Kies taak…</option>
        ${tasks.map(t => `<option value="${t.id}" ${String(currentTaskId||"")===String(t.id)?"selected":""}>${t.name}</option>`).join("")}
      </select>
    `;
  }

  function statusChip(status){
    if (!status) return "";
    return `<span class="pd-chip pd-chip--status pd-chip--${status}">${status}</span>`;
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

  function selectionCard(item){
    const k = keyOf(item);
    const a = state.assigned.get(k) || { location_id: "", task_id: "" };

    const card = document.createElement("div");
    card.className = "pd-item pd-item--selection";
    card.dataset.key = k;

    const rightButtons = item.existing ? deleteButtonHtml() : removeButtonHtml();

    card.innerHTML = `
      <div class="pd-item-main">
        <div class="pd-item-title">
          ${item.existing ? statusChip(item.status) : ""}
          <strong>${item.group}</strong> · ${item.firstname}
          <span class="pd-chip">${periodLabel(item.period)}</span>
        </div>
        <div class="pd-item-sub">${item.date}</div>
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
      const cur = state.assigned.get(k) || { location_id: "", task_id: "" };

      state.assigned.set(k, { location_id: String(locId || ""), task_id: "" });
      // if existing, mark dirty
      state.dirty.add(k);

      // re-render + switch tab + animate
      if (locId) setActiveTab(String(locId));
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
    // shiftLike can be existing shift OR "preview" item (selected + task)
    // Normalize:
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
      location_id: String(shiftLike.location_id || ""),
      task_id: String(shiftLike.task_id || ""),
    };

    const card = document.createElement("div");
    card.className = `pd-item pd-item--assigned ${isExisting ? "pd-item--existing" : ""}`;
    card.dataset.key = k;

    card.innerHTML = `
      <div class="pd-item-main">
        <div class="pd-item-title">
          ${status ? statusChip(status) : ""}
          <strong>${group}</strong> · ${firstname}
          <span class="pd-chip">${periodLabel(period)}</span>
        </div>
        <div class="pd-item-sub">${date}</div>
      </div>

      <div class="pd-item-actions">
        ${buildLocationSelect(a.location_id)}
        ${buildTaskSelect(a.location_id, a.task_id)}
        ${isExisting ? deleteButtonHtml() : ""}
      </div>
    `;

    const locSel = card.querySelector('select[data-action="location"]');
    const taskSel = card.querySelector('select[data-action="task"]');

    // allow changing existing directly in panel:
    locSel.addEventListener("change", () => {
      const locId = locSel.value;
      if (!locId) return;
      // update local existingShifts object if this is an existing shift
      if (isExisting){
        const idx = existingShifts.findIndex(s => s.id === shiftId);
        if (idx >= 0){
          existingShifts[idx].location_id = Number(locId);
          existingShifts[idx].location_name = locations.find(l => String(l.id)===String(locId))?.name || "";
          existingShifts[idx].task_id = null; // task must be reselected
          existingShifts[idx].task_name = "";
          // we do NOT change status here; that happens on save
        }
        // mark dirty by selecting it (so it appears above for save), but keep non-intrusive:
        if (!state.selected.has(k)){
          // create selection silently
          state.selected.set(k, {
            user_id, group, firstname, date, period,
            existing: true,
            shift_id: shiftId,
            status: status,
          });
        }
        state.assigned.set(k, { location_id: String(locId), task_id: "" });
        state.dirty.add(k);
      } else {
        // preview item: reflect into state
        state.assigned.set(k, { location_id: String(locId), task_id: "" });
        state.dirty.add(k);
      }

      setActiveTab(String(locId));
      renderAll();
      pop(card);
    });

    taskSel.addEventListener("change", () => {
      const taskId = taskSel.value;
      const locId = locSel.value;

      if (!locId) return;

      if (isExisting){
        const idx = existingShifts.findIndex(s => s.id === shiftId);
        if (idx >= 0){
          const tname = (tasksByLocation.get(String(locId)) || []).find(t => String(t.id)===String(taskId))?.name || "";
          existingShifts[idx].task_id = Number(taskId);
          existingShifts[idx].task_name = tname;
          existingShifts[idx].location_id = Number(locId);
          existingShifts[idx].location_name = locations.find(l => String(l.id)===String(locId))?.name || existingShifts[idx].location_name;
        }
        if (!state.selected.has(k)){
          state.selected.set(k, {
            user_id, group, firstname, date, period,
            existing: true,
            shift_id: shiftId,
            status: status,
          });
        }
        state.assigned.set(k, { location_id: String(locId), task_id: String(taskId || "") });
        state.dirty.add(k);
      } else {
        state.assigned.set(k, { location_id: String(locId), task_id: String(taskId || "") });
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

      // remove from existingShifts
      const removed = existingShifts.find(s => s.id === Number(shiftId));
      existingShifts = existingShifts.filter(s => s.id !== Number(shiftId));

      // also clear from selection if selected
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
     Render: selection list + panels + counts + save enabled
  ------------------------------ */
  function renderSelection(){
    selectionListEl.innerHTML = "";

    const items = Array.from(state.selected.values());
    items.sort((a,b) => {
      // existing first
      if (!!b.existing !== !!a.existing) return (b.existing ? 1 : 0) - (a.existing ? 1 : 0);
      // then group/name
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
      const staging = document.getElementById(`pdStagingItems-${loc.id}`);
      if (staging) staging.innerHTML = "";
      (loc.tasks || []).forEach(t => {
        const el = document.getElementById(`pdTaskItems-${loc.id}-${t.id}`);
        if (el) el.innerHTML = "";
      });
    });
  }

  function renderPanels(){
    clearAllPanelContainers();

    const existingMap = buildExistingMap();

    // 1) Render existing shifts directly under their tasks
    existingShifts.forEach(s => {
      const locId = String(s.location_id);
      const taskId = String(s.task_id);

      const container = document.getElementById(`pdTaskItems-${locId}-${taskId}`);
      if (container){
        container.appendChild(panelShiftCard({
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
        // fallback -> staging
        const staging = document.getElementById(`pdStagingItems-${locId}`);
        if (staging){
          staging.appendChild(panelShiftCard({
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
        }
      }
    });

    // 2) Render previews (selected items with location but no task -> staging; with task -> task container)
    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      // don't duplicate existing if not changed? we still want preview only if it's a NEW selection
      // For existing: only show preview if dirty (so user sees new placement)
      if (it.existing && !state.dirty.has(k)) continue;

      const locId = String(a.location_id);
      const taskId = String(a.task_id || "");

      if (!taskId){
        const staging = document.getElementById(`pdStagingItems-${locId}`);
        if (staging){
          staging.appendChild(panelShiftCard({
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
        }
        continue;
      }

      const container = document.getElementById(`pdTaskItems-${locId}-${taskId}`);
      if (container){
        container.appendChild(panelShiftCard({
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

    // hide staging blocks if empty
    locations.forEach(loc => {
      const stagingWrap = document.getElementById(`pdStaging-${loc.id}`);
      const stagingItems = document.getElementById(`pdStagingItems-${loc.id}`);
      if (stagingWrap && stagingItems){
        stagingWrap.style.display = stagingItems.children.length ? "" : "none";
      }
    });
  }

  function renderCounts(){
    // Location counts must count how many concept are opgeslagen (plus previews that will save as concept)
    const existingConceptByLoc = new Map();
    locations.forEach(l => existingConceptByLoc.set(String(l.id), 0));

    existingShifts.forEach(s => {
      if ((s.status || "concept") === "concept"){
        const locId = String(s.location_id);
        existingConceptByLoc.set(locId, (existingConceptByLoc.get(locId) || 0) + 1);
      }
    });

    // add previews that are "ready" (they will save as concept)
    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id || !a.task_id) continue;

      // new selections always count; existing only if dirty
      if (it.existing && !state.dirty.has(k)) continue;

      const locId = String(a.location_id);
      existingConceptByLoc.set(locId, (existingConceptByLoc.get(locId) || 0) + 1);
    }

    // write tab counts
    locations.forEach(loc => {
      const locId = String(loc.id);
      const el = document.getElementById(`pdLocCount-${locId}`);
      if (el) el.textContent = String(existingConceptByLoc.get(locId) || 0);

      (loc.tasks || []).forEach(t => {
        const tid = String(t.id);

        // task counts: existing concept in that task + previews
        let taskCount = 0;
        existingShifts.forEach(s => {
          if ((s.status || "concept") === "concept"
              && String(s.location_id) === locId
              && String(s.task_id) === tid){
            taskCount += 1;
          }
        });

        for (const it of state.selected.values()){
          const k = keyOf(it);
          const a = state.assigned.get(k);
          if (!a || !a.location_id || !a.task_id) continue;
          if (String(a.location_id) !== locId) continue;
          if (String(a.task_id) !== tid) continue;
          if (it.existing && !state.dirty.has(k)) continue;
          taskCount += 1;
        }

        const tcEl = document.getElementById(`pdTaskCount-${locId}-${tid}`);
        if (tcEl) tcEl.textContent = String(taskCount);
      });
    });
  }

  function computeReadyToSaveCount(){
    // ready to save: selection items that have task chosen AND:
    // - new item, OR existing item that is dirty
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
    const selectedCount = state.selected.size;
    const readyCount = computeReadyToSaveCount();

    selectedCountEl.textContent = String(selectedCount);
    readyCountEl.textContent = String(readyCount);

    // enabled only if there is something to save
    saveBtn.disabled = !(readyCount > 0);
  }

  function renderAll(){
    renderSelection();
    renderPanels();
    renderCounts();
    ensureSaveEnabled();
  }

  /* -----------------------------
     Save concept (API)
  ------------------------------ */
  async function saveConcept(){
    const items = [];

    for (const it of state.selected.values()){
      const k = keyOf(it);
      const a = state.assigned.get(k);
      if (!a || !a.location_id || !a.task_id) continue;

      // new always
      if (!it.existing){
        items.push({
          user_id: it.user_id,
          date: it.date,
          period: it.period,
          task_id: Number(a.task_id),
        });
        continue;
      }

      // existing only if dirty
      if (state.dirty.has(k)){
        items.push({
          user_id: it.user_id,
          date: it.date,
          period: it.period,
          task_id: Number(a.task_id),
        });
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

      // Update existingShifts with returned full details
      (data.saved || []).forEach(s => {
        // merge into existingShifts (by key)
        const k = `${s.user_id}|${s.date}|${s.period}`;
        const idx = existingShifts.findIndex(x => `${x.user_id}|${x.date}|${x.period}` === k);

        // need names for group/firstname - get from selection or rect dataset
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

        // Update matrix styling
        if (rect){
          rect.dataset.shiftId = String(merged.id);
          rect.dataset.shiftStatus = String(merged.status);
          rect.dataset.taskId = String(merged.task_id);
          rect.dataset.locationId = String(merged.location_id);

          rect.classList.remove("is-accepted", "is-concept");
          rect.classList.add(merged.status === "accepted" ? "is-accepted" : "is-concept");
          rect.classList.add("has-shift");
          rect.classList.remove("is-selected");
        }

        // after saving, clear selection & dirty for this key
        state.selected.delete(k);
        state.assigned.delete(k);
        state.dirty.delete(k);
      });

      // rebuild matrix markings (safe)
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

  /* -----------------------------
     Init
  ------------------------------ */
  buildTabs();
  markMatrixFromExisting();
  bindMatrix();
  renderAll();
})();