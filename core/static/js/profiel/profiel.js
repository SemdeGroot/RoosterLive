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

  // ===== FLASH (client-side, zelfde styling als jouw base.css) =====
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

  // ===== helpers =====
  function toBlobAsync(canvas, type, quality) {
    return new Promise((resolve) => {
      canvas.toBlob((b) => resolve(b), type, quality);
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
  let originalFile = null;
  let uploading = false;

  function openModal() {
    if (!cropModal) return;
    cropModal.style.display = "flex";
  }

  function destroyCropper() {
    if (cropper) {
      cropper.destroy();
      cropper = null;
    }
  }

  function resetFileInput() {
    if (!avatarInput) return;
    avatarInput.value = ""; // belangrijk: zodat dezelfde file opnieuw gekozen kan worden
    originalFile = null;
    if (avatarFilename) avatarFilename.textContent = "";
  }

  function closeModal({ resetFile = false } = {}) {
    if (cropModal) cropModal.style.display = "none";
    destroyCropper();
    if (resetFile) resetFileInput();
  }

  function startCropperFromFile(file) {
    if (!file || !cropImage) return;

    if (avatarFilename) avatarFilename.textContent = file.name;

    destroyCropper();

    const url = URL.createObjectURL(file);

    // iOS/mobile race fix: load handler eerst, dan src
    const onLoad = () => {
      URL.revokeObjectURL(url);

      // 1 frame wachten zodat modal/layout klopt op mobile
      requestAnimationFrame(() => {
        destroyCropper();
        cropper = new Cropper(cropImage, {
          aspectRatio: 1,
          viewMode: 1,
          autoCropArea: 1,
          dragMode: "move",
          background: false,
          responsive: true,
          checkOrientation: false,
        });
      });
    };

    cropImage.addEventListener("load", onLoad, { once: true });

    openModal();
    cropImage.src = url;
  }

  // zodra file gekozen is → meteen crop modal
  if (avatarInput) {
    avatarInput.addEventListener("change", () => {
      originalFile = avatarInput.files && avatarInput.files[0] ? avatarInput.files[0] : null;
      if (!originalFile) return;
      startCropperFromFile(originalFile);
    });
  }

  if (closeCropModal) closeCropModal.addEventListener("click", () => closeModal({ resetFile: true }));
  if (cancelCroppedBtn) cancelCroppedBtn.addEventListener("click", () => closeModal({ resetFile: true }));

  if (saveCroppedBtn) {
    saveCroppedBtn.addEventListener("click", async (e) => {
      e.preventDefault();

      if (!cropper || uploading) return;

      const canvas = cropper.getCroppedCanvas({ width: 512, height: 512 });
      if (!canvas) return;

      uploading = true;
      saveCroppedBtn.disabled = true;
      saveCroppedBtn.textContent = "Bezig…";

      try {
        // WebP werkt niet overal op iOS → fallback naar JPEG/PNG
        let blob = await toBlobAsync(canvas, "image/webp", 0.90);
        let filename = "avatar.webp";

        if (!blob) {
          blob = await toBlobAsync(canvas, "image/jpeg", 0.92);
          filename = "avatar.jpg";
        }
        if (!blob) {
          blob = await toBlobAsync(canvas, "image/png", 1.0);
          filename = "avatar.png";
        }
        if (!blob) throw new Error("Kon geen afbeelding maken (browser beperking).");

        const fd = new FormData();
        fd.append("avatar", blob, filename);

        const res = await fetch("/profiel/avatar/upload/", {
          method: "POST",
          headers: { "X-CSRFToken": getCSRFToken() },
          body: fd,
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          if (data?.flash?.text) showFlash(data.flash.level || "error", data.flash.text);
          throw new Error(data?.error || "Upload mislukt.");
        }

        if (avatarPreview && data.avatar_url) avatarPreview.src = data.avatar_url;
        if (removeAvatarBtn) removeAvatarBtn.disabled = false;

        if (data?.flash?.text) showFlash(data.flash.level || "success", data.flash.text);
        else showFlash("success", "Profielfoto opgeslagen.");

        closeModal({ resetFile: true });
      } catch (err) {
        showFlash("error", err?.message || "Upload mislukt.");
      } finally {
        uploading = false;
        saveCroppedBtn.disabled = false;
        saveCroppedBtn.textContent = "Opslaan";
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
        if (!res.ok) {
          if (data?.flash?.text) showFlash(data.flash.level || "error", data.flash.text);
          throw new Error(data?.error || "Verwijderen mislukt.");
        }

        if (avatarPreview && data.avatar_url) avatarPreview.src = data.avatar_url;
        removeAvatarBtn.disabled = true;

        if (data?.flash?.text) showFlash(data.flash.level || "success", data.flash.text);
        else showFlash("success", "Profielfoto verwijderd.");
      } catch (err) {
        showFlash("error", err?.message || "Verwijderen mislukt.");
      }
    });
  }
})();