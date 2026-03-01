(() => {
  /* ============================================================
     WEEK PICKER (unchanged logic)
     ============================================================ */
  function goToMonday(targetISO) {
    const url = new URL(window.location.href);
    if (targetISO) url.searchParams.set("monday", targetISO);
    else url.searchParams.delete("monday");
    window.location.href = url.toString();
  }

  const btnPrev = document.getElementById("prevWeekBtn");
  const btnNext = document.getElementById("nextWeekBtn");
  [btnPrev, btnNext].forEach(btn => {
    if (!btn || btn.disabled) return;
    btn.addEventListener("click", e => {
      e.preventDefault();
      if (btn.dataset.target) goToMonday(btn.dataset.target);
    });
  });

  const pickerBtn = document.getElementById("weekPickerBtn");
  const originalMenu = document.getElementById("weekMenu");
  let menu = originalMenu;
  let isPortaled = false;

  function portalMenu() {
    if (!isPortaled) { document.body.appendChild(menu); isPortaled = true; }
  }
  function restoreMenu() {
    if (isPortaled) { document.querySelector(".week-picker")?.appendChild(menu); isPortaled = false; }
  }
  function positionMenu() {
    if (!pickerBtn || !menu) return;
    const rect = pickerBtn.getBoundingClientRect();
    const gap = 6;
    let top = rect.bottom + gap;
    let left = rect.left + rect.width / 2;
    const mw = Math.max(menu.offsetWidth || 240, 240);
    const half = mw / 2;
    if (left - half < 8) left = 8 + half;
    if (left + half > window.innerWidth - 8) left = window.innerWidth - 8 - half;
    if (top + 280 > window.innerHeight - 8) top = Math.max(8, rect.top - gap - 280);
    menu.style.top = `${top}px`;
    menu.style.left = `${left}px`;
  }
  function openMenu() {
    if (!menu) return;
    portalMenu();
    menu.hidden = false;
    pickerBtn?.setAttribute("aria-expanded", "true");
    positionMenu();
    menu.focus({ preventScroll: true });
    window.addEventListener("resize", positionMenu);
    window.addEventListener("scroll", positionMenu, { passive: true });
  }
  function closeMenu() {
    if (!menu) return;
    menu.hidden = true;
    pickerBtn?.setAttribute("aria-expanded", "false");
    window.removeEventListener("resize", positionMenu);
    window.removeEventListener("scroll", positionMenu);
    restoreMenu();
  }
  pickerBtn?.addEventListener("click", e => {
    e.preventDefault();
    pickerBtn.getAttribute("aria-expanded") === "true" ? closeMenu() : openMenu();
  });
  menu?.addEventListener("click", e => {
    const opt = e.target.closest(".week-option");
    if (!opt) return;
    goToMonday(opt.dataset.value);
    closeMenu();
  });
  menu?.addEventListener("keydown", e => {
    const opts = Array.from(menu.querySelectorAll(".week-option"));
    const idx = opts.indexOf(document.activeElement);
    if (e.key === "Escape") { closeMenu(); pickerBtn?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); (opts[idx + 1] || opts[0])?.focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); (opts[idx - 1] || opts[opts.length - 1])?.focus(); }
    else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      const opt = document.activeElement;
      if (opt?.classList.contains("week-option")) { goToMonday(opt.dataset.value); closeMenu(); }
    }
  });
  menu?.querySelectorAll(".week-option").forEach(el => el.setAttribute("tabindex", "-1"));
  document.addEventListener("click", e => {
    if (!menu || menu.hidden) return;
    if (pickerBtn?.contains(e.target) || menu.contains(e.target)) return;
    closeMenu();
  });

  /* ============================================================
     DATA & STATE
     ============================================================ */
  const pdDataEl = document.getElementById("pd-data");
  if (!pdDataEl) return;
  let PD = JSON.parse(pdDataEl.textContent);

  let drafts = PD.draftShifts;
  let published = PD.publishedShifts;

  const PERIODS = ["morning", "afternoon", "evening"];
  const PERIOD_LABEL = { morning: "Ochtend", afternoon: "Middag", evening: "Vooravond" };
  const LOC_COLORS = { green: "#22c55e", red: "#ef4444", blue: "#3b82f6" };
  // Tint values used for both table row backgrounds and legend swatches (same alpha)
  const LOC_TINTS  = { green: "#22c55e25", red: "#ef444425", blue: "#3b82f625" };

  function getCsrf() {
    return document.cookie.split("; ").find(r => r.startsWith("csrftoken="))?.split("=")[1] ?? "";
  }

  /* ============================================================
     EFFECTIVE ASSIGNMENT HELPERS
     ============================================================ */
  function effectiveShift(userId, dateISO, period) {
    const draft = drafts.find(d => d.user_id === userId && d.date === dateISO && d.period === period);
    if (draft) {
      if (draft.action === "delete") return { task_id: null, isDraft: true, isDelete: true };
      return { task_id: draft.task_id, isDraft: true, isDelete: false };
    }
    const pub = published.find(s => s.user_id === userId && s.date === dateISO && s.period === period);
    if (pub) return { task_id: pub.task_id, isDraft: false, isDelete: false };
    return null;
  }

  function usersForSlot(taskId, dateISO, period) {
    const result = [];
    for (const u of PD.users) {
      const eff = effectiveShift(u.id, dateISO, period);
      if (eff && !eff.isDelete && eff.task_id === taskId) {
        result.push({ user: u, isDraft: eff.isDraft });
      }
    }
    return result;
  }

  function taskForUserSlot(userId, dateISO, period) {
    const eff = effectiveShift(userId, dateISO, period);
    if (!eff || eff.isDelete) return null;
    return eff.task_id;
  }

  function assignedCount(taskId, dateISO, period) {
    return usersForSlot(taskId, dateISO, period).length;
  }

  function taskMin(task, dateISO, period) {
    return task.min?.[dateISO]?.[period] ?? 0;
  }

  function totalDayAssigned(dateISO) {
    let count = 0;
    for (const u of PD.users) {
      for (const p of PERIODS) {
        if (taskForUserSlot(u.id, dateISO, p) !== null) count++;
      }
    }
    return count;
  }

  function totalWeekAssigned() {
    let count = 0;
    for (const day of PD.days) count += totalDayAssigned(day.iso);
    return count;
  }

  /* ============================================================
     DONUT CHARTS
     ============================================================ */
  function dayStats(dateISO) {
    let planned = 0, required = 0;
    for (const loc of PD.locations) {
      for (const t of loc.tasks) {
        for (const p of PERIODS) {
          const min = taskMin(t, dateISO, p);
          required += min;
          planned += Math.min(assignedCount(t.id, dateISO, p), min);
        }
      }
    }
    return { planned, required };
  }

  function dayTooltipData(dateISO) {
    const rows = [];
    for (const period of PERIODS) {
      const tasks = [];
      for (const loc of PD.locations) {
        for (const t of loc.tasks) {
          const min = taskMin(t, dateISO, period);
          const count = assignedCount(t.id, dateISO, period);
          if (min > 0 || count > 0) tasks.push({ name: t.name, count, min });
        }
      }
      if (tasks.length) rows.push({ period, tasks });
    }
    return rows;
  }

  function weekStats() {
    let planned = 0, required = 0;
    for (const day of PD.days) {
      const s = dayStats(day.iso);
      planned += s.planned; required += s.required;
    }
    return { planned, required };
  }

  function weekTooltipData() {
    const rows = [];
    for (const period of PERIODS) {
      const tasks = [];
      for (const loc of PD.locations) {
        for (const t of loc.tasks) {
          let count = 0, min = 0;
          for (const day of PD.days) {
            count += assignedCount(t.id, day.iso, period);
            min += taskMin(t, day.iso, period);
          }
          if (min > 0 || count > 0) tasks.push({ name: t.name, count, min });
        }
      }
      if (tasks.length) rows.push({ period, tasks });
    }
    return rows;
  }

  let tooltipEl = null;
  function getTooltipEl() {
    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.style.cssText = [
        "position:fixed;z-index:9999;pointer-events:none",
        "background:var(--panel);border:1px solid var(--border);border-radius:12px",
        "padding:10px 12px;font-size:0.76rem;min-width:180px;max-width:240px",
        "box-shadow:0 8px 24px rgba(0,0,0,.4)",
      ].join(";");
      document.body.appendChild(tooltipEl);
    }
    return tooltipEl;
  }

  function showDonutTooltip(evt, rows, label) {
    const el = getTooltipEl();
    let html = `<div style="font-weight:900;margin-bottom:6px;">${label}</div>`;
    for (const { period, tasks } of rows) {
      html += `<div style="font-weight:800;color:var(--muted);margin:6px 0 3px;">${PERIOD_LABEL[period]}</div>`;
      for (const t of tasks) {
        const ok = t.count >= t.min;
        const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;background:${ok ? "#22c55e" : "#ef4444"}"></span>`;
        html += `<div style="display:flex;align-items:center;padding:1px 0;">${dot}<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.name}</span><span style="font-weight:900;margin-left:8px;">${t.count}/${t.min}</span></div>`;
      }
    }
    el.innerHTML = html;
    el.style.display = "block";
    const x = evt.clientX + 12, y = evt.clientY + 12;
    const w = el.offsetWidth || 200, h = el.offsetHeight || 100;
    el.style.left = (x + w > window.innerWidth - 8 ? x - w - 24 : x) + "px";
    el.style.top  = (y + h > window.innerHeight - 8 ? y - h - 24 : y) + "px";
  }

  function hideDonutTooltip() {
    if (tooltipEl) tooltipEl.style.display = "none";
  }

  function buildDonut(canvas, planned, required, countFn) {
    const pct = required > 0 ? Math.min(planned / required, 1) : 1;
    const color = pct >= 1 ? "#22c55e" : pct > 0.5 ? "#f59e0b" : "#ef4444";
    const fontSize = canvas.width < 60 ? 10 : 13;
    return new Chart(canvas, {
      type: "doughnut",
      data: {
        datasets: [{
          data: [required > 0 ? planned : 1, Math.max(required - planned, 0)],
          backgroundColor: [color, "rgba(255,255,255,0.07)"],
          borderWidth: 0,
          borderRadius: 3,
        }],
      },
      options: {
        cutout: "68%",
        animation: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        events: [],
      },
      plugins: [{
        id: "centerText",
        afterDraw(chart) {
          const count = countFn();
          if (count === 0) return;
          const { ctx } = chart;
          const { top, bottom, left, right } = chart.chartArea;
          ctx.save();
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.font = `900 ${fontSize}px sans-serif`;
          ctx.fillStyle = chart.data.datasets[0].backgroundColor[0];
          ctx.fillText(String(count), (left + right) / 2, (top + bottom) / 2);
          ctx.restore();
        },
      }],
    });
  }

  const donutsRow = document.getElementById("pdDonutsRow");
  const dayCharts = [];
  let weekChartRef = null;

  function renderDonuts() {
    if (!donutsRow) return;
    donutsRow.innerHTML = "";
    dayCharts.length = 0;
    weekChartRef = null;

    for (const day of PD.days) {
      const { planned, required } = dayStats(day.iso);
      const item = document.createElement("div");
      item.className = "pd-donut-item";
      const canvas = document.createElement("canvas");
      canvas.width = 52; canvas.height = 52;
      canvas.style.cssText = "width:52px;height:52px;";
      const lbl = document.createElement("div");
      lbl.className = "pd-donut-label";
      lbl.textContent = day.short;
      item.appendChild(canvas);
      item.appendChild(lbl);
      donutsRow.appendChild(item);

      const chart = buildDonut(canvas, planned, required, () => totalDayAssigned(day.iso));
      dayCharts.push({ chart, day });
      canvas.addEventListener("mousemove", evt => showDonutTooltip(evt, dayTooltipData(day.iso), `${day.label} – ${day.daymonth}`));
      canvas.addEventListener("mouseleave", hideDonutTooltip);
    }

    const sep = document.createElement("div");
    sep.className = "pd-donut-sep";
    donutsRow.appendChild(sep);

    const { planned: wp, required: wr } = weekStats();
    const weekItem = document.createElement("div");
    weekItem.className = "pd-donut-item is-week";
    const weekCanvas = document.createElement("canvas");
    weekCanvas.width = 72; weekCanvas.height = 72;
    weekCanvas.style.cssText = "width:72px;height:72px;";
    const weekLbl = document.createElement("div");
    weekLbl.className = "pd-donut-label";
    weekLbl.textContent = "Week";
    weekItem.appendChild(weekCanvas);
    weekItem.appendChild(weekLbl);
    donutsRow.appendChild(weekItem);

    weekChartRef = buildDonut(weekCanvas, wp, wr, totalWeekAssigned);
    weekCanvas.addEventListener("mousemove", evt => showDonutTooltip(evt, weekTooltipData(), "Hele week"));
    weekCanvas.addEventListener("mouseleave", hideDonutTooltip);
  }

  function refreshDonutData() {
    for (const { chart, day } of dayCharts) {
      const { planned, required } = dayStats(day.iso);
      const pct = required > 0 ? Math.min(planned / required, 1) : 1;
      const color = pct >= 1 ? "#22c55e" : pct > 0.5 ? "#f59e0b" : "#ef4444";
      chart.data.datasets[0].data = [required > 0 ? planned : 1, Math.max(required - planned, 0)];
      chart.data.datasets[0].backgroundColor[0] = color;
      chart.update();
    }
    if (weekChartRef) {
      const { planned: wp, required: wr } = weekStats();
      const pct = wr > 0 ? Math.min(wp / wr, 1) : 1;
      const color = pct >= 1 ? "#22c55e" : pct > 0.5 ? "#f59e0b" : "#ef4444";
      weekChartRef.data.datasets[0].data = [wr > 0 ? wp : 1, Math.max(wr - wp, 0)];
      weekChartRef.data.datasets[0].backgroundColor[0] = color;
      weekChartRef.update();
    }
  }

  /* ============================================================
     X/Y INDICATOR HELPERS
     ============================================================ */
  function xyClass(count, min) {
    if (min === 0) return "";
    return count >= min ? "is-ok" : "is-warn";
  }

  function xyText(count, min) {
    return min > 0 ? `${count}/${min}` : `${count}`;
  }

  function dayPeriodXY(dateISO, period) {
    let count = 0, min = 0;
    for (const loc of PD.locations) {
      for (const t of loc.tasks) {
        count += assignedCount(t.id, dateISO, period);
        min += taskMin(t, dateISO, period);
      }
    }
    return { count, min };
  }

  function dayTotalXY(dateISO) {
    let count = 0, min = 0;
    for (const p of PERIODS) {
      const xy = dayPeriodXY(dateISO, p);
      count += xy.count; min += xy.min;
    }
    return { count, min };
  }

  function taskWeekXY(task) {
    let count = 0, min = 0;
    for (const day of PD.days) {
      for (const p of PERIODS) {
        count += assignedCount(task.id, day.iso, p);
        min += taskMin(task, day.iso, p);
      }
    }
    return { count, min };
  }

  function userWeekCount(userId) {
    let count = 0;
    for (const day of PD.days) {
      for (const p of PERIODS) {
        if (taskForUserSlot(userId, day.iso, p) !== null) count++;
      }
    }
    return count;
  }

  // Returns space-separated location names for tasks currently assigned to the user.
  // Used as extra search text so filtering by location name works on user rows.
  function computeUserLocNames(user) {
    const locs = new Set();
    for (const day of PD.days) {
      for (const period of PERIODS) {
        const taskId = taskForUserSlot(user.id, day.iso, period);
        if (taskId !== null) {
          for (const loc of PD.locations) {
            if (loc.tasks.some(t => t.id === taskId)) { locs.add(loc.name); break; }
          }
        }
      }
    }
    return [...locs].join(" ");
  }

  /* ============================================================
     SEARCH / FILTER
     ============================================================ */
  function filterTaskTable(q) {
    if (!taskTableRef) return;
    q = q.toLowerCase().trim();
    taskTableRef.querySelectorAll("tr.pd-task-row").forEach(row => {
      const text = row.innerText.toLowerCase();
      const locName = (row.dataset.locName || "").toLowerCase();
      row.style.display = (!q || text.includes(q) || locName.includes(q)) ? "" : "none";
    });
  }

  function filterUserTable(q) {
    if (!userTableRef) return;
    q = q.toLowerCase().trim();
    userTableRef.querySelectorAll("tr.pd-user-row").forEach(row => {
      const text = row.innerText.toLowerCase();
      const locNames = (row.dataset.locNames || "").toLowerCase();
      row.style.display = (!q || text.includes(q) || locNames.includes(q)) ? "" : "none";
    });
  }

  /* ============================================================
     LOCATION LEGEND
     ============================================================ */
  function renderLegend() {
    const container = document.getElementById("pdLegend");
    if (!container) return;
    container.innerHTML = "";
    for (const loc of PD.locations) {
      const solid = LOC_COLORS[loc.color] || "#888";
      const tint  = LOC_TINTS[loc.color]  || "#88888825";
      const item = document.createElement("div");
      item.className = "pd-legend-item";
      item.innerHTML = `<span class="pd-legend-swatch" style="background:${tint};border-color:${solid};"></span>${loc.name}`;
      container.appendChild(item);
    }
  }

  /* ============================================================
     PLANNING TABLE: PER TAAK
     ============================================================ */
  let taskTableRef = null;

  function buildTaskTable() {
    const wrap = document.getElementById("taskTableWrap");
    if (!wrap) return;

    const table = document.createElement("table");
    table.className = "pd-grid";
    taskTableRef = table;

    // colgroup: Taak (200px) + 18 slot cols (80px each)
    const colgroup = document.createElement("colgroup");
    const col0 = document.createElement("col"); col0.style.width = "200px"; colgroup.appendChild(col0);
    for (let i = 0; i < PD.days.length * PERIODS.length; i++) {
      const col = document.createElement("col"); col.style.width = "80px"; colgroup.appendChild(col);
    }
    table.appendChild(colgroup);

    const thead = document.createElement("thead");

    // Row 1: Taak header (no rowspan) + day headers with colspan=3
    const tr1 = document.createElement("tr");
    const thTask = document.createElement("th");
    thTask.className = "pd-col-sticky";
    thTask.textContent = "Taak";
    tr1.appendChild(thTask);

    for (const day of PD.days) {
      const { count, min } = dayTotalXY(day.iso);
      const th = document.createElement("th");
      th.colSpan = 3;
      th.className = `pd-th-day ${xyClass(count, min)}`;
      th.innerHTML = `${day.short} ${day.daymonth}<span class="pd-th-day-xy" data-day-xy="${day.iso}">${xyText(count, min)}</span>`;
      tr1.appendChild(th);
    }
    thead.appendChild(tr1);

    // Row 2: explicit empty cell for Taak column + period sub-headers
    // Empty cell ensures period headers start in the correct column
    const tr2 = document.createElement("tr");
    const emptyTh = document.createElement("th");
    emptyTh.className = "pd-col-sticky pd-th-empty";
    tr2.appendChild(emptyTh);

    for (const day of PD.days) {
      for (const period of PERIODS) {
        const { count, min } = dayPeriodXY(day.iso, period);
        const th = document.createElement("th");
        th.className = `pd-th-period ${xyClass(count, min)}`;
        th.innerHTML = `<span class="pd-th-period-label">${PERIOD_LABEL[period]}</span><span class="pd-th-period-xy" data-period-xy="${day.iso}|${period}">${xyText(count, min)}</span>`;
        tr2.appendChild(th);
      }
    }
    thead.appendChild(tr2);
    table.appendChild(thead);

    // TBODY
    const tbody = document.createElement("tbody");
    for (const loc of PD.locations) {
      for (const task of loc.tasks) {
        const row = document.createElement("tr");
        row.className = "pd-task-row";
        row.dataset.taskId = task.id;
        row.dataset.locColor = loc.color;
        row.dataset.locName = loc.name;

        const tdName = document.createElement("td");
        tdName.className = "pd-col-sticky";
        const { count: wc, min: wm } = taskWeekXY(task);
        tdName.innerHTML = `<span class="pd-task-name">${task.name}</span><span class="pd-row-xy" data-task-week-xy="${task.id}">${xyText(wc, wm)}</span>`;
        row.appendChild(tdName);

        for (const day of PD.days) {
          for (const period of PERIODS) {
            const td = document.createElement("td");
            td.className = "pd-slot-cell";
            td.dataset.taskId = task.id;
            td.dataset.date = day.iso;
            td.dataset.period = period;
            fillTaskSlotCell(td, task, day.iso, period);
            td.addEventListener("click", () => openTaskSlotModal(task, day, period));
            row.appendChild(td);
          }
        }
        tbody.appendChild(row);
      }
    }
    table.appendChild(tbody);
    wrap.innerHTML = "";
    wrap.appendChild(table);
  }

  function fillTaskSlotCell(td, task, dateISO, period) {
    const count = assignedCount(task.id, dateISO, period);
    const min = taskMin(task, dateISO, period);
    td.className = `pd-slot-cell ${xyClass(count, min)}`;
    const occupants = usersForSlot(task.id, dateISO, period);
    let html = "";
    for (const { user, isDraft } of occupants) {
      const draftObj = drafts.find(d => d.user_id === user.id && d.date === dateISO && d.period === period);
      const isDelete = draftObj?.action === "delete";
      const isVast = user.dienstverband === "vast";
      const cls = `pd-chip${isVast ? " is-vast" : ""}${isDelete ? " is-delete" : isDraft ? " is-concept" : ""}`;
      html += `<span class="${cls}">${user.displayName}</span>`;
    }
    td.innerHTML = html || `<span style="opacity:.2;font-size:.65rem;">–</span>`;
  }

  function refreshTaskTable() {
    if (!taskTableRef) return;
    taskTableRef.querySelectorAll("td.pd-slot-cell").forEach(td => {
      const task = findTask(parseInt(td.dataset.taskId));
      if (task) fillTaskSlotCell(td, task, td.dataset.date, td.dataset.period);
    });
    refreshTaskHeaders();
    refreshTaskRowXY();
  }

  function refreshTaskHeaders() {
    if (!taskTableRef) return;
    for (const day of PD.days) {
      const { count, min } = dayTotalXY(day.iso);
      const xyEl = taskTableRef.querySelector(`[data-day-xy="${day.iso}"]`);
      if (xyEl) {
        xyEl.textContent = xyText(count, min);
        const th = xyEl.closest("th");
        if (th) { th.classList.remove("is-ok", "is-warn"); if (xyClass(count, min)) th.classList.add(xyClass(count, min)); }
      }
      for (const period of PERIODS) {
        const { count: pc, min: pm } = dayPeriodXY(day.iso, period);
        const pEl = taskTableRef.querySelector(`[data-period-xy="${day.iso}|${period}"]`);
        if (pEl) {
          pEl.textContent = xyText(pc, pm);
          const th = pEl.closest("th");
          if (th) { th.classList.remove("is-ok", "is-warn"); if (xyClass(pc, pm)) th.classList.add(xyClass(pc, pm)); }
        }
      }
    }
  }

  function refreshTaskRowXY() {
    if (!taskTableRef) return;
    for (const loc of PD.locations) {
      for (const task of loc.tasks) {
        const { count, min } = taskWeekXY(task);
        const el = taskTableRef.querySelector(`[data-task-week-xy="${task.id}"]`);
        if (el) el.textContent = xyText(count, min);
      }
    }
  }

  /* ============================================================
     PLANNING TABLE: PER WERKNEMER
     ============================================================ */
  let userTableRef = null;
  let userSortState = [];

  function addOrToggleUserSort(col) {
    const idx = userSortState.findIndex(s => s.col === col);
    if (idx === -1) {
      userSortState.push({ col, dir: "asc" });
    } else if (userSortState[idx].dir === "asc") {
      userSortState[idx].dir = "desc";
    } else {
      userSortState.splice(idx, 1);
    }
    buildUserTable();
  }

  function sortedUsers() {
    return [...PD.users].sort((a, b) => {
      for (const { col, dir } of userSortState) {
        let cmp = 0;
        if (col === "user") {
          const da = a.dienstverband === "vast" ? 0 : 1;
          const db = b.dienstverband === "vast" ? 0 : 1;
          cmp = da - db;
        } else if (col === "function") {
          cmp = a.function_rank - b.function_rank;
          if (cmp === 0) cmp = a.function.localeCompare(b.function, "nl");
        } else if (col === "shifts") {
          cmp = userWeekCount(a.id) - userWeekCount(b.id);
        }
        if (cmp !== 0) return dir === "asc" ? cmp : -cmp;
      }
      if (a.function_rank !== b.function_rank) return a.function_rank - b.function_rank;
      return a.displayName.localeCompare(b.displayName, "nl");
    });
  }

  function buildUserTable() {
    const wrap = document.getElementById("userTableWrap");
    if (!wrap) return;

    const table = document.createElement("table");
    table.className = "pd-grid";
    userTableRef = table;

    // colgroup: Medewerker (240px) + Functie (150px) + Diensten (100px) + 18 slot cols (80px)
    const colgroup = document.createElement("colgroup");
    [240, 150, 100].forEach(w => {
      const col = document.createElement("col"); col.style.width = `${w}px`; colgroup.appendChild(col);
    });
    for (let i = 0; i < PD.days.length * PERIODS.length; i++) {
      const col = document.createElement("col"); col.style.width = "80px"; colgroup.appendChild(col);
    }
    table.appendChild(colgroup);

    const thead = document.createElement("thead");

    // Row 1: sortable fixed headers (no rowspan) + day headers
    const tr1 = document.createElement("tr");

    function makeSortHeader(label, col, isSticky) {
      const th = document.createElement("th");
      th.className = (isSticky ? "pd-col-sticky " : "") + "is-sortable";
      const entry = userSortState.find(s => s.col === col);
      if (entry) th.classList.add(entry.dir === "asc" ? "is-sorted-asc" : "is-sorted-desc");
      th.textContent = label;
      th.addEventListener("click", () => addOrToggleUserSort(col));
      return th;
    }

    tr1.appendChild(makeSortHeader("Medewerker", "user", true));
    tr1.appendChild(makeSortHeader("Functie", "function", false));
    tr1.appendChild(makeSortHeader("Diensten", "shifts", false));

    for (const day of PD.days) {
      const { count, min } = dayTotalXY(day.iso);
      const th = document.createElement("th");
      th.colSpan = 3;
      th.className = `pd-th-day ${xyClass(count, min)}`;
      th.innerHTML = `${day.short} ${day.daymonth}<span class="pd-th-day-xy" data-user-day-xy="${day.iso}">${xyText(count, min)}</span>`;
      tr1.appendChild(th);
    }
    thead.appendChild(tr1);

    // Row 2: explicit empty cells for the 3 fixed columns + period sub-headers
    const tr2 = document.createElement("tr");
    const emptyMedew = document.createElement("th");
    emptyMedew.className = "pd-col-sticky pd-th-empty";
    tr2.appendChild(emptyMedew);
    tr2.appendChild(Object.assign(document.createElement("th"), { className: "pd-th-empty" }));
    tr2.appendChild(Object.assign(document.createElement("th"), { className: "pd-th-empty" }));

    for (const day of PD.days) {
      for (const period of PERIODS) {
        const { count, min } = dayPeriodXY(day.iso, period);
        const th = document.createElement("th");
        th.className = `pd-th-period ${xyClass(count, min)}`;
        th.innerHTML = `<span class="pd-th-period-label">${PERIOD_LABEL[period]}</span><span class="pd-th-period-xy" data-user-period-xy="${day.iso}|${period}">${xyText(count, min)}</span>`;
        tr2.appendChild(th);
      }
    }
    thead.appendChild(tr2);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const user of sortedUsers()) {
      tbody.appendChild(buildUserRow(user));
    }
    table.appendChild(tbody);
    wrap.innerHTML = "";
    wrap.appendChild(table);
    // Re-apply search filter after sort rebuilds the table
    filterUserTable(document.getElementById("userSearch")?.value || "");
  }

  function buildUserRow(user) {
    const row = document.createElement("tr");
    row.className = "pd-user-row";
    row.dataset.userId = user.id;
    row.dataset.locNames = computeUserLocNames(user);

    const tdName = document.createElement("td");
    tdName.className = "pd-col-sticky";
    tdName.innerHTML = `<span class="pd-user-name${user.dienstverband === "vast" ? " is-vast" : ""}">${user.displayName}</span>`;
    row.appendChild(tdName);

    const tdFunc = document.createElement("td");
    tdFunc.className = "pd-col-meta";
    tdFunc.textContent = user.function;
    row.appendChild(tdFunc);

    const tdShifts = document.createElement("td");
    tdShifts.className = "pd-col-meta";
    tdShifts.dataset.userShiftsCell = user.id;
    tdShifts.textContent = String(userWeekCount(user.id));
    row.appendChild(tdShifts);

    for (const day of PD.days) {
      for (const period of PERIODS) {
        const td = document.createElement("td");
        td.className = "pd-slot-cell";
        td.dataset.userId = user.id;
        td.dataset.date = day.iso;
        td.dataset.period = period;
        fillUserSlotCell(td, user, day.iso, period);
        td.addEventListener("click", () => openUserSlotModal(user, day, period));
        row.appendChild(td);
      }
    }
    return row;
  }

  function fillUserSlotCell(td, user, dateISO, period) {
    const taskId = taskForUserSlot(user.id, dateISO, period);
    const draftObj = drafts.find(d => d.user_id === user.id && d.date === dateISO && d.period === period);
    const isDelete = draftObj?.action === "delete";
    const isDraft = !!draftObj && !isDelete;

    if (taskId === null && !isDelete) {
      td.innerHTML = "";
      td.className = "pd-slot-cell";
      return;
    }
    const task = taskId ? findTask(taskId) : null;
    const cls = `pd-task-chip${isDelete ? " is-delete" : isDraft ? " is-concept" : ""}`;
    td.className = "pd-slot-cell";
    td.innerHTML = `<span class="${cls}">${task ? task.name : "–"}</span>`;
  }

  function refreshUserTable() {
    if (!userTableRef) return;
    userTableRef.querySelectorAll("td.pd-slot-cell").forEach(td => {
      const user = PD.users.find(u => u.id === parseInt(td.dataset.userId));
      if (user) fillUserSlotCell(td, user, td.dataset.date, td.dataset.period);
    });
    // Keep loc-names in sync so search by location stays accurate after save
    userTableRef.querySelectorAll("tr.pd-user-row").forEach(row => {
      const user = PD.users.find(u => u.id === parseInt(row.dataset.userId));
      if (user) row.dataset.locNames = computeUserLocNames(user);
    });
    refreshUserHeaders();
    refreshUserWeekCounts();
    // Re-apply search filter (state may have changed loc assignments)
    filterUserTable(document.getElementById("userSearch")?.value || "");
  }

  function refreshUserHeaders() {
    if (!userTableRef) return;
    for (const day of PD.days) {
      const { count, min } = dayTotalXY(day.iso);
      const el = userTableRef.querySelector(`[data-user-day-xy="${day.iso}"]`);
      if (el) el.textContent = xyText(count, min);
      for (const period of PERIODS) {
        const { count: pc, min: pm } = dayPeriodXY(day.iso, period);
        const pEl = userTableRef.querySelector(`[data-user-period-xy="${day.iso}|${period}"]`);
        if (pEl) pEl.textContent = xyText(pc, pm);
      }
    }
  }

  function refreshUserWeekCounts() {
    if (!userTableRef) return;
    for (const user of PD.users) {
      const el = userTableRef.querySelector(`[data-user-shifts-cell="${user.id}"]`);
      if (el) el.textContent = String(userWeekCount(user.id));
    }
  }

  /* ============================================================
     MODAL
     ============================================================ */
  const backdrop = document.getElementById("pdModalBackdrop");
  const modal = document.getElementById("pdModal");
  const modalTitle = document.getElementById("pdModalTitle");
  const modalMeta = document.getElementById("pdModalMeta");
  const modalMin = document.getElementById("pdModalMin");

  let modalSelect2 = null;
  let currentSlot = null;

  function openModal() {
    backdrop.classList.add("is-open");
    modal.classList.add("is-open");
    backdrop.removeAttribute("aria-hidden");
    modal.removeAttribute("aria-hidden");
  }

  function closeModal() {
    backdrop.classList.remove("is-open");
    modal.classList.remove("is-open");
    if (modalSelect2) {
      try { window.$("#pdModalSelect").off("change.pd").select2("destroy"); } catch (_) {}
      modalSelect2 = null;
    }
    document.getElementById("pdModalSelect").innerHTML = "";
    currentSlot = null;
  }

  document.getElementById("pdModalClose")?.addEventListener("click", closeModal);
  backdrop?.addEventListener("click", e => { if (e.target === backdrop) closeModal(); });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) closeModal();
  });

  /* --- Task slot modal --- */
  function openTaskSlotModal(task, day, period) {
    currentSlot = { mode: "task", task, day, period };
    modalTitle.textContent = task.name;
    modalMeta.textContent = `${day.label} – ${PERIOD_LABEL[period]}`;

    const min = taskMin(task, day.iso, period);
    const count = assignedCount(task.id, day.iso, period);
    modalMin.innerHTML = `Minimale bezetting: <strong>${min}</strong> &nbsp;|&nbsp; Ingepland: <strong>${count}</strong>`;

    const currentIds = usersForSlot(task.id, day.iso, period).map(o => o.user.id);
    const available = PD.users.filter(u => u.availability?.[day.iso]?.[period] || currentIds.includes(u.id));
    populateTaskSelect(available, currentIds);

    openModal();
    initSelect2Multi(available, "Zoek medewerker…");
    bindTaskChangeHandler(task, day, period);
  }

  function populateTaskSelect(available, currentIds) {
    const select = document.getElementById("pdModalSelect");
    select.innerHTML = "";
    select.multiple = true;

    // Sort option as first disabled item — rendered as clickable row inside dropdown
    const sortOpt = document.createElement("option");
    sortOpt.value = "__sort__";
    sortOpt.disabled = true;
    sortOpt.text = "Sorteer";
    select.appendChild(sortOpt);

    for (const u of available) {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.text = `${u.displayName} (${u.function})`;
      if (currentIds && currentIds.includes(u.id)) opt.selected = true;
      select.appendChild(opt);
    }
  }

  function bindTaskChangeHandler(task, day, period) {
    let saveTimer = null;
    window.$("#pdModalSelect").off("change.pd").on("change.pd", () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => autosaveTaskSlot(task, day, period), 300);
    });
  }

  // Sort called from inside the select2 dropdown — preserves selections, reopens dropdown
  function doInlineSort() {
    if (!currentSlot || currentSlot.mode !== "task") return;
    const { task, day, period } = currentSlot;

    const selectedIds = new Set((window.$("#pdModalSelect").val() || []).map(Number));
    const currentIds = usersForSlot(task.id, day.iso, period).map(o => o.user.id);
    const available = PD.users.filter(u => u.availability?.[day.iso]?.[period] || currentIds.includes(u.id));
    available.sort((a, b) => {
      const da = a.dienstverband === "vast" ? 0 : 1;
      const db = b.dienstverband === "vast" ? 0 : 1;
      if (da !== db) return da - db;
      if (a.function_rank !== b.function_rank) return a.function_rank - b.function_rank;
      return a.displayName.localeCompare(b.displayName, "nl");
    });

    try { window.$("#pdModalSelect").off("change.pd").select2("destroy"); } catch (_) {}

    populateTaskSelect(available, [...selectedIds]);
    initSelect2Multi(available, "Zoek medewerker…");
    setTimeout(() => {
      window.$("#pdModalSelect").select2("open");
      bindTaskChangeHandler(task, day, period);
    }, 10);
  }

  function initSelect2Multi(users, placeholder) {
    const $ = window.$;
    modalSelect2 = $("#pdModalSelect").select2({
      placeholder,
      // dropdownParent body avoids clipping by modal overflow
      dropdownParent: $(document.body),
      width: "100%",
      templateResult: data => {
        if (!data.id) return data.text;

        // Inline sort row at the top of the dropdown
        if (String(data.id) === "__sort__") {
          const el = $('<div class="pd-inline-sort">⇅ Sorteer op dienstverband</div>');
          el.on("mousedown", e => {
            e.preventDefault();
            e.stopImmediatePropagation();
            doInlineSort();
          });
          return el;
        }

        const user = users.find(u => String(u.id) === String(data.id));
        if (!user) return data.text;
        const bold = user.dienstverband === "vast" ? "font-weight:900;" : "";
        return $(`<span style="${bold}">${user.displayName} <span style="color:var(--muted);font-size:.85em;">(${user.function})</span></span>`);
      },
      templateSelection: data => {
        if (!data.id || String(data.id) === "__sort__") return null;
        const user = users.find(u => String(u.id) === String(data.id));
        if (!user) return data.text;
        const bold = user.dienstverband === "vast" ? "font-weight:900;" : "";
        return $(`<span style="${bold}">${user.displayName}</span>`);
      },
    });
  }

  async function autosaveTaskSlot(task, day, period) {
    const selectedIds = (window.$("#pdModalSelect").val() || []).map(Number).filter(n => n > 0);
    const res = await fetch(PD.assignSlotUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
      body: JSON.stringify({
        task_id: task.id, date: day.iso, period,
        user_ids: selectedIds, week_start: PD.weekStart, week_end: PD.weekEnd,
      }),
    });
    const data = await res.json();
    if (data.ok) applyStateUpdate(data);
  }

  /* --- User slot modal --- */
  function openUserSlotModal(user, day, period) {
    currentSlot = { mode: "user", user, day, period };
    modalTitle.textContent = user.displayName;
    modalMeta.textContent = `${day.label} – ${PERIOD_LABEL[period]}`;
    modalMin.textContent = "";

    const currentTaskId = taskForUserSlot(user.id, day.iso, period);
    const select = document.getElementById("pdModalSelect");
    select.innerHTML = "";
    select.multiple = false;
    select.removeAttribute("multiple");

    const emptyOpt = document.createElement("option");
    emptyOpt.value = "";
    emptyOpt.text = "– geen taak –";
    if (!currentTaskId) emptyOpt.selected = true;
    select.appendChild(emptyOpt);

    const allTasks = [];
    for (const loc of PD.locations) {
      for (const t of loc.tasks) {
        const count = assignedCount(t.id, day.iso, period);
        const min = taskMin(t, day.iso, period);
        allTasks.push({ task: t, loc, count, min });
      }
    }
    for (const { task, loc, count, min } of allTasks) {
      const opt = document.createElement("option");
      opt.value = task.id;
      opt.text = `${task.name} (${loc.name}) – ${count}/${min}`;
      if (currentTaskId === task.id) opt.selected = true;
      select.appendChild(opt);
    }

    openModal();
    const $ = window.$;
    modalSelect2 = $("#pdModalSelect").select2({
      placeholder: "Kies een taak…",
      dropdownParent: $(document.body),
      width: "100%",
      allowClear: true,
      templateResult: data => {
        if (!data.id) return data.text;
        const entry = allTasks.find(e => String(e.task.id) === String(data.id));
        if (!entry) return data.text;
        const ok = entry.count >= entry.min;
        const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:${ok ? "#22c55e" : "#ef4444"}"></span>`;
        return $(`<span>${dot}${entry.task.name} <span style="color:var(--muted);font-size:.85em;">(${entry.loc.name}) ${entry.count}/${entry.min}</span></span>`);
      },
    });
    $("#pdModalSelect").off("change.pd").on("change.pd", () => autosaveUserSlot(user, day, period));
  }

  async function autosaveUserSlot(user, day, period) {
    const val = window.$("#pdModalSelect").val();
    const taskId = val ? parseInt(val) : null;

    if (taskId) {
      const res = await fetch(PD.saveConceptUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
        body: JSON.stringify({
          items: [{ user_id: user.id, date: day.iso, period, task_id: taskId }],
          week_start: PD.weekStart, week_end: PD.weekEnd,
        }),
      });
      const data = await res.json();
      if (data.ok) applyStateUpdate(data);
    } else {
      const res = await fetch(PD.deleteShiftUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
        body: JSON.stringify({
          user_id: user.id, date: day.iso, period,
          week_start: PD.weekStart, week_end: PD.weekEnd,
        }),
      });
      const data = await res.json();
      if (data.ok) applyStateUpdate(data);
    }
  }

  /* ============================================================
     STATE UPDATE
     ============================================================ */
  function applyStateUpdate(data) {
    if (data.draftShifts !== undefined) drafts = data.draftShifts;
    if (data.publishedShifts !== undefined) published = data.publishedShifts;
    if (data.unpublishedCount !== undefined) updateUnpublishedBadge(data.unpublishedCount);
    refreshTaskTable();
    refreshUserTable();
    refreshDonutData();
  }

  function updateUnpublishedBadge(count) {
    const el = document.getElementById("pdUnpublishedCount");
    if (el) el.textContent = count;
  }

  /* ============================================================
     PUBLISH
     ============================================================ */
  document.getElementById("pdPublishWeekBtn")?.addEventListener("click", async () => {
    if (!confirm("Weekrooster publiceren? Dit wordt zichtbaar voor alle medewerkers en zij ontvangen een melding.")) return;
    const res = await fetch(PD.publishUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
      body: JSON.stringify({ week_start: PD.weekStart, week_end: PD.weekEnd }),
    });
    const data = await res.json();
    if (data.ok) window.location.reload();
  });

  document.getElementById("pdCopyPrevWeekBtn")?.addEventListener("click", async () => {
    const ok = confirm(
      "Shifts van vorige week kopiëren?\n\n" +
      "Dit vult de diensten van vorige week in voor deze week " +
      "voor vaste medewerkers met beschikbaarheid op dat dagdeel deze week (beschikbaarheid wordt automatisch gevuld op basis van vaste werkdagen). " +
      "Slots die al zijn ingevuld voor deze week worden overgeslagen."
    );
    if (!ok) return;
    const res = await fetch(PD.copyPrevWeekUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
      body: JSON.stringify({ week_start: PD.weekStart, week_end: PD.weekEnd }),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Er is iets misgegaan.");
      return;
    }
    if (data.empty) {
      alert("Geen shifts gevonden voor vaste medewerkers in de vorige week.");
      return;
    }
    if (data.copied === 0) {
      alert("Geen nieuwe shifts toegevoegd — beschikbaarheid ontbreekt of al ingevuld.");
      return;
    }
    applyStateUpdate(data);
  });

  /* ============================================================
     SEGMENTED CONTROL
     ============================================================ */
  const segTask = document.getElementById("segTabTask");
  const segUser = document.getElementById("segTabUser");
  const tabTask = document.getElementById("tabTask");
  const tabUser = document.getElementById("tabUser");

  segTask?.addEventListener("click", () => {
    segTask.classList.add("is-active"); segUser.classList.remove("is-active");
    segTask.setAttribute("aria-selected", "true"); segUser.setAttribute("aria-selected", "false");
    tabTask.hidden = false; tabUser.hidden = true;
  });

  segUser?.addEventListener("click", () => {
    segUser.classList.add("is-active"); segTask.classList.remove("is-active");
    segUser.setAttribute("aria-selected", "true"); segTask.setAttribute("aria-selected", "false");
    tabUser.hidden = false; tabTask.hidden = true;
    if (!userTableRef) buildUserTable();
  });

  /* ============================================================
     FIND HELPERS
     ============================================================ */
  function findTask(taskId) {
    for (const loc of PD.locations) {
      const t = loc.tasks.find(t => t.id === taskId);
      if (t) return t;
    }
    return null;
  }

  /* ============================================================
     INIT
     ============================================================ */
  updateUnpublishedBadge(PD.unpublishedCount);
  renderDonuts();
  renderLegend();
  buildTaskTable();

  document.getElementById("taskSearch")?.addEventListener("input", e => filterTaskTable(e.target.value));
  document.getElementById("userSearch")?.addEventListener("input", e => filterUserTable(e.target.value));
})();
