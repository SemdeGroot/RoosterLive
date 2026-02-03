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

  function getNextParam() {
    const p = new URLSearchParams(window.location.search);
    return p.get("next") || "/";
  }

  function findLoginForm() {
    return (
      document.querySelector("main.login-app form") ||
      document.querySelector("main form") ||
      document.querySelector("form")
    );
  }

  // =========================
  // Status UI
  // =========================
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
  // Capacitor plugins
  // =========================
  async function detectBiometricCapable() {
    if (!isCapacitorNative()) return false;

    const P = window.Capacitor?.Plugins || {};
    const NativeBiometric = P.NativeBiometric;

    if (!NativeBiometric || typeof NativeBiometric.isAvailable !== "function") return false;

    try {
      const a = await NativeBiometric.isAvailable();
      return !!a?.isAvailable;
    } catch {
      return false;
    }
  }

  async function biometricVerify({ reason } = {}) {
    const P = window.Capacitor?.Plugins || {};
    const msg = reason || "Bevestig met biometrie om in te loggen.";

    const NativeBiometric = P.NativeBiometric;
    if (NativeBiometric) {
      if (typeof NativeBiometric.isAvailable === "function") {
        const a = await NativeBiometric.isAvailable();
        if (a && typeof a.isAvailable === "boolean" && a.isAvailable === false) {
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

  async function getNativeDeviceId() {
    const Device = window.Capacitor?.Plugins?.Device;
    if (!Device || typeof Device.getId !== "function") {
      throw new Error("Device plugin niet beschikbaar in Capacitor.");
    }
    const info = await Device.getId();
    if (!info?.identifier) throw new Error("Kon device identifier niet ophalen.");
    return info.identifier;
  }

  // =========================
  // Secure storage
  // =========================
  const SECRET_KEY = "apo_native_device_secret_v1";

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

  async function secureSet(key, value) {
    const S = _securePlugin();
    if (!S) throw new Error("Secure Storage plugin niet beschikbaar.");

    if (typeof S.set === "function") {
      await S.set({ key, value: String(value ?? "") });
      return;
    }
    if (typeof S.setValue === "function") {
      await S.setValue({ key, value: String(value ?? "") });
      return;
    }
    throw new Error("Secure Storage plugin heeft geen set/setValue.");
  }

  function randomSecret(bytes = 32) {
    const arr = new Uint8Array(bytes);
    crypto.getRandomValues(arr);
    return btoa(String.fromCharCode(...arr))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
  }

  // =========================
  // Server calls
  // =========================
  async function nativeBiometricLogin({ identifier, device_id, device_secret, next }) {
    const resp = await fetch("/api/native-biometrics/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRF() },
      credentials: "same-origin",
      body: JSON.stringify({ identifier, device_id, device_secret, next }),
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Biometrisch inloggen mislukt.");
    }
    return data;
  }

  async function enableNativeBiometrics({ nickname } = {}) {
    if (!isCapacitorNative()) throw new Error("Niet in Capacitor native context.");

    await biometricVerify({ reason: "Bevestig met biometrie om biometrische login in te stellen." });

    const device_id = await getNativeDeviceId();
    const device_secret = randomSecret(32);
    await secureSet(SECRET_KEY, device_secret);

    const platform =
      (typeof window.Capacitor?.getPlatform === "function" ? window.Capacitor.getPlatform() : "other") || "other";

    const resp = await fetch("/api/native-biometrics/enable/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRF() },
      credentials: "same-origin",
      body: JSON.stringify({
        device_id,
        device_secret,
        platform,
        nickname: nickname || "App toestel",
      }),
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      try {
        await secureSet(SECRET_KEY, "");
      } catch {}
      throw new Error((data && data.error) || "Instellen mislukt.");
    }

    return data;
  }

  async function skipNativeBioOffer(device_id) {
    await fetch("/api/native-biometrics/skip/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRF() },
      credentials: "same-origin",
      body: JSON.stringify({ device_id }),
    }).catch(() => {});
  }

  // =========================
  // Login intercept: identifier -> biometrics -> fallback password -> TOTP
  // =========================
  async function tryNativeBiometricOnLoginForm() {
    if (!isCapacitorNative()) return;

    const form = findLoginForm();
    if (!form) return;

    // matcht jouw template
    const identifierInput = form.querySelector("#id_username, input[name='username']");
    const passwordBlock = document.getElementById("passwordBlock");
    const passwordInput = passwordBlock
      ? passwordBlock.querySelector("#id_password, input[name='password']")
      : form.querySelector("#id_password, input[name='password']");

    if (!identifierInput || !passwordBlock || !passwordInput) return;

    const hidePassword = () => {
      passwordBlock.style.display = "none";
    };

    const showPasswordAndFocus = () => {
      passwordBlock.style.display = "block";
      setTimeout(() => passwordInput.focus(), 0);
    };

    // default: password weg
    hidePassword();

    // voorkom dubbel binden
    if (form.dataset.nativeBioBound === "1") return;
    form.dataset.nativeBioBound = "1";

    async function getLocalSecret() {
      try {
        return (await secureGet(SECRET_KEY)) || "";
      } catch {
        return "";
      }
    }

    form.addEventListener("submit", async (ev) => {
      const identifier = (identifierInput.value || "").trim();
      const passwordVisible = passwordBlock.style.display !== "none";

      // password zichtbaar => laat Django het doen (password -> TOTP)
      if (passwordVisible) return;

      // password hidden: we willen NOOIT een gewone submit zonder password
      ev.preventDefault();
      clearStatus();

      if (!identifier) {
        // user moet eerst identifier invullen
        return;
      }

      try {
        const capable = await detectBiometricCapable();
        if (!capable) {
          showPasswordAndFocus();
          return;
        }

        const device_secret = await getLocalSecret();
        if (!device_secret) {
          showPasswordAndFocus();
          return;
        }

        setStatus("Bevestig met biometrie…", "waiting");
        await biometricVerify({ reason: "Bevestig met biometrie om in te loggen." });

        const device_id = await getNativeDeviceId();
        const next = getNextParam();

        const data = await nativeBiometricLogin({
          identifier,
          device_id,
          device_secret,
          next,
        });

        setStatus("Inloggen gelukt. Je wordt doorgestuurd…", "ok");
        window.location.href = data.redirect_url || next || "/";
      } catch (e) {
        console.error(e);
        clearStatus();
        showPasswordAndFocus();
      }
    });
  }

  // =========================
  // Public API
  // =========================
  window.nativeBiometricFlows = {
    enable: enableNativeBiometrics,
    tryOnLoginForm: tryNativeBiometricOnLoginForm,
    skipOffer: skipNativeBioOffer,
    getDeviceId: getNativeDeviceId,
    isCapacitorNative,
    detectBiometricCapable,
    secureGet,
    secureSet,
  };

  // =========================
  // DOMContentLoaded: flags + bind
  // =========================
  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const cap = document.getElementById("is_capacitor");
      if (cap) cap.value = isCapacitorNative() ? "1" : "0";

      const bio = document.getElementById("biometric_capable");
      if (bio) {
        bio.value = "0";
        if (isCapacitorNative()) {
          const capable = await detectBiometricCapable().catch(() => false);
          bio.value = capable ? "1" : "0";
        }
      }

      const secretEl = document.getElementById("biometric_secret_present");
      if (secretEl) {
        secretEl.value = "0";
        if (isCapacitorNative()) {
          const s = await secureGet(SECRET_KEY).catch(() => "");
          secretEl.value = s ? "1" : "0";
        }
      }

      await tryNativeBiometricOnLoginForm();
    } catch (e) {
      // als er iets crasht: toon password als failsafe
      console.error(e);
      const passwordBlock = document.getElementById("passwordBlock");
      if (passwordBlock) passwordBlock.style.display = "block";
    }
  });
})();
