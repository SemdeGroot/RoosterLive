// static/js/agenda/agenda.js

document.addEventListener("DOMContentLoaded", function () {
  // Bevestiging voor verwijderen van agenda-items
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
        event.preventDefault(); // Stop de submit
      }
    });
  });
});