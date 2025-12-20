// static/js/agenda/agenda.js
document.addEventListener("DOMContentLoaded", function () {
  // === Submit lock / timeout (hufter-proof) ===
  // - voorkomt dubbel submitten
  // - disable submit buttons
  // - fallback: na 10s unlocken als page niet redirect
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
        // Alleen unlocken als user nog op dezelfde pagina zit
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

  // === Bevestiging voor verwijderen van agenda-items ===
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
        // unlock weer, anders blijft knop disabled na annuleren
        form.dataset.submitted = "0";
        form.querySelectorAll("[data-submit-btn]").forEach(function (b) {
          b.disabled = false;
          b.removeAttribute("aria-disabled");
        });

        event.preventDefault();
      }
    });
  });
});