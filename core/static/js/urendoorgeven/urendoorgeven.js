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
    // update elke 30 sec is genoeg (dagen/uren/minuten)
    setInterval(tick, 30000);
  }

  function normalizeOneDecimalInput(input) {
    // Sta comma toe
    let v = input.value.replace(",", ".").trim();
    if (v === "") return;

    // Alleen digits + 1 punt
    v = v.replace(/[^\d.]/g, "");
    const parts = v.split(".");
    if (parts.length > 2) {
      v = parts[0] + "." + parts.slice(1).join("");
    }

    // max 1 decimaal
    if (v.includes(".")) {
      const [a, b] = v.split(".");
      v = a + "." + (b || "").slice(0, 1);
    }

    input.value = v;
  }

  function setupDecimalInputs() {
    const inputs = document.querySelectorAll(".uren-form input[type='number'], .uren-form input.admin-input");
    inputs.forEach((inp) => {
      inp.addEventListener("input", () => normalizeOneDecimalInput(inp));
      inp.addEventListener("blur", () => normalizeOneDecimalInput(inp));
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
