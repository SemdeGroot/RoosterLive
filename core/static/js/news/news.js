// static/js/news/news.js
document.addEventListener("DOMContentLoaded", function () {
  // === Toggle inline form via + knop ===
  document.querySelectorAll(".js-toggle-form").forEach(function (btn) {
    btn.addEventListener("click", function (event) {
      // Voorkom dat de klik "doorbubbelt" naar .news-item
      event.preventDefault();
      event.stopPropagation();

      var targetSelector = btn.getAttribute("data-target");
      if (!targetSelector) return;

      var form = document.querySelector(targetSelector);
      if (!form) return;

      var isHidden = form.classList.toggle("is-hidden");
      btn.setAttribute("aria-expanded", isHidden ? "false" : "true");

      if (!isHidden) {
        var firstField = form.querySelector("input, textarea");
        if (firstField) firstField.focus();
      }
    });
  });

  // === Inklappen/uitklappen van nieuwsitems ===
  // De hele .news-item (li) is klikbaar,
  // behalve:
  //   - het delete-form (kruisje)
  //   - de uitgeklapte .news-body (zodat je in de tekst/afbeeldingen kunt klikken zonder te togglen)
  //   - de + toevoeg-knop (.js-toggle-form)
  document.querySelectorAll(".news-item").forEach(function (item) {
    var body = item.querySelector(".news-body");
    if (!body) return;

    function toggleItem() {
      var expanded = item.classList.toggle("news-item--expanded");
      body.classList.toggle("is-hidden", !expanded);
    }

    item.addEventListener("click", function (event) {
      // klik op + toevoeg-knop → NIET togglen
      if (event.target.closest(".js-toggle-form")) return;

      // klik op delete-form → NIET togglen
      if (event.target.closest(".news-delete-form")) return;

      // klik in de body (uitgeklapt deel) → NIET togglen
      if (event.target.closest(".news-body")) return;

      toggleItem();
    });

    // Toetsenbord: Enter/Spatie op de li
    item.setAttribute("tabindex", "0");
    item.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleItem();
      }
    });
  });

  // === Bevestiging voor verwijderen van nieuwsitems ===
  document.querySelectorAll(".news-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var title =
        form
          .closest(".news-item")
          ?.querySelector(".birthday-name")
          ?.innerText
          ?.trim() || "";

      var message =
        "Weet je zeker dat je het nieuwsbericht " +
        (title ? "\"" + title + "\"" : "dit nieuwsbericht") +
        " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!";

      if (!confirm(message)) {
        event.preventDefault();
      }
    });
  });

  // === Filename tonen naast de upload-knop ===
  var fileInput = document.querySelector('input[type="file"][name="file"]');
  var fileNameSpan = document.getElementById("news-file-name");

  if (fileInput && fileNameSpan) {
    fileInput.addEventListener("change", function () {
      var name =
        fileInput.files && fileInput.files[0]
          ? fileInput.files[0].name
          : "";
      fileNameSpan.textContent = name;
    });
  }
});