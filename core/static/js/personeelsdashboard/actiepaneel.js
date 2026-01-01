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

  // ✅ nieuw: published + drafts
  let publishedShifts = pd.publishedShifts || [];
  let draftShifts = pd.draftShifts || [];

  const saveConceptUrl = pd.saveConceptUrl;
  const deleteShiftUrl = pd.deleteShiftUrl;
  const publishUrl = pd.publishUrl;

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

  function keyFromParts(user_id, date, period){
    return `${user_id}|${date}|${period}`;
  }

  function buildPublishedMap(){
    const m = new Map();
    publishedShifts.forEach(s => m.set(keyFromParts(s.user_id, s.date, s.period), s));
    return m;
  }

  function buildDraftMap(){
    const m = new Map();
    draftShifts.forEach(d => m.set(keyFromParts(d.user_id, d.date, d.period), d));
    return m;
  }

  // effective:
  // - draft delete hides published and shows delete marker
  // - draft upsert overrides published (concept)
  // - else published
  function getEffectiveByKey(k){
    const pub = buildPublishedMap().get(k) || null;
    const dr = buildDraftMap().get(k) || null;

    if (dr && dr.action === "delete"){
      return { kind: "draft_delete", published: pub, draft: dr };
    }
    if (dr && dr.action === "upsert"){
      return { kind: "draft_upsert", published: pub, draft: dr };
    }
    if (pub){
      return { kind: "published", published: pub, draft: null };
    }
    return null;
  }

  function findRectByKey(k){
    const [user_id, date, period] = k.split("|");
    return document.querySelector(`.avail-rect[data-user-id="${user_id}"][data-date="${date}"][data-period="${period}"]`);
  }

  function clearRectMark(rect){
    if (!rect) return;
    delete rect.dataset.shiftKind;
    delete rect.dataset.taskId;
    delete rect.dataset.locationId;
    rect.classList.remove("has-shift","is-accepted","is-concept","is-delete-draft");
  }

  function markRectAs(rect, kind, locId, taskId){
    if (!rect) return;

    rect.classList.add("has-shift");
    rect.dataset.shiftKind = String(kind || "");

    if (locId != null) rect.dataset.locationId = String(locId);
    if (taskId != null) rect.dataset.taskId = String(taskId);

    rect.classList.remove("is-accepted","is-concept","is-delete-draft");
    if (kind === "published") rect.classList.add("is-accepted");
    else if (kind === "draft_upsert") rect.classList.add("is-concept");
    else if (kind === "draft_delete") rect.classList.add("is-delete-draft");

    rect.tabIndex = 0;
    rect.removeAttribute("aria-disabled");
  }

  function markMatrixFromEffective(){
    // reset only shift styles; keep .available as-is
    $all(".avail-rect").forEach(r => clearRectMark(r));

    const pubMap = buildPublishedMap();
    const drMap = buildDraftMap();

    // 1) published (skip if draft delete exists or draft upsert exists -> will be handled by draft)
    pubMap.forEach((s, k) => {
      const dr = drMap.get(k);
      if (dr) return; // any draft overrides visibility in matrix
      const rect = findRectByKey(k);
      markRectAs(rect, "published", s.location_id, s.task_id);
    });

    // 2) drafts
    drMap.forEach((d, k) => {
      const rect = findRectByKey(k);
      if (d.action === "delete"){
        markRectAs(rect, "draft_delete", null, null);
      } else {
        markRectAs(rect, "draft_upsert", d.location_id, d.task_id);
      }
    });
  }

  // state
  const state = {
    selected: new Map(),  // k -> item
    assigned: new Map(),  // k -> {location_id, task_id}
    dirty: new Set(),     // k with unsaved changes
    ui: {
      activeLocId: locations.length ? String(locations[0].id) : "",
      activePeriodByLoc: new Map(), // locId -> "morning"/...
    }
  };

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

    applyPeriodVisibility(state.ui.activeLocId);
  }

  function setActivePeriod(locId, period){
    const locIdStr = String(locId || "");
    if (!locIdStr) return;
    if (!PERIODS.includes(period)) return;

    state.ui.activePeriodByLoc.set(locIdStr, period);
    applyPeriodVisibility(locIdStr);
  }

  function setPeriodForAllLocations(period){
    if (!PERIODS.includes(period)) return;
    locations.forEach(loc => state.ui.activePeriodByLoc.set(String(loc.id), period));
    if (state.ui.activeLocId) applyPeriodVisibility(state.ui.activeLocId);
  }

  function applyPeriodVisibility(locId){
    const locIdStr = String(locId || "");
    const activePeriod = state.ui.activePeriodByLoc.get(locIdStr) || "morning";

    const panel = locPanelsEl.querySelector(`.pd-loc-panel[data-loc-id="${locIdStr}"]`);
    if (!panel) return;

    $all(`button[data-period-pill="1"][data-loc-id="${locIdStr}"]`, panel).forEach(btn => {
      const isActive = btn.dataset.period === activePeriod;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    $all(`.pd-period-panel[data-loc-id="${locIdStr}"]`, panel).forEach(sec => {
      const show = sec.dataset.period === activePeriod;
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
      kind === "delete" ? "verwijderen" :
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
     Build Location UI
  ------------------------------ */
  function buildLocationUI(){
    locPillsEl.innerHTML = "";
    locPanelsEl.innerHTML = "";

    locations.forEach((loc, idx) => {
      const locId = String(loc.id);

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

    locPillsEl.addEventListener("click", (e) => {
      const btn = e.target.closest('button[data-loc-pill="1"]');
      if (!btn) return;
      setActiveLocation(btn.dataset.locId);
    });

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

    const eff = getEffectiveByKey(k);

    if (eff){
      if (eff.kind === "draft_delete"){
        state.selected.set(k, { user_id, group, firstname, date, period, existing: true, kind: "draft_delete" });
        state.assigned.set(k, { location_id: "", task_id: "" });
      } else if (eff.kind === "draft_upsert"){
        state.selected.set(k, { user_id, group, firstname, date, period, existing: true, kind: "draft_upsert" });
        state.assigned.set(k, {
          location_id: String(eff.draft.location_id ?? ""),
          task_id: String(eff.draft.task_id ?? "")
        });
      } else {
        state.selected.set(k, { user_id, group, firstname, date, period, existing: true, kind: "published" });
        state.assigned.set(k, {
          location_id: String(eff.published.location_id ?? ""),
          task_id: String(eff.published.task_id ?? "")
        });
      }
    } else {
      state.selected.set(k, { user_id, group, firstname, date, period, existing: false, kind: "available" });
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
  function buildLocationSelect(current, disabled=false){
    return `
      <select class="admin-select pd-mini-select" data-action="location" ${disabled ? "disabled" : ""}>
        <option value="">Kies locatie…</option>
        ${locations.map(l => `<option value="${l.id}" ${String(current ?? "")===String(l.id)?"selected":""}>${l.name}</option>`).join("")}
      </select>
    `;
  }

  function buildTaskSelect(locId, currentTaskId, disabled=false){
    const tasks = tasksByLocation.get(String(locId)) || [];
    const dis = disabled || !locId;
    return `
      <select class="admin-select pd-mini-select" data-action="task" ${dis ? "disabled" : ""}>
        <option value="">Kies taak…</option>
        ${tasks.map(t => `<option value="${t.id}" ${String(currentTaskId ?? "")===String(t.id)?"selected":""}>${t.name}</option>`).join("")}
      </select>
    `;
  }

  /* -----------------------------
     Shift card header
  ------------------------------ */
  function shiftCardHeader(item){
    let pillKind = "available";

    if (item.kind === "published") pillKind = "active";
    else if (item.kind === "draft_upsert") pillKind = "concept";
    else if (item.kind === "draft_delete") pillKind = "delete";
    else if (item.existing) pillKind = "concept";

    const pill = statusPill(pillKind);

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

    const isDeleteDraft = item.kind === "draft_delete";
    const disableSelects = isDeleteDraft;

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
        ${buildLocationSelect(a.location_id, disableSelects)}
        ${buildTaskSelect(a.location_id, a.task_id, disableSelects)}
        ${rightButtons}
      </div>
    `;

    const locSel = card.querySelector('select[data-action="location"]');
    const taskSel = card.querySelector('select[data-action="task"]');

    if (!disableSelects){
      locSel.addEventListener("change", () => {
        const locId = locSel.value;
        state.assigned.set(k, { location_id: String(locId || ""), task_id: "" });

        // existing published/draft_upsert -> wijzigingen betekenen dirty
        if (item.existing) state.dirty.add(k);

        if (locId){
          setActiveLocation(String(locId));
          setActivePeriod(String(locId), item.period);
        }

        renderAll();
        pop(card);
      });

      taskSel.addEventListener("change", () => {
        const taskId = taskSel.value;
        const cur = state.assigned.get(k) || { location_id: "", task_id: "" };
        state.assigned.set(k, { ...cur, task_id: String(taskId || "") });

        if (item.existing) state.dirty.add(k);

        renderAll();
        pop(card);
      });
    }

    const delBtn = card.querySelector('[data-action="delete"]');
    if (delBtn){
      delBtn.addEventListener("click", async () => {
        await toggleDeleteDraftByKey(k);
      });
    }

    const rmBtn = card.querySelector('[data-action="remove"]');
    if (rmBtn){
      rmBtn.addEventListener("click", () => deselectByKey(k));
    }

    return card;
  }

  function panelShiftCard(shiftLike){
    const user_id = shiftLike.user_id;
    const date = shiftLike.date;
    const period = shiftLike.period;
    const group = shiftLike.group;
    const firstname = shiftLike.firstname;

    const k = `${user_id}|${date}|${period}`;
    const a = {
      location_id: String(shiftLike.location_id ?? ""),
      task_id: String(shiftLike.task_id ?? ""),
    };

    const kind = shiftLike.kind || (shiftLike.existing ? "draft_upsert" : "available");
    const isDeleteDraft = kind === "draft_delete";
    const disableSelects = isDeleteDraft;

    const card = document.createElement("div");
    card.className = `pd-item pd-item--assigned ${kind === "published" ? "pd-item--existing" : ""}`;
    card.dataset.key = k;

    card.innerHTML = `
      <div class="pd-item-main">
        ${shiftCardHeader({
          existing: kind !== "available",
          kind,
          period,
          date,
          firstname,
          group
        })}
      </div>

      <div class="pd-item-actions">
        ${buildLocationSelect(a.location_id, disableSelects)}
        ${buildTaskSelect(a.location_id, a.task_id, disableSelects)}
        ${kind !== "available" ? deleteButtonHtml() : ""}
      </div>
    `;

    const locSel = card.querySelector('select[data-action="location"]');
    const taskSel = card.querySelector('select[data-action="task"]');

    if (!disableSelects){
      locSel.addEventListener("change", () => {
        const locId = String(locSel.value || "");

        // zorg dat hij in selection staat zodra je hem wijzigt
        if (!state.selected.has(k)){
          state.selected.set(k, { user_id, group, firstname, date, period, existing: kind !== "available", kind });
        }

        state.assigned.set(k, { location_id: locId, task_id: "" });
        state.dirty.add(k);

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

        if (!state.selected.has(k)){
          state.selected.set(k, { user_id, group, firstname, date, period, existing: kind !== "available", kind });
        }

        state.assigned.set(k, { location_id: locId, task_id: taskId });
        state.dirty.add(k);

        renderAll();
        pop(card);
      });
    }

    const delBtn = card.querySelector('[data-action="delete"]');
    if (delBtn){
      delBtn.addEventListener("click", async () => {
        await toggleDeleteDraftByKey(k);
      });
    }

    return card;
  }

  /* -----------------------------
     Delete toggle (draft on/off)
  ------------------------------ */
  async function toggleDeleteDraftByKey(k){
    const eff = getEffectiveByKey(k);
    const [user_id, date, period] = k.split("|");

    const msg = (eff && eff.kind === "draft_delete")
      ? "Wil je de verwijdermarkering ongedaan maken?"
      : "Weet je zeker dat je deze dienst wilt verwijderen? (wordt pas definitief na publiceren)";

    const ok = confirm(msg);
    if (!ok) return;

    try{
      const res = await fetch(deleteShiftUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken") || "",
        },
        body: JSON.stringify({
          user_id: Number(user_id),
          date,
          period
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Verwijderen mislukt.");

      // update local draftShifts
      const drMap = buildDraftMap();
      const existingDraft = drMap.get(k) || null;

      if (data.mode === "undone"){
        // draft removed
        draftShifts = draftShifts.filter(d => keyFromParts(d.user_id, d.date, d.period) !== k);
      } else if (data.mode === "marked_delete"){
        // create/keep delete draft
        const pubMap = buildPublishedMap();
        const pub = pubMap.get(k) || null;
        const rect = findRectByKey(k);
        const g = rect?.dataset.group || pub?.group || "—";
        const fn = rect?.dataset.firstname || pub?.firstname || "—";

        const merged = {
          id: data.draft_id || (existingDraft?.id ?? null),
          user_id: Number(user_id),
          group: g,
          firstname: fn,
          date,
          period,
          action: "delete",
          task_id: null,
          task_name: null,
          location_id: null,
          location_name: null,
        };

        const idx = draftShifts.findIndex(x => keyFromParts(x.user_id, x.date, x.period) === k);
        if (idx >= 0) draftShifts[idx] = merged;
        else draftShifts.push(merged);
      }

      // selection/dirties cleanup for this slot
      state.selected.delete(k);
      state.assigned.delete(k);
      state.dirty.delete(k);

      const rect = findRectByKey(k);
      rect?.classList.remove("is-selected");

      markMatrixFromEffective();
      renderAll();

    } catch(err){
      alert(err.message || "Verwijderen mislukt.");
    }
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

  function buildEffectiveListForPanels(){
    const pubMap = buildPublishedMap();
    const drMap = buildDraftMap();

    const list = [];

    // published that are not overridden by draft
    pubMap.forEach((s, k) => {
      const dr = drMap.get(k);
      if (dr) return; // any draft overrides
      list.push({
        kind: "published",
        user_id: s.user_id,
        group: s.group,
        firstname: s.firstname,
        date: s.date,
        period: s.period,
        location_id: s.location_id,
        task_id: s.task_id,
      });
    });

    // drafts
    drMap.forEach((d, k) => {
      if (d.action === "delete"){
        list.push({
          kind: "draft_delete",
          user_id: d.user_id,
          group: d.group,
          firstname: d.firstname,
          date: d.date,
          period: d.period,
          location_id: null,
          task_id: null,
        });
      } else {
        list.push({
          kind: "draft_upsert",
          user_id: d.user_id,
          group: d.group,
          firstname: d.firstname,
          date: d.date,
          period: d.period,
          location_id: d.location_id,
          task_id: d.task_id,
        });
      }
    });

    return list;
  }

  function renderPanels(){
    clearAllPanelContainers();

    // 1) render effective (published + drafts)
    const effective = buildEffectiveListForPanels();

    effective.forEach(s => {
      const per = String(s.period);
      if (!PERIODS.includes(per)) return;

      if (s.kind === "draft_delete"){
        // show delete markers in staging of currently active location for that period
        const fallbackLoc = state.ui.activeLocId || (locations[0] ? String(locations[0].id) : "");
        if (!fallbackLoc) return;
        const staging = document.getElementById(`pdStagingItems-${fallbackLoc}-${per}`);
        staging?.appendChild(panelShiftCard(s));
        return;
      }

      const locId = String(s.location_id ?? "");
      if (!locId) return;

      const taskId = String(s.task_id ?? "");
      if (taskId){
        const container = document.getElementById(`pdTaskItems-${locId}-${taskId}-${per}`);
        container?.appendChild(panelShiftCard(s));
      } else {
        const staging = document.getElementById(`pdStagingItems-${locId}-${per}`);
        staging?.appendChild(panelShiftCard(s));
      }
    });

    // 2) previews (new + dirty existing) - keep old behavior
    for (const it of state.selected.values()){
      const k = keyOf(it);

      // don't show preview for delete-draft selection (no assigns)
      if (it.kind === "draft_delete") continue;

      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      const locId = String(a.location_id);
      const per = String(it.period);
      if (!PERIODS.includes(per)) continue;

      // only preview if new or dirty
      if (it.existing && !state.dirty.has(k)) continue;

      const taskId = String(a.task_id || "");

      const previewKind = it.existing ? (it.kind === "published" ? "draft_upsert" : it.kind) : "draft_upsert";

      if (!taskId){
        const staging = document.getElementById(`pdStagingItems-${locId}-${per}`);
        staging?.appendChild(panelShiftCard({
          kind: previewKind,
          user_id: it.user_id,
          group: it.group,
          firstname: it.firstname,
          date: it.date,
          period: it.period,
          location_id: Number(locId),
          task_id: null,
        }));
      } else {
        const container = document.getElementById(`pdTaskItems-${locId}-${taskId}-${per}`);
        container?.appendChild(panelShiftCard({
          kind: previewKind,
          user_id: it.user_id,
          group: it.group,
          firstname: it.firstname,
          date: it.date,
          period: it.period,
          location_id: Number(locId),
          task_id: Number(taskId),
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

    if (state.ui.activeLocId) applyPeriodVisibility(state.ui.activeLocId);
  }

  /* -----------------------------
     Counts + save enable
  ------------------------------ */
  function renderCounts(){
    // overrides for unsaved dirty changes on existing slots
    const overrideByKey = new Map();
    for (const it of state.selected.values()){
      const k = keyOf(it);

      if (it.kind === "draft_delete") continue;

      // only overrides matter for existing dirty
      if (!it.existing) continue;
      if (!state.dirty.has(k)) continue;

      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      overrideByKey.set(k, {
        location_id: String(a.location_id),
        task_id: String(a.task_id || ""),
      });
    }

    // base effective map (published + drafts)
    const base = new Map();
    const pubMap = buildPublishedMap();
    const drMap = buildDraftMap();

    // published unless overridden by any draft
    pubMap.forEach((s, k) => {
      if (drMap.has(k)) return;
      base.set(k, { location_id: String(s.location_id ?? ""), task_id: String(s.task_id ?? ""), period: String(s.period) });
    });

    // drafts: upsert => base set; delete => remove
    drMap.forEach((d, k) => {
      if (d.action === "delete"){
        base.delete(k);
      } else {
        base.set(k, { location_id: String(d.location_id ?? ""), task_id: String(d.task_id ?? ""), period: String(d.period) });
      }
    });

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

    // 1) count base (skip overrides)
    base.forEach((v, k) => {
      if (overrideByKey.has(k)) return;

      const locId = String(v.location_id ?? "");
      const taskId = String(v.task_id ?? "");
      const per = String(v.period ?? "");

      bumpLoc(locId, per);
      if (taskId) bumpTask(locId, taskId, per);
    });

    // 2) count previews (new + dirty existing)
    for (const it of state.selected.values()){
      const k = keyOf(it);

      if (it.kind === "draft_delete") continue;

      const a = state.assigned.get(k);
      if (!a || !a.location_id) continue;

      // only include if new or dirty
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

      // delete drafts are not "save concept"
      if (it.kind === "draft_delete") continue;

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
     Save concept -> ShiftDraft upsert
  ------------------------------ */
  async function saveConcept(){
    const items = [];

    for (const it of state.selected.values()){
      const k = keyOf(it);

      if (it.kind === "draft_delete") continue;

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

    if (!items.length) return { ok: true, saved: 0 };

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

      // update local draftShifts from response
      (data.saved || []).forEach(s => {
        const k = `${s.user_id}|${s.date}|${s.period}`;
        const rect = findRectByKey(k);
        const group = rect?.dataset.group || state.selected.get(k)?.group || "—";
        const firstname = rect?.dataset.firstname || state.selected.get(k)?.firstname || "—";

        const merged = {
          id: s.draft_id,
          user_id: s.user_id,
          group,
          firstname,
          date: s.date,
          period: s.period,
          action: s.action || "upsert",
          task_id: s.task_id,
          task_name: s.task_name,
          location_id: s.location_id,
          location_name: s.location_name,
        };

        const idx = draftShifts.findIndex(x => `${x.user_id}|${x.date}|${x.period}` === k);
        if (idx >= 0) draftShifts[idx] = merged;
        else draftShifts.push(merged);

        // clear selection state for this key
        state.selected.delete(k);
        state.assigned.delete(k);
        state.dirty.delete(k);

        rect?.classList.remove("is-selected");
      });

      markMatrixFromEffective();
      renderAll();

      return { ok: true, saved: (data.saved || []).length };

    } catch(err){
      alert(err.message || "Opslaan mislukt.");
      return { ok: false, saved: 0 };
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
  // Publish week:
  // - if there are unsaved changes in selection => saveConcept() first
  // - then publish drafts for the week
  // -----------------------------
  const publishBtn = $("#pdPublishWeekBtn");
  if (publishBtn) {
    publishBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      if (!publishUrl) return;

      const msg =
        "Weet je zeker dat je wilt publiceren?\n\n" +
        "Na publiceren krijgen medewerkers een melding en worden de diensten zichtbaar in de Jansen app en de gesynchroniseerde agenda app.\n" +
        "Publiceer bij voorkeur pas als je het rooster voor deze week volledig hebt ingepland.\n\n" +
        "Dit publiceert alle conceptwijzigingen (drafts) van deze week.";

      const ok = confirm(msg);
      if (!ok) return;

      publishBtn.disabled = true;
      const oldText = publishBtn.textContent;
      publishBtn.textContent = "Publiceren…";

      try {
        // 1) save selection if needed
        if (computeReadyToSaveCount() > 0) {
          const savedRes = await saveConcept();
          if (!savedRes.ok) throw new Error("Opslaan mislukt; publiceren geannuleerd.");
        }

        // 2) publish drafts in week
        const res = await fetch(publishUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken") || "",
          },
          body: JSON.stringify({
            week_start: pd.weekStart,
            week_end: pd.weekEnd,
          }),
        });

        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "Publiceren mislukt.");

        window.location.reload(); // Django message + fresh payload
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
  markMatrixFromEffective();
  bindMatrix();
  renderAll();
})();