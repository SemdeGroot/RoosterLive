document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("set-password-form");
  if (!form) return;

  const minLen = parseInt(form.getAttribute("data-min-length") || "8", 10);
  const pw1 = document.getElementById("id_new_password1");
  const pw2 = document.getElementById("id_new_password2");

  const barFill = document.getElementById("pw-bar-fill");
  const badge = document.getElementById("pw-badge");
  const badgeText = document.getElementById("pw-strength-text");
  const hints = document.getElementById("pw-hints");
  const minSpan = document.getElementById("pw-min");
  if (minSpan) minSpan.textContent = String(minLen);

  // Mini-blacklist (client-side UX); server blijft leidend
  const COMMON = new Set(["password","123456","12345678","qwerty","letmein","welcome","iloveyou","111111","abc123","admin","123456789","passw0rd"]);

  // Helpers
  const hasLower = s => /[a-z]/.test(s);
  const hasUpper = s => /[A-Z]/.test(s);
  const hasDigit = s => /\d/.test(s);
  const hasSymbol = s => /[^A-Za-z0-9]/.test(s);
  const isNumericOnly = s => !!s && /^[0-9]+$/.test(s);

  function setHint(key, ok) {
    if (!hints) return;
    const li = hints.querySelector(`li[data-check="${key}"]`);
    if (!li) return;
    li.classList.toggle("ok", !!ok);
  }

  function scorePassword(s) {
    if (!s) return 0;
    let score = 0;
    if (s.length >= minLen) score++;
    const classes = [hasLower(s), hasUpper(s), hasDigit(s), hasSymbol(s)].filter(Boolean).length;
    if (classes >= 3) score++;
    if (!isNumericOnly(s)) score++;
    if (!COMMON.has(s.toLowerCase())) score++;
    // 0..4
    return Math.max(0, Math.min(4, score));
  }

  function labelForScore(n) {
    switch (n) {
      case 1: return "Zwak";
      case 2: return "Matig";
      case 3: return "Redelijk";
      case 4: return "Sterk";
      default: return "—";
    }
  }

  function classForScore(n) {
    switch (n) {
      case 1: return "weak";
      case 2: return "fair";
      case 3: return "good";
      case 4: return "strong";
      default: return "";
    }
  }

  function widthForScore(n) {
    switch (n) {
      case 1: return "25%";
      case 2: return "50%";
      case 3: return "75%";
      case 4: return "100%";
      default: return "0%";
    }
  }

  function updatePw1() {
    const v = pw1.value || "";

    // Hints toggles (in tooltip)
    setHint("length", v.length >= minLen);
    setHint("not-numeric", !!v && !isNumericOnly(v));
    setHint("not-common", !!v && !COMMON.has(v.toLowerCase()));
    const variety = [hasLower(v), hasUpper(v), hasDigit(v), hasSymbol(v)].filter(Boolean).length >= 3;
    setHint("variety", variety);

    // Score → badge + bar
    const s = scorePassword(v);
    const cls = classForScore(s);
    const w = widthForScore(s);

    if (barFill) {
      barFill.style.width = w;
      barFill.classList.remove("weak","fair","good","strong");
      if (cls) barFill.classList.add(cls);
    }
    if (badge && badgeText) {
      badge.classList.remove("weak","fair","good","strong");
      if (cls) badge.classList.add(cls);
      badgeText.textContent = "Sterkte: " + labelForScore(s);
    }
  }

  function updateMatch() {
    // we houden ‘match’-tekst buiten; jij toont server-side flash bij mismatch
    // Wil je toch live tekst? Uncomment onderstaande regels:
    /*
    const a = pw1.value || "", b = pw2.value || "";
    const el = document.getElementById("pw-match");
    if (!el) return;
    if (!b) { el.textContent = ""; el.classList.remove("ok"); return; }
    if (a === b) { el.textContent = "Wachtwoorden komen overeen."; el.classList.add("ok"); }
    else { el.textContent = "Wachtwoorden komen niet overeen."; el.classList.remove("ok"); }
    */
  }

  pw1.addEventListener("input", () => { updatePw1(); updateMatch(); });
  pw2.addEventListener("input", () => { updateMatch(); });

  // init
  updatePw1();
});

document.addEventListener("DOMContentLoaded", () => {
  // 1) Tooltip gedrag: desktop(hover) vs mobile(click)
  const info = document.querySelector(".pw-info");
  if (info) {
    const isMobile = window.matchMedia("(hover: none) and (pointer: coarse)").matches;

    // Accessibility
    info.setAttribute("role", "button");
    info.setAttribute("aria-expanded", "false");

    function setOpen(open) {
      if (isMobile) {
        info.classList.toggle("open", open);      // mobile toont via .open (CSS)
      }
      info.setAttribute("aria-expanded", open ? "true" : "false");
    }

    if (isMobile) {
      // Alleen mobile: click = toggle; click buiten = dicht; ESC = dicht
      info.addEventListener("click", (e) => {
        if (e.target.closest(".pw-tooltip")) return; // klikken in tooltip niet togglen
        e.stopPropagation();
        setOpen(!info.classList.contains("open"));
      });
      document.addEventListener("click", (e) => {
        if (!info.contains(e.target)) setOpen(false);
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") setOpen(false);
      });
    } else {
      // Desktop: click doet niets, alleen hover/focus via CSS
      info.addEventListener("click", (e) => e.preventDefault());
    }
  }

  // 2) Oog-toggle per veld (werkt onafhankelijk)
  // Voeg in je template bij elk wachtwoordveld een button .pw-toggle met data-target="#id_new_password1" / "#id_new_password2"
  document.querySelectorAll(".pw-toggle[data-target]").forEach(btn => {
    const targetSel = btn.getAttribute("data-target");
    const input = document.querySelector(targetSel);
    if (!input) return;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const toType = input.type === "password" ? "text" : "password";
      input.type = toType;
      // optioneel: toggle icoon van het oogje
      btn.classList.toggle("shown", toType === "text");
      // cursor/focus blijft waar hij is
      input.focus({ preventScroll: true });
      // plaats caret aan het eind
      const v = input.value; input.value = ""; input.value = v;
    });
  });

  // 3) Live match melding (blijft bestaan)
  const pw1 = document.getElementById("id_new_password1");
  const pw2 = document.getElementById("id_new_password2");
  const matchEl = document.getElementById("pw-match");
  function updateMatch() {
    if (!pw1 || !pw2 || !matchEl) return;
    const a = pw1.value || "", b = pw2.value || "";
    matchEl.classList.remove("ok","bad");
    if (!b) { matchEl.textContent = ""; return; }
    if (a === b) {
      matchEl.textContent = "Wachtwoorden komen overeen.";
      matchEl.classList.add("ok");
    } else {
      matchEl.textContent = "Wachtwoorden komen niet overeen.";
      matchEl.classList.add("bad");
    }
  }
  if (pw1 && pw2 && matchEl) {
    pw1.addEventListener("input", updateMatch);
    pw2.addEventListener("input", updateMatch);
    updateMatch();
  }
});