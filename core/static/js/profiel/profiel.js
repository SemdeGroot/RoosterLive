(function () {
  function $(id) { return document.getElementById(id); }

  // ===== CONFIG =====
  const SETTINGS_UPDATE_URL = "/profiel/settings/update/";

  // ===== CAPACITOR HELPERS =====
  function isCapacitorNative() {
    const cap = window.Capacitor;
    if (!cap) return false;

    if (typeof cap.isNativePlatform === "function") {
      try { return cap.isNativePlatform(); } catch (_) { /* ignore */ }
    }

    const platform = (typeof cap.getPlatform === "function") ? cap.getPlatform() : "web";
    return platform !== "web";
  }

  function getCapacitorCameraPlugin() {
    const cap = window.Capacitor;
    if (!cap || !cap.Plugins) return null;
    return cap.Plugins.Camera || null;
  }

  async function capacitorPhotoToFile(photo) {
    const webPath = photo && photo.webPath ? photo.webPath : null;
    if (!webPath) throw new Error("Geen webPath teruggekregen van Camera plugin.");

    const resp = await fetch(webPath);
    const blob = await resp.blob();

    const format = (photo && photo.format ? String(photo.format) : "").toLowerCase();
    const ext =
      format ||
      (blob.type && blob.type.includes("png") ? "png" :
      (blob.type && blob.type.includes("webp") ? "webp" : "jpg"));

    const filename = `avatar.${ext}`;
    return new File([blob], filename, { type: blob.type || `image/${ext}` });
  }

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
    // Works because your page already has csrf token in forms
    const el = document.querySelector("input[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  // ===== AUTOSAVE SETTINGS =====
  const savingKeys = new Set();

  const PREF_KEYS = new Set([
    "push_enabled", "push_new_roster", "push_new_agenda", "push_news_upload", "push_dienst_changed",
    "push_birthday_self", "push_birthday_apojansen", "push_uren_reminder",
    "email_enabled", "email_birthday_self", "email_uren_reminder", "email_diensten_overzicht"
  ]);

  const PROFILE_KEYS = new Set([
    "haptics_enabled"
  ]);

  async function saveSetting(key, valueBool) {
    try {
      const res = await fetch(SETTINGS_UPDATE_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({ key: key, value: !!valueBool }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Opslaan mislukt.");

      return true;
    } catch (err) {
      console.error(err);
      showFlash("error", err?.message || "Opslaan mislukt.");
      return false;
    }
  }

  function setAppSetting(key, value) {
    // Keep global settings in sync so haptic_feedback.js can react instantly
    window.APP_SETTINGS = window.APP_SETTINGS || {};
    window.APP_SETTINGS[key] = value;
  }

  function setBusy(el, busy) {
    // Optional tiny UX: disable while saving to prevent double-toggles
    if (!el) return;
    el.disabled = !!busy;
  }

  async function handleToggleAutosave(checkboxEl, key) {
    if (!checkboxEl) return;

    if (savingKeys.has(key)) return;
    savingKeys.add(key);

    const prev = !checkboxEl.checked; // because change already applied
    const next = !!checkboxEl.checked;

    setBusy(checkboxEl, true);

    const ok = await saveSetting(key, next);

    setBusy(checkboxEl, false);
    savingKeys.delete(key);

    if (!ok) {
      // revert
      checkboxEl.checked = prev;
      // keep UI consistent
      if (checkboxEl.id === "id_push_enabled" || checkboxEl.id === "id_email_enabled") {
        syncChildBlocks();
      }
      return;
    }

    // success: if this is an app setting, update runtime
    if (PROFILE_KEYS.has(key)) {
      setAppSetting(key, next);
    }
  }

  // ===== NOTIF UI =====
  function syncChildBlocks() {
    document.querySelectorAll("[data-child-of]").forEach((block) => {
      const parentId = block.getAttribute("data-child-of");
      const parent = document.getElementById(parentId);
      if (!parent) return;
      block.classList.toggle("is-disabled", !parent.checked);
    });
  }

  document.addEventListener("DOMContentLoaded", syncChildBlocks);

  // Autosave listener for ALL checkboxes on this page (that match known keys)
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (!t || t.type !== "checkbox") return;

    // App voorkeuren: fixed id -> key
    if (t.id === "id_haptics_enabled") {
      handleToggleAutosave(t, "haptics_enabled");
      return;
    }

    // Notification preferences: name matches key
    const name = t.name || "";
    if (PREF_KEYS.has(name)) {
      handleToggleAutosave(t, name);

      // keep your children enabled/disabled in sync immediately
      if (t.id === "id_push_enabled" || t.id === "id_email_enabled") {
        syncChildBlocks();
      }
    }
  });

  // ===== CANVAS UTILS =====
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

  const avatarPickLabel = document.querySelector('label[for="avatarInput"]');

  let cropper = null;
  let uploading = false;
  let cropperReady = false;

  function setSaveState(enabled, label) {
    if (!saveCroppedBtn) return;
    saveCroppedBtn.disabled = !enabled;
    if (label) saveCroppedBtn.textContent = label;
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
    document.body.style.overflow = "";
    destroyCropper();
    if (resetFile) resetFileInput();
    setSaveState(true, "Opslaan");
  }

  async function startCropperFromFile(file) {
    if (!file || !cropImage || !cropModal) return;

    setSaveState(false, "Laden…");
    destroyCropper();

    if (avatarFilename) avatarFilename.textContent = file.name || "";

    cropModal.style.display = "flex";
    document.body.style.overflow = "hidden";

    try {
      await waitFor(() => typeof window.Cropper === "function", 5000);
    } catch (_) {
      showFlash("error", "Fout: Cropper library niet geladen.");
      closeModal({ resetFile: true });
      return;
    }

    const url = URL.createObjectURL(file);

    const tempImg = new Image();
    tempImg.onload = () => {
      cropImage.src = url;

      requestAnimationFrame(() => {
        setTimeout(() => {
          try {
            cropper = new window.Cropper(cropImage, {
              aspectRatio: 1,
              viewMode: 1,
              dragMode: "move",
              autoCropArea: 1,
              checkOrientation: true,
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
            closeModal({ resetFile: true });
          }
        }, 100);
      });
    };
    tempImg.src = url;
  }

  // Native: open fotobibliotheek
  if (avatarPickLabel) {
    avatarPickLabel.addEventListener("click", async (e) => {
      if (!isCapacitorNative()) return;
      const Camera = getCapacitorCameraPlugin();
      if (!Camera) return;

      e.preventDefault();

      try {
        const photo = await Camera.getPhoto({
          quality: 92,
          resultType: "uri",
          source: "photos",
        });

        if (!photo) return;

        const file = await capacitorPhotoToFile(photo);
        startCropperFromFile(file);
      } catch (err) {
        console.error(err);
      }
    });
  }

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

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          if (data.flash && data.flash.text) {
            showFlash(data.flash.level || "error", data.flash.text);
          } else {
            showFlash("error", data.error || "Er ging iets mis bij het uploaden.");
          }
          uploading = false;
          setSaveState(true, "Opslaan");
          return;
        }

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