// static/js/base/confirm_delete.js
document.addEventListener("DOMContentLoaded", function () {
  
  // Zoek alle formulieren met de class 'delete-confirm-form'
  document.querySelectorAll(".delete-confirm-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      // Haal de naam op uit het data-attribuut dat we in de HTML hebben gezet
      const itemName = form.getAttribute("data-name") || "dit item";

      const message = 
        "Weet je zeker dat je dit item wilt verwijderen?\n\n" +
        "⚠️ Deze actie kan niet ongedaan worden gemaakt!";

      if (!confirm(message)) {
        event.preventDefault(); // Stop het versturen van het formulier
      }
    });
  });
});