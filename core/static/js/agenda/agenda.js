// static/js/agenda/agenda.js
document.addEventListener("DOMContentLoaded", function () {
  
  // === Submit lock / timeout (Alleen voor formulieren met data-lock-submit="1") ===
  document.querySelectorAll('form[data-lock-submit="1"]').forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (form.dataset.submitted === "1") {
        event.preventDefault();
        return false;
      }
      form.dataset.submitted = "1";

      var btns = form.querySelectorAll("[data-submit-btn]");
      btns.forEach(function (b) {
        b.disabled = true;
        b.setAttribute("aria-disabled", "true");
      });

      setTimeout(function () {
        if (document.body.contains(form)) {
          btns.forEach(function (b) {
            b.disabled = false;
            b.removeAttribute("aria-disabled");
          });
          form.dataset.submitted = "0";
        }
      }, 10000);
    });
  });

  // === Bevestiging voor verwijderen (Zonder lock-logica) ===
  document.querySelectorAll(".agenda-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      const title =
        form
          .closest(".birthday-item")
          ?.querySelector(".birthday-name")
          ?.innerText
          ?.trim() || "";

      const message =
        "Weet je zeker dat je het agendapunt " +
        (title ? `"${title}"` : "dit agendapunt") +
        " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!";

      if (!confirm(message)) {
        event.preventDefault(); // Annuleert alleen de submit
      }
    });
  });
});