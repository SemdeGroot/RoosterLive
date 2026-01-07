// static/js/onboarding_formulieren/formulieren.js
document.addEventListener("DOMContentLoaded", function () {

  // === Toggle forms ===
  document.querySelectorAll(".js-toggle-form").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetSelector = btn.getAttribute("data-target");
      if (!targetSelector) return;

      var form = document.querySelector(targetSelector);
      if (!form) return;

      var isHidden = form.classList.toggle("is-hidden");
      btn.setAttribute("aria-expanded", isHidden ? "false" : "true");

      if (!isHidden) {
        var firstField = form.querySelector("input, textarea, select");
        if (firstField) firstField.focus();
      }
    });
  });

  // === Annuleren ===
  document.querySelectorAll(".js-cancel-form").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetSelector = btn.getAttribute("data-target");
      if (!targetSelector) return;

      var form = document.querySelector(targetSelector);
      if (!form) return;

      form.classList.add("is-hidden");

      var toggleBtn = document.querySelector('.js-toggle-form[data-target="' + targetSelector + '"]');
      if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "false");
    });
  });

  // === Submit lock / timeout (Alleen voor formulieren met data-lock-submit="1") ===
  // (Exact hetzelfde patroon als in agenda.js)
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
  // Zorg dat je delete-forms GEEN data-lock-submit="1" hebben (net als agenda)
  document.querySelectorAll(".agenda-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      const title =
        form
          .closest(".birthday-item")
          ?.querySelector(".birthday-name")
          ?.innerText
          ?.trim() || "";

      const message =
        "Weet je zeker dat je het formulier " +
        (title ? `"${title}"` : "dit formulier") +
        " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!";

      if (!confirm(message)) {
        event.preventDefault();
      }
    });
  });

});