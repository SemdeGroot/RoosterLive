// static/js/news/news.js
document.addEventListener("DOMContentLoaded", function () {
  // === Toggle inline form via + / edit knop (zelfde als agenda) ===
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

  // === Cancel buttons (add/edit) ===
  document.querySelectorAll(".js-cancel-form").forEach(function (btn) {
    btn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();

      var targetSelector = btn.getAttribute("data-target");
      if (!targetSelector) return;

      var form = document.querySelector(targetSelector);
      if (!form) return;

      form.classList.add("is-hidden");

      var toggleBtn = document.querySelector(
        '.js-toggle-form[data-target="' + targetSelector + '"]'
      );
      if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "false");
    });
  });

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

  // === Lazy media loader ===
  async function loadMediaIfNeeded(liEl) {
    var host = liEl.querySelector("[data-media-host]");
    if (!host) return;

    if (host.dataset.loaded === "1") return;

    var itemId = host.getAttribute("data-item-id");
    if (!itemId) return;

    try {
      var resp = await fetch("/nieuws/media/" + itemId + "/", {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!resp.ok) return;

      var data = await resp.json();
      if (!data || !data.has_file) {
        host.dataset.loaded = "1";
        return;
      }

      if (data.type === "image" && data.url) {
        var img = document.createElement("img");
        img.src = data.url;
        img.alt = "Nieuws afbeelding";
        host.appendChild(img);
      }

      if (data.type === "pdf" && Array.isArray(data.urls)) {
        data.urls.forEach(function (url) {
          var img = document.createElement("img");
          img.src = url;
          img.alt = "Nieuws PDF pagina";
          host.appendChild(img);
        });
      }

      host.dataset.loaded = "1";
    } catch (err) {
      // silent fail
    }
  }

  // === Inklappen/uitklappen van nieuwsitems ===
  // De hele .news-item (li) is klikbaar,
  // behalve:
  //   - .js-toggle-form (toevoegen/edit buttons)
  //   - delete-form
  //   - alles met data-stop-toggle
  //   - de uitgeklapte .news-body (zodat je in de tekst/afbeeldingen kunt klikken zonder te togglen)
  document.querySelectorAll(".news-item").forEach(function (item) {
    var body = item.querySelector(".news-body");
    if (!body) return;

    function toggleItem() {
      var expanded = item.classList.toggle("news-item--expanded");
      body.classList.toggle("is-hidden", !expanded);

      // bij openen: lazy load media (pas 1x)
      if (expanded) {
        loadMediaIfNeeded(item);
      }
    }

    item.addEventListener("click", function (event) {
      // klik op toggle/edit/add knoppen → NIET togglen
      if (event.target.closest(".js-toggle-form")) return;

      // klik op delete-form → NIET togglen
      if (event.target.closest(".news-delete-form")) return;

      // klik in de body (uitgeklapt deel) → NIET togglen
      if (event.target.closest(".news-body")) return;

      // klik op elementen die expliciet stop-toggle zijn → NIET togglen
      if (event.target.closest("[data-stop-toggle]")) return;

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

  // === Filename tonen naast de upload-knop (add + alle edit forms) ===
  // Werkt met spans: <span class="news-file-name" data-file-name></span>
  document.querySelectorAll("form").forEach(function (form) {
    var fileInput = form.querySelector('input[type="file"]');
    var fileNameSpan = form.querySelector("[data-file-name]");

    if (!fileInput || !fileNameSpan) return;

    fileInput.addEventListener("change", function () {
      var name =
        fileInput.files && fileInput.files[0]
          ? fileInput.files[0].name
          : "";
      fileNameSpan.textContent = name;
    });
  });
});