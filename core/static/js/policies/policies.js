// static/js/policies/policies.js
document.addEventListener("DOMContentLoaded", function () {
  // === Toggle inline form via Toevoegen / edit knop ===
  document.querySelectorAll(".js-toggle-form").forEach(function (btn) {
    btn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();

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

  // === Submit lock / timeout (alleen forms met data-lock-submit="1") ===
  // Belangrijk: delete-forms hebben dit attribuut niet, dus blijven werken.
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
    function showLoading(host, text) {
      // voorkom dubbele loaders
      if (host.querySelector("[data-loader]")) return;

      var loader = document.createElement("div");
      loader.setAttribute("data-loader", "1");
      loader.className = "media-loader";
      loader.textContent = text || "Afbeelding laden...";
      host.appendChild(loader);
    }

    function hideLoading(host) {
      var loader = host.querySelector("[data-loader]");
      if (loader) loader.remove();
    }

    function showError(host, text) {
      // voorkom dubbele errors
      if (host.querySelector("[data-media-error]")) return;

      var err = document.createElement("div");
      err.setAttribute("data-media-error", "1");
      err.className = "media-error";
      err.textContent = text || "Kon media niet laden.";
      host.appendChild(err);
    }

    function waitForImage(img) {
      return new Promise(function (resolve, reject) {
        img.addEventListener("load", resolve, { once: true });
        img.addEventListener("error", reject, { once: true });
      });
    }

  // === Lazy media loader (zoals news, maar endpoint /werkafspraken/media/<id>/) ===
  async function loadMediaIfNeeded(liEl) {
    var host = liEl.querySelector("[data-media-host]");
    if (!host) return;
    if (host.dataset.loaded === "1") return;

    var itemId = host.getAttribute("data-item-id");
    if (!itemId) return;

    showLoading(host, "Afbeelding laden...");

    try {
      var resp = await fetch("/werkafspraken/media/" + itemId + "/", {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!resp.ok) {
        hideLoading(host);
        showError(host, "Kon media niet laden.");
        return;
      }

      var data = await resp.json();

      if (!data || !data.has_file) {
        hideLoading(host);
        host.dataset.loaded = "1";
        return;
      }

      var waits = [];

      if (data.type === "image" && data.url) {
        var img = document.createElement("img");
        img.src = data.url;
        img.alt = "Werkafspraak afbeelding";
        host.appendChild(img);
        waits.push(waitForImage(img));
      }

      if (data.type === "pdf" && Array.isArray(data.urls)) {
        data.urls.forEach(function (url) {
          var img = document.createElement("img");
          img.src = url;
          img.alt = "Werkafspraak PDF pagina";
          host.appendChild(img);
          waits.push(waitForImage(img));
        });
      }

      if (waits.length) {
        await Promise.allSettled(waits);
      }

      hideLoading(host);
      host.dataset.loaded = "1";
    } catch (err) {
      hideLoading(host);
      showError(host, "Kon media niet laden.");
    }
  }

  // === Inklappen/uitklappen van items ===
  document.querySelectorAll(".policy-item").forEach(function (item) {
    var body = item.querySelector(".news-body");
    if (!body) return;

    function toggleItem() {
      var expanded = item.classList.toggle("news-item--expanded");
      body.classList.toggle("is-hidden", !expanded);

      if (expanded) {
        loadMediaIfNeeded(item);
      }
    }

    item.addEventListener("click", function (event) {
      if (event.target.closest(".js-toggle-form")) return;
      if (event.target.closest(".policy-delete-form")) return;
      if (event.target.closest(".news-body")) return;
      if (event.target.closest("[data-stop-toggle]")) return;

      toggleItem();
    });

    item.setAttribute("tabindex", "0");
    item.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleItem();
      }
    });
  });

  // === Bevestiging voor verwijderen ===
  document.querySelectorAll(".policy-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var title =
        form
          .closest(".policy-item")
          ?.querySelector(".birthday-name")
          ?.innerText
          ?.trim() || "";

      var message =
        "Weet je zeker dat je de werkafspraak " +
        (title ? "\"" + title + "\"" : "deze werkafspraak") +
        " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!";

      if (!confirm(message)) {
        event.preventDefault();
      }
    });
  });

  // === Filename tonen (zelfde als news) ===
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
