(function () {
  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function formatCountdown(ms) {
    if (ms <= 0) return "0 dagen 00:00";

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
    const passed = bar.getAttribute("data-deadline-passed") === "1";

    if (!iso) {
      timerEl.textContent = "—";
      return;
    }

    const deadline = new Date(iso);
    if (Number.isNaN(deadline.getTime())) {
      timerEl.textContent = "—";
      return;
    }

    if (passed) {
      timerEl.textContent = "Deadline verstreken";
      return;
    }

    const tick = () => {
      const now = new Date();
      const ms = deadline.getTime() - now.getTime();
      timerEl.textContent = formatCountdown(ms);
    };

    tick();
    setInterval(tick, 30000);
  }

  // Tijdens typen: laat digits, comma en punt toe (maar verder niks)
  function allowDecimalTyping(input) {
    let v = input.value;

    // alleen digits + , .
    v = v.replace(/[^\d,\.]/g, "");

    // maximaal 1 scheidingsteken (eerste van , of .)
    const firstSepIndex = v.search(/[,.]/);
    if (firstSepIndex !== -1) {
      const before = v.slice(0, firstSepIndex + 1);
      const after = v.slice(firstSepIndex + 1).replace(/[,.]/g, "");
      v = before + after;
    }

    // max 1 decimaal na scheidingsteken (als aanwezig)
    const parts = v.split(/[,.]/);
    if (parts.length === 2) {
      v = parts[0] + (v.includes(",") ? "," : ".") + parts[1].slice(0, 1);
    }

    input.value = v;
  }

  // Bij blur/submit: normaliseer naar punt en 1 decimaal
  function normalizeOneDecimal(input) {
    let v = (input.value || "").trim();
    if (v === "") return;

    v = v.replace(",", ".");         // Django-friendly
    v = v.replace(/[^\d.]/g, "");    // safety

    const parts = v.split(".");
    if (parts.length > 2) {
      v = parts[0] + "." + parts.slice(1).join("");
    }

    if (v.includes(".")) {
      const [a, b] = v.split(".");
      v = a + "." + (b || "").slice(0, 1);
    }

    input.value = v;
  }

  function setupDecimalInputs() {
    const form = document.querySelector(".uren-form");
    if (!form) return;

    // Pak alleen de 2 uur-velden (class admin-input in jouw form)
    const inputs = form.querySelectorAll("input.admin-input");

    inputs.forEach((inp) => {
      inp.addEventListener("input", () => allowDecimalTyping(inp));
      inp.addEventListener("blur", () => normalizeOneDecimal(inp));
    });

    // Extra: bij submit altijd normaliseren (belangrijk voor Django DecimalField)
    form.addEventListener("submit", () => {
      inputs.forEach((inp) => normalizeOneDecimal(inp));
    });
  }

  function setupToeslagEdit() {
    const editBtn = document.getElementById("toeslagEditBtn");
    const form = document.getElementById("toeslagForm");
    const cancelBtn = document.getElementById("toeslagCancelBtn");

    if (!editBtn || !form) return;

    editBtn.addEventListener("click", () => {
      form.style.display = "block";
      editBtn.style.display = "none";
      const input = form.querySelector("input");
      if (input) input.focus();
    });

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        form.style.display = "none";
        editBtn.style.display = "inline-flex";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupCountdown();
    setupDecimalInputs();
    setupToeslagEdit();
  });
})();