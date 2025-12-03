// static/js/policies/policies.js
document.addEventListener("DOMContentLoaded", function () {
  
  // === 1. Toggle inline form via + knop ===
  document.querySelectorAll(".js-toggle-form").forEach(function (btn) {
    btn.addEventListener("click", function (event) {
      // Voorkom dat de klik "doorbubbelt" en het item uitklapt
      event.preventDefault();
      event.stopPropagation();

      var targetSelector = btn.getAttribute("data-target");
      if (!targetSelector) return;

      var form = document.querySelector(targetSelector);
      if (!form) return;

      var isHidden = form.classList.toggle("is-hidden");
      btn.setAttribute("aria-expanded", isHidden ? "false" : "true");

      // Focus op het eerste veld als het formulier opent
      if (!isHidden) {
        var firstField = form.querySelector("input, textarea, select");
        if (firstField) firstField.focus();
      }
    });
  });

  // === 2. Inklappen/uitklappen van werkafspraak items ===
  document.querySelectorAll(".news-item").forEach(function (item) {
    var body = item.querySelector(".news-body");
    if (!body) return;

    function toggleItem() {
      var expanded = item.classList.toggle("news-item--expanded");
      body.classList.toggle("is-hidden", !expanded);
    }

    item.addEventListener("click", function (event) {
      // Als we op interactieve elementen klikken, niet togglen
      if (event.target.closest(".js-toggle-form")) return;
      if (event.target.closest(".news-delete-form")) return;
      if (event.target.closest(".news-body")) return; // Niet inklappen als je in de PDF/tekst klikt
      if (event.target.closest("form")) return;       // Niet inklappen als je in het upload formulier klikt

      toggleItem();
    });

    // Toetsenbord toegankelijkheid (Enter/Spatie)
    item.setAttribute("tabindex", "0");
    item.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        // Alleen togglen als de focus op de item-wrapper zelf ligt
        if(event.target === item) { 
            event.preventDefault(); 
            toggleItem(); 
        }
      }
    });
  });

  // === 3. Bevestiging voor verwijderen ===
  document.querySelectorAll(".news-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var title =
        form
          .closest(".news-item")
          ?.querySelector(".birthday-name")
          ?.innerText
          ?.trim() || "";

      var message =
        "Weet je zeker dat je de werkafspraak " +
        (title ? '"' + title + '"' : "deze werkafspraak") +
        " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!";

      if (!confirm(message)) {
        event.preventDefault();
      }
    });
  });

  // === 4. Filename tonen naast de upload-knop ===
  // We luisteren op het hele document naar een 'change' event.
  // Dit werkt altijd, ongeacht wat de 'auto_id' precies is.
  document.addEventListener("change", function (event) {
    
    // Check: Is het element dat veranderde een file input?
    if (event.target && event.target.type === "file") {
      var fileInput = event.target;
      
      // Zoek de 'wrapper' om dit specifieke veld heen
      var wrapper = fileInput.closest(".news-file-wrapper");
      
      // Als we de wrapper vinden, zoek daarbinnen naar de span waar de naam moet komen
      if (wrapper) {
        var fileNameSpan = wrapper.querySelector(".news-file-name");
        
        if (fileNameSpan) {
          // Pak de bestandsnaam of maak leeg als er geen bestand is
          var name = fileInput.files && fileInput.files[0] 
                     ? fileInput.files[0].name 
                     : "";
          
          fileNameSpan.textContent = name;
        }
      }
    }
  });

});