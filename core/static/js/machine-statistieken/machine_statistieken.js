/* static/js/machine-statistieken/machine_statistieken.js */

/* -------------------------------------------------------
   CONFIGURATIE
------------------------------------------------------- */

const MS_CONFIG = {
  dagTarget:  80_000,
  weekTarget: 400_000,

  dagTargets: [
    { tijd: "08:00", zakjes: 0      },
    { tijd: "09:00", zakjes: 9_000  },
    { tijd: "09:50", zakjes: 17_000 },
    { tijd: "10:10", zakjes: 17_000 },
    { tijd: "11:00", zakjes: 25_000 },
    { tijd: "12:00", zakjes: 34_500 },
    { tijd: "12:30", zakjes: 39_000 },
    { tijd: "13:00", zakjes: 39_000 },
    { tijd: "14:00", zakjes: 49_000 },
    { tijd: "14:50", zakjes: 56_500 },
    { tijd: "15:10", zakjes: 56_500 },
    { tijd: "16:00", zakjes: 65_000 },
    { tijd: "17:00", zakjes: 75_000 },
    { tijd: "17:30", zakjes: 80_000 },
  ],

  pollInterval: 60_000,
};

const MS_USE_DEMO = true;

/* -------------------------------------------------------
   KLEUR-HELPERS
------------------------------------------------------- */

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function c(varName, alpha = 1) {
  const rgb = cssVar(varName).trim().split(/\s+/).join(", ");
  return `rgba(${rgb}, ${alpha})`;
}

function mutedKleur() { return cssVar("--muted"); }
function tekstKleur() { return cssVar("--text"); }
function gridKleur()  { return c("--muted-rgb", 0.12); }
function panelKleur() { return cssVar("--panel"); }

const ACCENT_HEX       = "#072a72";
const STATUS_GROEN_HEX = "#16a34a";
const STATUS_ROOD_HEX  = "#f59e0b"; // oranje

function accentRgba(alpha = 1)      { return hexRgba(ACCENT_HEX, alpha); }
function statusGroenRgba(alpha = 1) { return hexRgba(STATUS_GROEN_HEX, alpha); }

function hexRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* -------------------------------------------------------
   MACHINE KLEUR LOOKUP — hash-gebaseerd
------------------------------------------------------- */

const MACHINE_KLEUR_PALET = [
  "--c-sky", "--c-emerald", "--c-rose", "--c-amber", "--c-indigo",
  "--c-teal", "--c-orange", "--c-violet", "--c-cyan", "--c-purple", "--c-lime",
];

function machineIdHash(id) {
  let h = 5381;
  for (let i = 0; i < id.length; i++) h = (h * 33) ^ id.charCodeAt(i);
  return Math.abs(h) % MACHINE_KLEUR_PALET.length;
}

function machineKleur(machineId, alpha = 1) {
  return c(MACHINE_KLEUR_PALET[machineIdHash(machineId)], alpha);
}

function machineHoverKleur(machineId) {
  return machineKleur(machineId, 0.55);
}

/* -------------------------------------------------------
   CHART DEFAULTS
------------------------------------------------------- */

function applyChartDefaults() {
  Chart.defaults.color       = mutedKleur();
  Chart.defaults.borderColor = gridKleur();
  Chart.defaults.font.family = "inherit";
  Chart.defaults.font.size   = 12;
}

function destroyAllCharts() {
  Object.values(state.charts).forEach(ch => ch?.destroy?.());
  state.charts = {};
}

/* -------------------------------------------------------
   DEMO DATA
------------------------------------------------------- */

function buildDemoData() {
  const nu      = new Date();
  const vandaag = datumString(nu);
  const actieveMachines = ["M1","M2","M3","M4","M5","M6","M7","M8","M9","M10","M11"];

  const vandaagMachines = {
    M1: 3_800, M2: 3_400, M3: 3_600, M4: 3_100,
    M5: 3_500, M6: 3_200, M7: 3_400, M8: 3_000,
    M9: 3_300, M10: 3_100, M11: 2_900,
  };

  function randomDag() {
    const obj = {};
    actieveMachines.forEach(m => { obj[m] = Math.round(6_500 + Math.random() * 5_500); });
    return obj;
  }

  function randomWeek() {
    const obj = {};
    actieveMachines.forEach(m => { obj[m] = Math.round(44_000 + Math.random() * 28_000); });
    return obj;
  }

  function dagenReeks(n) {
    return Array.from({ length: n }, (_, i) => {
      const d = new Date(nu);
      d.setDate(d.getDate() - (n - 1 - i));
      return { datum: datumString(d), machines: randomDag() };
    });
  }

  function wekenReeks(n) {
    return Array.from({ length: n }, (_, i) => {
      const d = new Date(nu);
      d.setDate(d.getDate() - (n - 1 - i) * 7);
      return { week: `W${getWeekNumber(d)}`, machines: randomWeek() };
    });
  }

    const weekDagenDates = volledigeWeekDagen(nu);

    // Alleen Ma–Vr opnemen in week_dagen, zodat Za/Zo als "geen data" verschijnen
    const weekDagenData = weekDagenDates
    .filter(d => {
        const day = d.getDay();            // 0=Zo, 6=Za
        return day !== 0 && day !== 6;     // skip weekend
    })
    .map(d => ({
        datum:    datumString(d),
        machines: datumString(d) === vandaag ? vandaagMachines : randomDag(),
    }));

    const weekTotaal = weekDagenData.reduce(
    (s, d) => s + Object.values(d.machines).reduce((a, v) => a + v, 0), 0
    );

  return {
    vandaag: {
      datum:               vandaag,
      machines:            vandaagMachines,
      week_totaal:         weekTotaal,
      week_dagen:          weekDagenData,
      last_machine_update: new Date(nu.getTime() - 4 * 60 * 1000).toISOString(),
    },
    dagen7:  dagenReeks(7),
    dagen30: dagenReeks(30),
    weken4:  wekenReeks(4),
    weken26: wekenReeks(26),
    weken52: wekenReeks(52),
  };
}

/* -------------------------------------------------------
   LIVE DATA
------------------------------------------------------- */

async function fetchVandaag() {
  const res = await fetch("/baxter/machine-statistieken/api/vandaag/");
  if (!res.ok) throw new Error(`API vandaag failed: ${res.status}`);
  return res.json();
}

async function fetchGeschiedenis(bereik) {
  const res = await fetch(`/baxter/machine-statistieken/api/geschiedenis/?bereik=${encodeURIComponent(bereik)}`);
  if (!res.ok) throw new Error(`API geschiedenis failed: ${res.status}`);
  const json = await res.json();
  return json.data || [];
}

/* -------------------------------------------------------
   STATE
------------------------------------------------------- */

const state = {
  huidigView:   "vandaag",
  dagenBereik:  "dagen7",
  wekenBereik:  "weken4",
  data:         null,
  charts:       {},
  historyCache: {},   // bereik -> data[]
};

/* -------------------------------------------------------
   INITIALISATIE
------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
  applyChartDefaults();
  bindControls();
  bindFullscreenAutoHide();
  bindThemeObserver();
  laadEnRender();
  startPoll();
});

function bindControls() {
  document.getElementById("ms-view-select")?.addEventListener("change", async function () {
    state.huidigView = this.value;
    toonView(state.huidigView);

    const fsBtn = document.getElementById("ms-fullscreen-btn");
    if (fsBtn) fsBtn.style.display = this.value === "vandaag" ? "flex" : "none";

    await ensureHistoryLoadedForCurrentSelection();
    renderAlles();
  });

  document.getElementById("ms-dagen-select")?.addEventListener("change", async function () {
    state.dagenBereik = this.value;
    await ensureHistoryLoaded(this.value);
    renderDagen();
  });

  document.getElementById("ms-weken-select")?.addEventListener("change", async function () {
    state.wekenBereik = this.value;
    await ensureHistoryLoaded(this.value);
    renderWeken();
  });

  document.getElementById("ms-fullscreen-btn")?.addEventListener("click", toggleFullscreen);
  document.getElementById("ms-fullscreen-exit")?.addEventListener("click", toggleFullscreen);
}

function bindThemeObserver() {
  const observer = new MutationObserver(() => {
    applyChartDefaults();
    destroyAllCharts();
    renderAlles();
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
}

function syncDropdowns() {
  const dagenSelect = document.getElementById("ms-dagen-select");
  const wekenSelect = document.getElementById("ms-weken-select");
  if (dagenSelect) dagenSelect.value = state.dagenBereik;
  if (wekenSelect) wekenSelect.value = state.wekenBereik;
}

function bindFullscreenAutoHide() {
  const exitBar = document.getElementById("ms-fullscreen-exit-bar");
  if (!exitBar) return;
  let hideTimer = null;
  function toonExitBar() {
    exitBar.classList.add("visible");
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => exitBar.classList.remove("visible"), 3000);
  }
  document.addEventListener("mousemove",  () => { if (document.body.classList.contains("ms-fullscreen")) toonExitBar(); });
  document.addEventListener("touchstart", () => { if (document.body.classList.contains("ms-fullscreen")) toonExitBar(); });
}

function toonView(naam) {
  document.querySelectorAll(".ms-view").forEach(el => el.classList.remove("active"));
  document.getElementById(`ms-view-${naam}`)?.classList.add("active");
}

/* -------------------------------------------------------
   DATA LADEN
------------------------------------------------------- */

async function ensureHistoryLoaded(bereik) {
  if (MS_USE_DEMO) return;

  if (state.historyCache[bereik]) {
    state.data[bereik] = state.historyCache[bereik];
    return;
  }

  const data = await fetchGeschiedenis(bereik);
  state.historyCache[bereik] = data;
  state.data[bereik] = data;
}

async function ensureHistoryLoadedForCurrentSelection() {
  if (!state.data) return;
  if (state.huidigView === "dagen")  await ensureHistoryLoaded(state.dagenBereik);
  if (state.huidigView === "weken")  await ensureHistoryLoaded(state.wekenBereik);
}

async function laadEnRender() {
  try {
    if (MS_USE_DEMO) {
      state.data = buildDemoData();
    } else {
      if (!state.data) state.data = {};
      state.data.vandaag = await fetchVandaag();

      // refresh alleen de actuele selectie, zodat de demo/DB “laatste datums” logisch blijft
      if (state.huidigView === "dagen") await refreshHistory(state.dagenBereik);
      if (state.huidigView === "weken") await refreshHistory(state.wekenBereik);
    }

    renderAlles();
    syncDropdowns();
    updateLastUpdated();
  } catch (e) {
    console.error(e);
  }
}

async function refreshHistory(bereik) {
  if (MS_USE_DEMO) return;
  const data = await fetchGeschiedenis(bereik);
  state.historyCache[bereik] = data;
  state.data[bereik] = data;
}

function startPoll() {
  setInterval(laadEnRender, MS_CONFIG.pollInterval);
}

function updateLastUpdated() {
  const el  = document.getElementById("ms-last-updated");
  if (!el) return;
  const raw = state.data?.vandaag?.last_machine_update;
  if (!raw) { el.textContent = "Laatst bijgewerkt: onbekend"; return; }
  const dt = new Date(raw);
  el.textContent = `Laatst bijgewerkt: ${dt.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })}`;
}

/* -------------------------------------------------------
   RENDER ALLES
------------------------------------------------------- */

function renderAlles() {
  if (!state.data) return;
  renderVandaag();
  renderDagen();
  renderWeken();
}

/* -------------------------------------------------------
   VANDAAG
------------------------------------------------------- */

function renderVandaag() {
  const d = state.data.vandaag;
  if (!d) return;
  const totaal    = Object.values(d.machines || {}).reduce((s, v) => s + v, 0);
  const weekDagen = d.week_dagen || [];
  renderDonut(totaal);
  renderStatusBadge(totaal);
  renderHorizontalBars(d.machines || {});
  renderTodayLine(totaal);
  renderWeekProgress(d.week_totaal || 0, weekDagen);
}

/* -------------------------------------------------------
   DONUT
------------------------------------------------------- */

Chart.Tooltip.positioners.buitenRing = function (elements, eventPos) {
  if (!elements.length) return false;
  const el  = elements[0].element;
  const cx  = el.x;
  const cy  = el.y;
  const dx  = (eventPos.x ?? cx) - cx;
  const dy  = (eventPos.y ?? cy) - cy;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const r   = el.outerRadius + 16;
  return { x: cx + (dx / len) * r, y: cy + (dy / len) * r };
};

function renderDonut(totaal) {
  const target     = MS_CONFIG.dagTarget;
  const verwacht   = berekenVerwacht(new Date());
  const isOpSchema = totaal >= verwacht;

  let segmenten, kleuren, hoverOffsets, tooltipLabels;

  if (totaal >= target) {
    const overschot = totaal - target;
    segmenten     = [target, overschot, 1];
    kleuren       = [ACCENT_HEX, STATUS_GROEN_HEX, accentRgba(0.06)];
    hoverOffsets  = [6, 6, 0];
    tooltipLabels = [
      `Geproduceerd: ${formatNummer(totaal)} zakjes`,
      `Boven target: +${formatNummer(overschot)} zakjes`,
      null,
    ];
  } else if (isOpSchema) {
    const voorsprong = totaal - verwacht;
    const restLeeg   = target - totaal;
    segmenten     = [verwacht, voorsprong, restLeeg];
    kleuren       = [ACCENT_HEX, STATUS_GROEN_HEX, accentRgba(0.08)];
    hoverOffsets  = [6, 6, 0];
    tooltipLabels = [
      `Geproduceerd: ${formatNummer(totaal)} zakjes`,
      `Voorsprong: +${formatNummer(voorsprong)} zakjes`,
      null,
    ];
  } else {
    const achterstand = verwacht - totaal;
    const restLeeg    = target - verwacht;
    segmenten     = [totaal, achterstand, restLeeg];
    kleuren       = [ACCENT_HEX, STATUS_ROOD_HEX, accentRgba(0.08)];
    hoverOffsets  = [6, 6, 0];
    tooltipLabels = [
      `Geproduceerd: ${formatNummer(totaal)} zakjes`,
      `Achter op schema: −${formatNummer(achterstand)} zakjes`,
      null,
    ];
  }

  setEl("ms-donut-total",        formatNummer(totaal));
  setEl("ms-donut-pct",          `${(totaal / target * 100).toFixed(1)}%`);
  setEl("ms-donut-target-label", `van ${formatNummer(target)}`);

  const ctx = document.getElementById("ms-donut-chart");
  if (!ctx) return;

  if (state.charts.donut) {
    state.charts.donut.data.datasets[0].data            = segmenten;
    state.charts.donut.data.datasets[0].backgroundColor = kleuren;
    state.charts.donut.data.datasets[0].hoverOffset     = hoverOffsets;
    state.charts.donut._tooltipLabels                   = tooltipLabels;
    state.charts.donut.update("none");
    return;
  }

  const chart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data:            segmenten,
        backgroundColor: kleuren,
        borderWidth:     0,
        borderRadius:    4,
        hoverOffset:     hoverOffsets,
      }],
    },
    options: {
      cutout:              "72%",
      responsive:          true,
      maintainAspectRatio: true,
      animation:           { duration: 600 },
      plugins: {
        legend:  { display: false },
        tooltip: {
          position:    "buitenRing",
          caretSize:   0,
          callbacks: {
            title()      { return ""; },
            label(item)  { return chart._tooltipLabels?.[item.dataIndex] ?? null; },
            filter(item) { return chart._tooltipLabels?.[item.dataIndex] != null; },
          },
          backgroundColor: panelKleur(),
          bodyColor:       mutedKleur(),
          borderColor:     gridKleur(),
          borderWidth:     1,
          padding:         10,
          displayColors:   false,
        },
      },
    },
  });

  chart._tooltipLabels = tooltipLabels;
  state.charts.donut   = chart;
}

/* -------------------------------------------------------
   STATUS BADGE
------------------------------------------------------- */

function renderStatusBadge(totaal) {
  const verwacht = berekenVerwacht(new Date());
  const badge    = document.getElementById("ms-status-badge");
  if (!badge) return;
  if (totaal >= verwacht) {
    badge.className = "ms-status-badge on-track";
    badge.innerHTML = `<span class="ms-status-dot"></span> Op schema`;
  } else {
    badge.className = "ms-status-badge behind";
    badge.innerHTML = `<span class="ms-status-dot"></span> ${formatNummer(verwacht - totaal)} achter`;
  }
}

/* -------------------------------------------------------
   HORIZONTALE BAR CHART PER MACHINE (vandaag)
------------------------------------------------------- */

function renderHorizontalBars(machines) {
  const ctx = document.getElementById("ms-hbar-chart");
  if (!ctx) return;

  const gesorteerd   = Object.entries(machines).sort(([a], [b]) => sortMachineId(a, b));
  const labels       = gesorteerd.map(([id]) => id);
  const data         = gesorteerd.map(([, v]) => v);
  const bgKleuren    = labels.map(id => machineKleur(id));
  const hoverKleuren = labels.map(id => machineHoverKleur(id));

  if (state.charts.hbar) {
    state.charts.hbar.data.labels                            = labels;
    state.charts.hbar.data.datasets[0].data                  = data;
    state.charts.hbar.data.datasets[0].backgroundColor       = bgKleuren;
    state.charts.hbar.data.datasets[0].hoverBackgroundColor  = hoverKleuren;
    state.charts.hbar.update("none");
    return;
  }

  state.charts.hbar = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data:                 data,
        backgroundColor:      bgKleuren,
        hoverBackgroundColor: hoverKleuren,
        borderRadius:         4,
        borderSkipped:        false,
      }],
    },
    options: {
      indexAxis:           "y",
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend:  { display: false },
        tooltip: {
          callbacks: {
            label:      ctx => ` ${formatNummer(ctx.parsed.x)} zakjes`,
            labelColor: ctx => ({
              borderColor:     bgKleuren[ctx.dataIndex],
              backgroundColor: bgKleuren[ctx.dataIndex],
            }),
          },
          backgroundColor: panelKleur(),
          titleColor:      mutedKleur(),
          bodyColor:       mutedKleur(),
          borderColor:     gridKleur(),
          borderWidth:     1,
        },
      },
      scales: {
        x: {
          beginAtZero:  true,
          grid:         { color: gridKleur() },
          ticks: {
            color:         mutedKleur(),
            callback:      v => formatKort(v),
            precision:     0,
            maxTicksLimit: 6,
          },
          border: { display: false },
        },
        y: {
          grid:   { display: false },
          ticks:  { color: mutedKleur() },
          border: { display: false },
        },
      },
    },
  });
}

/* -------------------------------------------------------
   TODAY LINE CHART
------------------------------------------------------- */

function renderTodayLine(totaalNu) {
  const ctx = document.getElementById("ms-line-chart");
  if (!ctx) return;

  const nu         = new Date();
  const nuMin      = nu.getHours() * 60 + nu.getMinutes();
  const labels     = MS_CONFIG.dagTargets.map(t => t.tijd);
  const targetData = MS_CONFIG.dagTargets.map(t => t.zakjes);

  const actualData = MS_CONFIG.dagTargets.map(t => {
    const tMin = tijdNaarMinuten(t.tijd);
    if (tMin > nuMin) return null;
    if (nuMin === 0)  return 0;
    return Math.round(totaalNu * (tMin / nuMin));
  });

  const tempo = nuMin > 0 ? totaalNu / nuMin : 0;
  const interpolatieData = MS_CONFIG.dagTargets.map(t => {
    const tMin = tijdNaarMinuten(t.tijd);
    if (tMin <= nuMin) return Math.round(totaalNu * (tMin / (nuMin || 1)));
    return Math.round(totaalNu + tempo * (tMin - nuMin));
  });

  const tooltipOpties = {
    backgroundColor: panelKleur(),
    titleColor:      mutedKleur(),
    bodyColor:       mutedKleur(),
    borderColor:     gridKleur(),
    borderWidth:     1,
    callbacks: { label: ctx => ` ${formatNummer(ctx.parsed.y)} zakjes` },
  };

  if (state.charts.todayLine) {
    state.charts.todayLine.data.datasets[0].data = targetData;
    state.charts.todayLine.data.datasets[1].data = actualData;
    state.charts.todayLine.data.datasets[2].data = interpolatieData;
    state.charts.todayLine.update("none");
    return;
  }

  state.charts.todayLine = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label:            "Doel",
          data:             targetData,
          borderColor:      tekstKleur(),
          borderDash:       [7, 4],
          borderWidth:      1.5,
          pointRadius:      0,
          fill:             false,
          tension:          0,
          pointHoverRadius: 0,
        },
        {
          label:                "Werkelijk",
          data:                 actualData,
          borderColor:          ACCENT_HEX,
          borderWidth:          2.5,
          pointRadius:          3,
          pointBackgroundColor: ACCENT_HEX,
          fill:                 false,
          tension:              0,
          spanGaps:             false,
          pointHoverRadius:     5,
        },
        {
          label:            "Voorspelling",
          data:             interpolatieData,
          borderColor:      accentRgba(0.85),
          borderDash:       [5, 5],
          borderWidth:      2,
          pointRadius:      0,
          fill:             false,
          tension:          0,
          spanGaps:         false,
          pointHoverRadius: 0,
        },
      ],
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: mutedKleur(), font: { size: 11 }, boxWidth: 20 },
        },
        tooltip: tooltipOpties,
      },
      scales: {
        y: {
          beginAtZero: true,
          grid:   { color: gridKleur() },
          ticks:  { color: mutedKleur(), callback: v => formatKort(v) },
          border: { display: false },
        },
        x: {
          grid:   { display: false },
          ticks:  { color: mutedKleur(), maxRotation: 45 },
          border: { display: false },
        },
      },
    },
  });
}

/* -------------------------------------------------------
   WEEKVOORTGANG
------------------------------------------------------- */

function renderWeekProgress(weekTotaal, weekDagen) {
  const target     = MS_CONFIG.weekTarget;
  const pct        = Math.min(weekTotaal / target * 100, 200);
  const overTarget = weekTotaal > target;

  const fill = document.getElementById("ms-week-fill");
  if (fill) {
    fill.style.width = `${Math.min(pct, 100)}%`;
    fill.classList.toggle("over-target", overTarget);
  }

  setEl("ms-week-pct",        `${pct.toFixed(1)}%`);
  setEl("ms-week-val",        formatNummer(weekTotaal));
  setEl("ms-week-val-target", formatNummer(target));

  renderWeekDagenChart(weekDagen);
}

function renderWeekDagenChart(weekDagen) {
  const ctx    = document.getElementById("ms-week-dagen-chart");
  if (!ctx) return;

  const dagNamen = ["Ma","Di","Wo","Do","Vr","Za","Zo"];
  const target   = MS_CONFIG.dagTarget;

  const volledigeWeek = dagNamen.map((naam, i) => {
    const dagData = weekDagen.find(d => {
      const dt = new Date(d.datum);
      return (dt.getDay() === 0 ? 6 : dt.getDay() - 1) === i;
    });
    const totaal = dagData
      ? Object.values(dagData.machines).reduce((s, v) => s + v, 0)
      : null;
    return { naam, totaal };
  });

  const labels       = volledigeWeek.map(d => d.naam);
  const data         = volledigeWeek.map(d => d.totaal ?? 0);
    const kleuren = volledigeWeek.map(d =>
    d.totaal === null ? c("--muted-rgb", 0.12)
        : d.totaal >= target ? STATUS_GROEN_HEX : STATUS_ROOD_HEX
    );

    const hoverKleuren = volledigeWeek.map(d =>
    d.totaal === null ? c("--muted-rgb", 0.20)
        : d.totaal >= target ? statusGroenRgba(0.65) : hexRgba(STATUS_ROOD_HEX, 0.65)
    );

  const maxData = Math.max(...data, 0);
    const basis   = Math.max(target, maxData);
    const MAX_X   = Math.ceil(basis * 1.10 / 1000) * 1000; // 10% marge, netjes afgerond

  const targetLijnPlugin = {
    id: "weekDagTargetLijn",
    afterDraw(chart) {
      const { ctx: c2d, scales: { x } } = chart;
      if (!x) return;
      const xPos  = x.getPixelForValue(target);
      const muted = mutedKleur();
      c2d.save();
      c2d.beginPath();
      c2d.setLineDash([6, 4]);
      c2d.strokeStyle = tekstKleur();
      c2d.lineWidth   = 1.5;
      c2d.moveTo(xPos, chart.chartArea.top);
      c2d.lineTo(xPos, chart.chartArea.bottom);
      c2d.stroke();
      c2d.setLineDash([]);
      c2d.fillStyle    = muted;
      c2d.font         = `11px ${Chart.defaults.font.family || "inherit"}`;
      c2d.textAlign    = "center";
      c2d.textBaseline = "top";
      c2d.fillText(formatKort(target), xPos, chart.chartArea.bottom + 4);
      c2d.restore();
    },
  };

  const schaalOpties = {
    x: {
      beginAtZero: true,
      max:    MAX_X,
      grid:   { color: gridKleur() },
      ticks: {
        color:         mutedKleur(),
        callback:      v => (v === target ? null : formatKort(v)),
        maxTicksLimit: 5,
      },
      border: { display: false },
    },
    y: {
      grid:   { display: false },
      ticks: { color: mutedKleur(), autoSkip: false, padding: 8 },
      border: { display: false },
    },
  };

  if (state.charts.weekDagen) {
    state.charts.weekDagen.data.labels                           = labels;
    state.charts.weekDagen.data.datasets[0].data                 = data;
    state.charts.weekDagen.data.datasets[0].backgroundColor      = kleuren;
    state.charts.weekDagen.data.datasets[0].hoverBackgroundColor = hoverKleuren;
    state.charts.weekDagen.options.scales                        = schaalOpties;
    state.charts.weekDagen.update("none");
    return;
  }

  state.charts.weekDagen = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
        datasets: [{
        data:                 data,
        backgroundColor:      kleuren,
        hoverBackgroundColor: hoverKleuren,
        borderRadius:         3,
        borderSkipped:        false,

        /* Meer verticale ruimte tussen Ma–Zo */
        maxBarThickness:    18,   // limiet omhoog
        categoryPercentage: 0.9,  // benut meer van de "row"
        barPercentage:      1.0,  // bar vult de categorie
        }],
    },
    plugins: [targetLijnPlugin],
    options: {
      indexAxis:           "y",
      responsive:          true,
      maintainAspectRatio: false,
      layout: { padding: { top: 6, bottom: 16 } },
      plugins: {
        legend:  { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ctx.parsed.x > 0 ? ` ${formatNummer(ctx.parsed.x)} zakjes` : " Geen data",
          },
          backgroundColor: panelKleur(),
          titleColor:      mutedKleur(),
          bodyColor:       mutedKleur(),
          borderColor:     gridKleur(),
          borderWidth:     1,
        },
      },
      scales: schaalOpties,
    },
  });
}

/* -------------------------------------------------------
   DAGEN SCHERM
------------------------------------------------------- */

function renderDagen() {
  const data = state.data?.[state.dagenBereik] || [];
  renderDagenLine(data);
  renderDagenStacked(data);
  renderDagenMachineBars(data);
}

function renderDagenLine(data) {
  const ctx = document.getElementById("ms-dagen-line");
  if (!ctx) return;

  const labels  = data.map(d => formatDatumLabel(d.datum));
  const totalen = data.map(d => Object.values(d.machines).reduce((s, v) => s + v, 0));

  if (state.charts.dagenLine) {
    state.charts.dagenLine.data.labels           = labels;
    state.charts.dagenLine.data.datasets[0].data = totalen;
    state.charts.dagenLine.data.datasets[1].data = data.map(() => MS_CONFIG.dagTarget);
    state.charts.dagenLine.update("none");
    return;
  }

  state.charts.dagenLine = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label:                "Zakjes",
          data:                 totalen,
          borderColor:          ACCENT_HEX,
          borderWidth:          2.5,
          pointRadius:          4,
          pointBackgroundColor: ACCENT_HEX,
          fill:                 false,
          tension:              0,
          pointHoverRadius:     6,
        },
        targetLijnDataset(data, MS_CONFIG.dagTarget, "Dagdoelstelling"),
      ],
    },
    options: histLineOpties(),
  });
}

function renderDagenStacked(data) {
  const ctx = document.getElementById("ms-dagen-stacked");
  if (!ctx) return;

  const { labels, datasets } = buildStackedDatasets(data, "datum");
  const targetDs             = targetLijnDataset(data, MS_CONFIG.dagTarget, "Dagdoelstelling");

  if (state.charts.dagenStacked) {
    state.charts.dagenStacked.data.labels   = labels;
    state.charts.dagenStacked.data.datasets = [...datasets, targetDs];
    state.charts.dagenStacked.update("none");
    return;
  }

  state.charts.dagenStacked = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [...datasets, targetDs] },
    options: stackedOpties(),
  });
}

function renderDagenMachineBars(data) {
  const ctx = document.getElementById("ms-dagen-machine-bars");
  if (!ctx) return;

  const { machineIds, machineData } = buildMachineTotalen(data);
  const bgKleuren    = machineIds.map(id => machineKleur(id));
  const hoverKleuren = machineIds.map(id => machineHoverKleur(id));

  if (state.charts.dagenMachine) {
    state.charts.dagenMachine.data.labels                            = machineIds;
    state.charts.dagenMachine.data.datasets[0].data                  = machineData;
    state.charts.dagenMachine.data.datasets[0].backgroundColor       = bgKleuren;
    state.charts.dagenMachine.data.datasets[0].hoverBackgroundColor  = hoverKleuren;
    state.charts.dagenMachine.update("none");
    return;
  }

  state.charts.dagenMachine = new Chart(ctx, {
    type: "bar",
    data: {
      labels: machineIds,
      datasets: [{
        label:                "Totaal zakjes",
        data:                 machineData,
        backgroundColor:      bgKleuren,
        hoverBackgroundColor: hoverKleuren,
        borderRadius:         4,
      }],
    },
    options: machineBarOpties(machineIds),
  });
}

/* -------------------------------------------------------
   WEKEN SCHERM
------------------------------------------------------- */

function renderWeken() {
  const data = state.data?.[state.wekenBereik] || [];
  renderWekenLine(data);
  renderWekenStacked(data);
  renderWekenMachineBars(data);
}

function renderWekenLine(data) {
  const ctx = document.getElementById("ms-weken-line");
  if (!ctx) return;

  const labels  = data.map(d => d.week);
  const totalen = data.map(d => Object.values(d.machines).reduce((s, v) => s + v, 0));

  if (state.charts.wekenLine) {
    state.charts.wekenLine.data.labels           = labels;
    state.charts.wekenLine.data.datasets[0].data = totalen;
    state.charts.wekenLine.data.datasets[1].data = data.map(() => MS_CONFIG.weekTarget);
    state.charts.wekenLine.update("none");
    return;
  }

  state.charts.wekenLine = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label:                "Zakjes",
          data:                 totalen,
          borderColor:          ACCENT_HEX,
          borderWidth:          2.5,
          pointRadius:          4,
          pointBackgroundColor: ACCENT_HEX,
          fill:                 false,
          tension:              0,
          pointHoverRadius:     6,
        },
        targetLijnDataset(data, MS_CONFIG.weekTarget, "Weekdoelstelling"),
      ],
    },
    options: histLineOpties(),
  });
}

function renderWekenStacked(data) {
  const ctx = document.getElementById("ms-weken-stacked");
  if (!ctx) return;

  const { labels, datasets } = buildStackedDatasets(data, "week");
  const targetDs             = targetLijnDataset(data, MS_CONFIG.weekTarget, "Weekdoelstelling");

  if (state.charts.wekenStacked) {
    state.charts.wekenStacked.data.labels   = labels;
    state.charts.wekenStacked.data.datasets = [...datasets, targetDs];
    state.charts.wekenStacked.update("none");
    return;
  }

  state.charts.wekenStacked = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [...datasets, targetDs] },
    options: stackedOpties(),
  });
}

function renderWekenMachineBars(data) {
  const ctx = document.getElementById("ms-weken-machine-bars");
  if (!ctx) return;

  const { machineIds, machineData } = buildMachineTotalen(data);
  const bgKleuren    = machineIds.map(id => machineKleur(id));
  const hoverKleuren = machineIds.map(id => machineHoverKleur(id));

  if (state.charts.wekenMachine) {
    state.charts.wekenMachine.data.labels                            = machineIds;
    state.charts.wekenMachine.data.datasets[0].data                  = machineData;
    state.charts.wekenMachine.data.datasets[0].backgroundColor       = bgKleuren;
    state.charts.wekenMachine.data.datasets[0].hoverBackgroundColor  = hoverKleuren;
    state.charts.wekenMachine.update("none");
    return;
  }

  state.charts.wekenMachine = new Chart(ctx, {
    type: "bar",
    data: {
      labels: machineIds,
      datasets: [{
        label:                "Totaal zakjes",
        data:                 machineData,
        backgroundColor:      bgKleuren,
        hoverBackgroundColor: hoverKleuren,
        borderRadius:         4,
      }],
    },
    options: machineBarOpties(machineIds),
  });
}

/* -------------------------------------------------------
   CHART OPTIES HELPERS
------------------------------------------------------- */

function histLineOpties() {
  return {
    responsive:          true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: mutedKleur(), font: { size: 11 }, boxWidth: 20 } },
      tooltip: {
        callbacks: { label: ctx => ` ${formatNummer(ctx.parsed.y)} zakjes` },
        backgroundColor: panelKleur(),
        titleColor:      mutedKleur(),
        bodyColor:       mutedKleur(),
        borderColor:     gridKleur(),
        borderWidth:     1,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        grid:   { color: gridKleur() },
        ticks:  { color: mutedKleur(), callback: v => formatKort(v) },
        border: { display: false },
      },
      x: {
        grid:   { display: false },
        ticks:  { color: mutedKleur(), maxRotation: 45 },
        border: { display: false },
      },
    },
  };
}

function stackedOpties() {
  return {
    responsive:          true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color:    mutedKleur(),
          font:     { size: 11 },
          boxWidth: 14,
          filter:   item => item.text !== "Dagdoelstelling" && item.text !== "Weekdoelstelling",
        },
      },
      tooltip: {
        callbacks: { label: ctx => ` ${ctx.dataset.label}: ${formatNummer(ctx.parsed.y)}` },
        backgroundColor: panelKleur(),
        titleColor:      mutedKleur(),
        bodyColor:       mutedKleur(),
        borderColor:     gridKleur(),
        borderWidth:     1,
      },
    },
    scales: {
      x: {
        stacked: true,
        grid:    { display: false },
        ticks:   { color: mutedKleur(), maxRotation: 45 },
        border:  { display: false },
      },
      y: {
        stacked: true,
        grid:    { color: gridKleur() },
        ticks:   { color: mutedKleur(), callback: v => formatKort(v) },
        border:  { display: false },
      },
    },
  };
}

function machineBarOpties(machineIds = []) {
  return {
    responsive:          true,
    maintainAspectRatio: false,
    plugins: {
      legend:  { display: false },
      tooltip: {
        callbacks: {
          label:      ctx => ` ${formatNummer(ctx.parsed.y)} zakjes`,
          labelColor: ctx => ({
            borderColor:     machineKleur(machineIds[ctx.dataIndex]),
            backgroundColor: machineKleur(machineIds[ctx.dataIndex]),
          }),
        },
        backgroundColor: panelKleur(),
        titleColor:      mutedKleur(),
        bodyColor:       mutedKleur(),
        borderColor:     gridKleur(),
        borderWidth:     1,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid:   { color: gridKleur() },
        ticks:  { color: mutedKleur(), callback: v => formatKort(v) },
        border: { display: false },
      },
      x: {
        grid:   { display: false },
        ticks:  { color: mutedKleur() },
        border: { display: false },
      },
    },
  };
}

function targetLijnDataset(data, targetWaarde, label) {
  return {
    label,
    data:             data.map(() => targetWaarde),
    borderColor:      tekstKleur(),
    borderDash:       [10, 5],
    borderWidth:      1.5,
    pointRadius:      0,
    type:             "line",
    fill:             false,
    order:            0,
    tension:          0,
    pointHoverRadius: 0,
  };
}

/* -------------------------------------------------------
   DATA BUILDERS
------------------------------------------------------- */

function buildStackedDatasets(data, labelKey) {
  const machineSet = new Set();
  data.forEach(d => Object.keys(d.machines).forEach(m => machineSet.add(m)));
  const machineIds = [...machineSet].sort(sortMachineId);
  const labels     = data.map(d => labelKey === "week" ? d.week : formatDatumLabel(d.datum));

  const datasets = machineIds.map(id => ({
    label:                id,
    data:                 data.map(d => d.machines[id] || 0),
    backgroundColor:      machineKleur(id),
    hoverBackgroundColor: machineHoverKleur(id),
    stack:                "machines",
    borderRadius:         2,
    order:                1,
  }));

  return { labels, machineIds, datasets };
}

function buildMachineTotalen(data) {
  const machineSet = new Set();
  data.forEach(d => Object.keys(d.machines).forEach(m => machineSet.add(m)));
  const machineIds  = [...machineSet].sort(sortMachineId);
  const machineData = machineIds.map(id =>
    data.reduce((s, d) => s + (d.machines[id] || 0), 0)
  );
  return { machineIds, machineData };
}

/* -------------------------------------------------------
   FULLSCREEN
------------------------------------------------------- */

function toggleFullscreen() {
  const isFs    = document.body.classList.toggle("ms-fullscreen");
  const overlay = document.getElementById("ms-fullscreen-overlay");
  const view    = document.getElementById("ms-view-vandaag");
  const dash    = document.getElementById("ms-dashboard");
  if (!overlay || !view || !dash) return;

  if (isFs) {
    overlay.appendChild(view);
  } else {
    dash.insertBefore(view, dash.firstChild);
    document.getElementById("ms-fullscreen-exit-bar")?.classList.remove("visible");
  }

  // Rebuild charts zodat Chart.js altijd de nieuwe container-maten pakt
  destroyAllCharts();
  renderAlles();

  // Extra safety resize na layout settle
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      Object.values(state.charts).forEach(ch => ch?.resize?.());
    });
  });
}

/* -------------------------------------------------------
   UTILITIES
------------------------------------------------------- */

function berekenVerwacht(nu) {
  const nuMin  = nu.getHours() * 60 + nu.getMinutes();
  const points = MS_CONFIG.dagTargets;
  for (let i = 0; i < points.length - 1; i++) {
    const t1 = tijdNaarMinuten(points[i].tijd);
    const t2 = tijdNaarMinuten(points[i + 1].tijd);
    if (nuMin >= t1 && nuMin <= t2) {
      const f = (nuMin - t1) / (t2 - t1);
      return Math.round(points[i].zakjes + f * (points[i + 1].zakjes - points[i].zakjes));
    }
  }
  if (nuMin < tijdNaarMinuten(points[0].tijd)) return 0;
  return points[points.length - 1].zakjes;
}

function huidigeWeekDagen(nu) {
  const dag     = nu.getDay();
  const maandag = new Date(nu);
  maandag.setDate(nu.getDate() + (dag === 0 ? -6 : 1 - dag));
  maandag.setHours(0, 0, 0, 0);
  const dagen = [];
  for (let i = 0; i <= 6; i++) {
    const d = new Date(maandag);
    d.setDate(maandag.getDate() + i);
    if (d <= nu) dagen.push(d);
  }
  return dagen;
}

function volledigeWeekDagen(nu) {
  const dag     = nu.getDay();
  const maandag = new Date(nu);
  maandag.setDate(nu.getDate() + (dag === 0 ? -6 : 1 - dag));
  maandag.setHours(0, 0, 0, 0);

  const dagen = [];
  for (let i = 0; i <= 6; i++) {
    const d = new Date(maandag);
    d.setDate(maandag.getDate() + i);
    dagen.push(d);
  }
  return dagen;
}

function datumString(d)     { return d.toISOString().slice(0, 10); }
function tijdNaarMinuten(t) { const [h, m] = t.split(":").map(Number); return h * 60 + m; }

function formatDatumLabel(datumStr) {
  const d     = new Date(datumStr);
  const namen = ["Zo","Ma","Di","Wo","Do","Vr","Za"];
  const dag   = String(d.getDate()).padStart(2, "0");
  const maand = String(d.getMonth() + 1).padStart(2, "0");
  return `${namen[d.getDay()]} ${dag}-${maand}-${d.getFullYear()}`;
}

function formatNummer(n) { return n == null ? "—" : Math.round(n).toLocaleString("nl-NL"); }
function formatKort(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}k`;
  return n;
}

function sortMachineId(a, b) {
  return (parseInt(a.replace(/\D/g, ""), 10) || 0) - (parseInt(b.replace(/\D/g, ""), 10) || 0);
}

function getWeekNumber(d) {
  const utc = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  utc.setUTCDate(utc.getUTCDate() + 4 - (utc.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
  return Math.ceil((((utc - yearStart) / 86400000) + 1) / 7);
}

function setEl(id, tekst) {
  const el = document.getElementById(id);
  if (el) el.textContent = tekst;
}