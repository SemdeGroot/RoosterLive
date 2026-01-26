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
    // base64url random
    const arr = new Uint8Array(bytes);
    crypto.getRandomValues(arr);
    return btoa(String.fromCharCode(...arr))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
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

  async function enableNativeBiometrics({ nickname } = {}) {
    if (!isCapacitorNative()) throw new Error("Niet in Capacitor native context.");

    // Belangrijk: pairing alleen na echte biometrie prompt
    await biometricVerify({ reason: "Bevestig met biometrie om biometrische login in te stellen." });

    const device_id = await getNativeDeviceId();

    // Nieuwe secret genereren en lokaal opslaan (reinstall-safe)
    const device_secret = randomSecret(32);
    await secureSet(SECRET_KEY, device_secret);

    const platform =
      (typeof window.Capacitor?.getPlatform === "function" ? window.Capacitor.getPlatform() : "other") || "other";

    const resp = await fetch("/api/native-biometrics/enable/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
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
      // cleanup: geen half-ingestelde secret laten hangen
      try {
        await secureSet(SECRET_KEY, "");
      } catch {}
      throw new Error((data && data.error) || "Instellen mislukt.");
    }

    return data;
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
    const passwordInput = form.querySelector('input[name="password"], input[name$="-password"]');
    if (!usernameInput || !passwordInput) return;

    // voorkom dubbel binden
    if (form.dataset.nativeBioBound === "1") return;
    form.dataset.nativeBioBound = "1";

    form.addEventListener("submit", async (ev) => {
      const username = (usernameInput.value || "").trim();
      const password = passwordInput.value || "";
      if (!username || !password) return;

      // Alleen Capacitor stap 1 intercepten
      ev.preventDefault();
      clearStatus();

      try {
        // Als er géén secret is (reinstall), NOOIT prompten.
        // Gewoon reguliere 2FA flow (form.submit -> django-two-factor).
        let device_secret = "";
        try {
          device_secret = await secureGet(SECRET_KEY);
        } catch {
          device_secret = "";
        }
        if (!device_secret) {
          form.submit();
          return;
        }

        // 1) check username+password via JSON endpoint
        setStatus("Controleren…", "waiting");
        const data = await passwordLoginWithNativeBio(username, password);

        // geen native bio actief voor user+device => normale 2FA flow
        if (!data.has_native_bio) {
          clearStatus();
          form.submit();
          return;
        }

        // 2) wel secret + server says has_native_bio -> prompt en native login
        setStatus("Bevestig met biometrie…", "waiting");
        await biometricVerify({ reason: "Bevestig met biometrie om in te loggen." });

        const device_id = await getNativeDeviceId();
        await nativeBiometricLogin(device_id, device_secret);

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

  // =========================
  // Expose + auto-run (zoals passkeys)
  // =========================
  window.nativeBiometricFlows = {
    login: loginWithNativeBiometricsFlow,
    enable: enableNativeBiometrics, // <-- FIX: setup.html verwacht deze
    tryOnLoginForm: tryNativeBiometricOnLoginForm,
    skipOffer: skipNativeBioOffer,
    getDeviceId: getNativeDeviceId,
    isCapacitorNative,
    detectBiometricCapable, // handig voor debug
  };

  document.addEventListener("DOMContentLoaded", async () => {
    // is_capacitor flag
    const cap = document.getElementById("is_capacitor");
    if (cap) cap.value = isCapacitorNative() ? "1" : "0";

    // biometric_capable flag (default 0)
    const bio = document.getElementById("biometric_capable");
    if (bio) {
      bio.value = "0";
      if (isCapacitorNative()) {
        try {
          const capable = await detectBiometricCapable();
          bio.value = capable ? "1" : "0";
        } catch {
          bio.value = "0";
        }
      }
    }

    // biometric_secret_present flag (default 0)
    const secretEl = document.getElementById("biometric_secret_present");
    if (secretEl) {
      secretEl.value = "0";
      if (isCapacitorNative()) {
        try {
          const s = await secureGet(SECRET_KEY);
          secretEl.value = s ? "1" : "0";
        } catch {
          secretEl.value = "0";
        }
      }
    }

    // Koppel biometrische login intercept aan submit (stap 1)
    tryNativeBiometricOnLoginForm();
  });
})();