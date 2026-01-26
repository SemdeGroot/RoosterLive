// static/js/auth/native_biometrics.js
(function () {
  // =========================
  // Helpers
  // =========================
  function getCSRF() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function isCapacitorNative() {
    const C = window.Capacitor;
    if (!C) return false;
    if (typeof C.getPlatform === "function") {
      const p = C.getPlatform();
      return p === "ios" || p === "android";
    }
    if (typeof C.isNativePlatform === "function") return !!C.isNativePlatform();
    return !!C.isNativePlatform;
  }

  async function detectBiometricCapable() {
    if (!isCapacitorNative()) return false;

    // Houd dit bewust simpel: alleen capability checken.
    const P = window.Capacitor?.Plugins || {};
    const NativeBiometric = P.NativeBiometric;

    if (!NativeBiometric || typeof NativeBiometric.isAvailable !== "function") {
      return false;
    }

    try {
      const a = await NativeBiometric.isAvailable();
      return !!a?.isAvailable;
    } catch {
      return false;
    }
  }

  async function getNativeDeviceId() {
    const Device = window.Capacitor?.Plugins?.Device;
    if (!Device || typeof Device.getId !== "function") {
      throw new Error("Device plugin niet beschikbaar in Capacitor.");
    }
    const info = await Device.getId();
    if (!info?.identifier) throw new Error("Kon device identifier niet ophalen.");
    return info.identifier;
  }

  function getNextParam() {
    const p = new URLSearchParams(window.location.search);
    return p.get("next") || "/";
  }

  // status UI (zelfde element als passkeys; anders geen UI)
  const statusEl =
    document.getElementById("passkeyStatus") ||
    document.getElementById("biometricMessage") ||
    document.getElementById("passkeyMessage");

  function setStatus(text, variant) {
    if (!statusEl) return;
    const base = "passkey-message";
    const extra = variant ? " " + variant : "";
    statusEl.className = base + extra;
    statusEl.textContent = text || "";
  }
  function clearStatus() {
    if (!statusEl) return;
    statusEl.className = "passkey-message";
    statusEl.textContent = "";
  }

  // =========================
  // Biometric verify (plugins)
  // =========================
  async function biometricVerify({ reason } = {}) {
    const P = window.Capacitor?.Plugins || {};
    const msg = reason || "Bevestig met biometrie om in te loggen.";

    const NativeBiometric = P.NativeBiometric;
    if (NativeBiometric) {
      if (typeof NativeBiometric.isAvailable === "function") {
        const a = await NativeBiometric.isAvailable();
        if (a && typeof a.isAvailable === "boolean" && a.isAvailable === false) {
          // Jouw oude gedrag: device zonder biometrie geeft deze fout
          throw new Error("Biometrie is niet beschikbaar op dit toestel.");
        }
      }
      if (typeof NativeBiometric.verifyIdentity === "function") {
        await NativeBiometric.verifyIdentity({ reason: msg });
        return true;
      }
      if (typeof NativeBiometric.authenticate === "function") {
        await NativeBiometric.authenticate({ reason: msg });
        return true;
      }
      throw new Error("NativeBiometric plugin mist verifyIdentity/authenticate.");
    }

    const Biometric = P.Biometric;
    if (Biometric) {
      if (typeof Biometric.authenticate === "function") {
        await Biometric.authenticate({ reason: msg });
        return true;
      }
      if (typeof Biometric.verifyIdentity === "function") {
        await Biometric.verifyIdentity({ reason: msg });
        return true;
      }
      throw new Error("Biometric plugin mist authenticate/verifyIdentity.");
    }

    throw new Error("Biometric plugin niet beschikbaar.");
  }

  // =========================
  // Secure storage
  // =========================
  function _securePlugin() {
    const P = window.Capacitor?.Plugins || {};
    return P.SecureStoragePlugin || P.SecureStorage || null;
  }

  async function secureGet(key) {
    const S = _securePlugin();
    if (!S) throw new Error("Secure Storage plugin niet beschikbaar.");

    try {
      if (typeof S.get === "function") {
        const res = await S.get({ key });
        return res?.value || "";
      }
      if (typeof S.getValue === "function") {
        const res = await S.getValue({ key });
        return res?.value || "";
      }
      throw new Error("Secure Storage plugin heeft geen get/getValue.");
    } catch (e) {
      const msg = (e && (e.message || e.error || String(e))) || "";
      if (/does not exist|not exist|not found|missing/i.test(msg)) return "";
      throw e;
    }
  }

  // =========================
  // Server calls (passkey-style)
  // =========================
  async function passwordLoginWithNativeBio(username, password) {
    const device_id = await getNativeDeviceId();
    const next = getNextParam();

    const resp = await fetch("/api/native-biometrics/password-login/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ username, password, device_id, next }),
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Login mislukt.");
    }
    return data;
  }

  async function nativeBiometricLogin(device_id, device_secret) {
    const resp = await fetch("/api/native-biometrics/login/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ device_id, device_secret }),
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Biometrisch inloggen mislukt.");
    }
    return data;
  }

  async function shouldOfferNativeBio(device_id, next) {
    const resp = await fetch("/api/native-biometrics/should-offer/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ device_id, next }),
    });
    if (!resp.ok) return { offer: false };
    return resp.json().catch(() => ({ offer: false }));
  }

  async function skipNativeBioOffer(device_id) {
    await fetch("/api/native-biometrics/skip/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ device_id }),
    }).catch(() => {});
  }

  // =========================
  // Flows (zoals passkeys)
  // =========================
  const SECRET_KEY = "apo_native_device_secret_v1";

  async function loginWithNativeBiometricsFlow() {
    if (!isCapacitorNative()) throw new Error("Niet in Capacitor native context.");

    // 1) prompt
    await biometricVerify({ reason: "Bevestig met biometrie om in te loggen." });

    // 2) secret uit secure storage
    const device_id = await getNativeDeviceId();
    const device_secret = await secureGet(SECRET_KEY);
    if (!device_secret) throw new Error("Geen biometrie-setup gevonden op dit device.");

    // 3) server session
    await nativeBiometricLogin(device_id, device_secret);
    return true;
  }

  function findLoginForm() {
    return (
      document.querySelector("main.login-app form") ||
      document.querySelector("main form") ||
      document.querySelector("form")
    );
  }

  async function tryNativeBiometricOnLoginForm() {
    if (!isCapacitorNative()) return;

    const form = findLoginForm();
    if (!form) return;

    const usernameInput = form.querySelector(
      'input[name="username"], input[name$="-username"], input[name="id_identifier"]'
    );
    const passwordInput = form.querySelector(
      'input[name="password"], input[name$="-password"]'
    );
    if (!usernameInput || !passwordInput) return;

    // Zorg dat we niet per ongeluk dubbel binden
    if (form.dataset.nativeBioBound === "1") return;
    form.dataset.nativeBioBound = "1";

    form.addEventListener("submit", async (ev) => {
      const username = (usernameInput.value || "").trim();
      const password = passwordInput.value || "";
      if (!username || !password) return;

      ev.preventDefault();
      clearStatus();

      try {
        setStatus("Controleren…", "waiting");
        const data = await passwordLoginWithNativeBio(username, password);

        // geen native bio op dit device/user => normale flow (2FA)
        if (!data.has_native_bio) {
          clearStatus();
          form.submit();
          return;
        }

        // 2) toon prompt en doe native bio login
        setStatus("Bevestig met biometrie…", "waiting");
        await loginWithNativeBiometricsFlow();

        setStatus("Inloggen gelukt. Je wordt doorgestuurd…", "ok");
        const redirectUrl = data.redirect_url || getNextParam() || "/";
        window.location.href = redirectUrl;
      } catch (e) {
        console.error(e);
        clearStatus();
        // fallback: normale 2FA flow
        form.submit();
      }
    });
  }

  async function checkOfferNativeBiometrics() {
    if (!isCapacitorNative()) return;

    let device_id;
    try {
      device_id = await getNativeDeviceId();
    } catch {
      return;
    }

    const next = window.location.pathname + window.location.search;
    const data = await shouldOfferNativeBio(device_id, next).catch(() => ({ offer: false }));
    if (data && data.offer && data.setup_url) {
      window.location.href = data.setup_url;
    }
  }

  // =========================
  // Expose + auto-run (zoals passkeys)
  // =========================
  window.nativeBiometricFlows = {
    login: loginWithNativeBiometricsFlow,
    tryOnLoginForm: tryNativeBiometricOnLoginForm,
    skipOffer: skipNativeBioOffer,
    getDeviceId: getNativeDeviceId,
    isCapacitorNative,
    detectBiometricCapable, // handig voor debug
  };

  document.addEventListener("DOMContentLoaded", async () => {
    // net als passkeys: meteen koppelen aan login submit
    const cap = document.getElementById("is_capacitor");
    if (cap && isCapacitorNative()) cap.value = "1";

    // capability flag zetten voor server-success-url logic
    const bio = document.getElementById("biometric_capable");
    if (bio) {
      bio.value = "0"; // default
      if (isCapacitorNative()) {
        const capable = await detectBiometricCapable();
        bio.value = capable ? "1" : "0";
      }
    }

    tryNativeBiometricOnLoginForm();
  });
})();
