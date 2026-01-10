(function () {
  function $(id) { return document.getElementById(id); }

  // ===== NOTIF UI =====
  function syncChildBlocks() {
    document.querySelectorAll("[data-child-of]").forEach((block) => {
      const parentId = block.getAttribute("data-child-of");
      const parent = document.getElementById(parentId);
      if (!parent) return;
      block.classList.toggle("is-disabled", !parent.checked);
    });
  }

  document.addEventListener("change", (e) => {
    const t = e.target;
    if (!t) return;
    if (t.id === "id_push_enabled" || t.id === "id_email_enabled") {
      syncChildBlocks();
    }
  });
  document.addEventListener("DOMContentLoaded", syncChildBlocks);

  // ===== FLASH =====
  function showFlash(level, text) {
    const container = document.querySelector(".content") || document.body;
    if (!container) return;

    const div = document.createElement("div");
    div.className = "flash";

    if (level === "success") div.classList.add("flash-success");
    else if (level === "warning") div.classList.add("flash-info");
    else div.classList.add("flash-error");

    div.textContent = text;
    container.prepend(div);

    window.setTimeout(() => div.remove(), 5600);
  }

  function getCSRFToken() {
    const el = document.querySelector("input[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function toBlobAsync(canvas, type, quality) {
    return new Promise((resolve) => {
      canvas.toBlob((b) => resolve(b), type, quality);
    });
  }

  function waitFor(fn, timeoutMs = 4000) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      (function tick() {
        let ok = false;
        try { ok = !!fn(); } catch (_) { ok = false; }
        if (ok) return resolve(true);
        if (Date.now() - start > timeoutMs) return reject(new Error("timeout"));
        setTimeout(tick, 30);
      })();
    });
  }

  // ===== AVATAR CROP + UPLOAD =====
  const avatarInput = $("avatarInput");
  const avatarFilename = $("avatarFilename");
  const removeAvatarBtn = $("removeAvatarBtn");
  const cropModal = $("cropModal");
  const cropImage = $("cropImage");
  const closeCropModal = $("closeCropModal");
  const cancelCroppedBtn = $("cancelCroppedBtn");
  const saveCroppedBtn = $("saveCroppedBtn");
  const avatarPreview = $("avatarPreview");

  let cropper = null;
  let uploading = false;
  let cropperReady = false;

  function setSaveState(enabled, label) {
    if (!saveCroppedBtn) return;
    saveCroppedBtn.disabled = !enabled;
    if (label) saveCroppedBtn.textContent = label;
  }

  function openModal() {
    if (!cropModal) return;
    cropModal.style.display = "flex";
  }

  function destroyCropper() {
    cropperReady = false;
    if (cropper) {
      try { cropper.destroy(); } catch (_) {}
      cropper = null;
    }
  }

  function resetFileInput() {
    if (!avatarInput) return;
    avatarInput.value = "";
    if (avatarFilename) avatarFilename.textContent = "";
  }

  function closeModal({ resetFile = false } = {}) {
    if (cropModal) cropModal.style.display = "none";
    document.body.style.overflow = ""; // Herstel scroll
    destroyCropper();
    if (resetFile) resetFileInput();
    setSaveState(true, "Opslaan");
  }

  async function startCropperFromFile(file) {
    if (!file || !cropImage) return;

    setSaveState(false, "Laden…");
    destroyCropper();
    
    if (avatarFilename) avatarFilename.textContent = file.name || "";

    // 1. Toon de modal direct (nodig voor berekening)
    cropModal.style.display = "flex";
    // Voorkom scrollen van de achtergrond (body)
    document.body.style.overflow = "hidden";

    // 2. Wacht op Cropper library
    try {
      await waitFor(() => typeof window.Cropper === "function", 5000);
    } catch (_) {
      showFlash("error", "Fout: Cropper library niet geladen.");
      closeModal({ resetFile: true });
      return;
    }

    const url = URL.createObjectURL(file);

    // 3. Gebruik een Image object om te pre-loaden (Safari stabieler)
    const tempImg = new Image();
    tempImg.onload = () => {
      cropImage.src = url;

      // Forceer layout frame
      requestAnimationFrame(() => {
        setTimeout(() => {
          try {
            cropper = new window.Cropper(cropImage, {
              aspectRatio: 1,
              viewMode: 1,
              dragMode: 'move',
              autoCropArea: 1,
              checkOrientation: true, // Cruciaal voor iPhone foto's!
              background: false,
              responsive: true,
              ready() {
                cropperReady = true;
                setSaveState(true, "Opslaan");
              }
            });
          } catch (e) {
            console.error(e);
            showFlash("error", "Cropper kon niet starten.");
          }
        }, 100);
      });
    };
    tempImg.src = url;
  }
  // Event Listeners voor de Input en Modal buttons
  if (avatarInput) {
    avatarInput.addEventListener("change", () => {
      const file = avatarInput.files && avatarInput.files[0] ? avatarInput.files[0] : null;
      if (!file) return;
      startCropperFromFile(file);
    });
  }

  if (closeCropModal) closeCropModal.addEventListener("click", () => closeModal({ resetFile: true }));
  if (cancelCroppedBtn) cancelCroppedBtn.addEventListener("click", () => closeModal({ resetFile: true }));

  if (saveCroppedBtn) {
    saveCroppedBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      if (uploading) return;

      if (!cropper || !cropperReady) {
        showFlash("error", "De cropper is nog niet klaar.");
        return;
      }

      let canvas = null;
      try {
        canvas = cropper.getCroppedCanvas({ width: 512, height: 512 });
      } catch (_) {
        canvas = null;
      }

      if (!canvas) {
        showFlash("error", "Kon uitsnede niet maken. Controleer of de foto niet te groot is.");
        return;
      }

      uploading = true;
      setSaveState(false, "Bezig…");

      try {
        let blob = await toBlobAsync(canvas, "image/webp", 0.90);
        let filename = "avatar.webp";

        if (!blob) {
          blob = await toBlobAsync(canvas, "image/jpeg", 0.92);
          filename = "avatar.jpg";
        }
        
        if (!blob) throw new Error("Kon geen afbeelding maken.");

        const fd = new FormData();
          fd.append("avatar", blob, filename);

          const res = await fetch("/profiel/avatar/upload/", {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            body: fd,
          });

          // Probeer ALTIJD de JSON te parsen, ook bij status 400/500
          const data = await res.json().catch(() => ({}));

          if (!res.ok) {
            // Check of de server een specifieke flash melding heeft gestuurd (zoals Rekognition)
            if (data.flash && data.flash.text) {
              showFlash(data.flash.level || "error", data.flash.text);
            } else {
              showFlash("error", data.error || "Er ging iets mis bij het uploaden.");
            }
            // BELANGRIJK: stop hier, want res.ok is false
            uploading = false;
            setSaveState(true, "Opslaan");
            return; 
          }

          // Succes geval
          if (avatarPreview && data.avatar_url) avatarPreview.src = data.avatar_url;
          showFlash("success", "Profielfoto opgeslagen.");
          closeModal({ resetFile: true });

        } catch (err) {
          console.error(err);
          showFlash("error", "Netwerkfout of server onbereikbaar.");
        } finally {
          uploading = false;
          setSaveState(true, "Opslaan");
        }
    });
  }

  if (removeAvatarBtn) {
    removeAvatarBtn.addEventListener("click", async () => {
      if (uploading) return;
      if (!confirm("Weet je zeker dat je je profielfoto wilt verwijderen?")) return;

      try {
        const res = await fetch("/profiel/avatar/remove/", {
          method: "POST",
          headers: { "X-CSRFToken": getCSRFToken() },
        });

        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.error || "Verwijderen mislukt.");

        if (avatarPreview && data.avatar_url) avatarPreview.src = data.avatar_url;
        removeAvatarBtn.disabled = true;
        showFlash("success", "Profielfoto verwijderd.");
      } catch (err) {
        showFlash("error", err?.message || "Verwijderen mislukt.");
      }
    });
  }
})();