// static/js/auth/passkeys.js
(function () {
  const onHttps = location.protocol === "https:" || location.hostname === "localhost";

  // ---------- PASSKEY STATUS UI ----------
  const passkeyStatusEl =
    document.getElementById("passkeyStatus") ||
    document.getElementById("passkeyMessage");

  function setPasskeyStatus(text, variant) {
    if (!passkeyStatusEl) return;
    const base = "passkey-message";
    const extra = variant ? " " + variant : "";
    passkeyStatusEl.className = base + extra;
    passkeyStatusEl.textContent = text || "";
  }

  function clearPasskeyStatus() {
    if (!passkeyStatusEl) return;
    passkeyStatusEl.className = "passkey-message";
    passkeyStatusEl.textContent = "";
  }

  function isCapacitorNative() {
    return (
      !!window.Capacitor &&
      (typeof window.Capacitor.isNativePlatform === "function"
        ? window.Capacitor.isNativePlatform()
        : !!window.Capacitor.isNativePlatform)
    );
  }

  // ---------- WEB AUTHN SUPPORT ----------
  function isWebAuthnSupported() {
    return (
      typeof window.PublicKeyCredential !== "undefined" &&
      typeof window.navigator.credentials !== "undefined" &&
      typeof window.navigator.credentials.get === "function"
    );
  }

  // ---------- BROWSER / CAPABILITIES ----------

  async function supportsHybridTransport() {
    // null = onbekend (API niet beschikbaar / error)
    if (!PublicKeyCredential?.getClientCapabilities) return null;
    try {
      const caps = await PublicKeyCredential.getClientCapabilities();
      return !!caps?.hybridTransport;
    } catch {
      return null;
    }
  }

  // ---------- HELPERS ----------
  function getCSRF() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function b64uToArrayBuffer(b64u) {
    const pad = "=".repeat((4 - (b64u.length % 4)) % 4);
    const base64 = (b64u + pad).replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  function arrayBufferToB64u(buf) {
    const bytes = new Uint8Array(buf);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64 = btoa(binary);
    return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function getNextParam() {
    const params = new URLSearchParams(window.location.search);
    return params.get("next") || "/";
  }

  function findLoginForm() {
    return (
      document.querySelector("main.login-app form") ||
      document.querySelector("main form") ||
      document.querySelector("form")
    );
  }

  // ---------- PASSKEY REGISTRATIE (setup pagina) ----------
  async function prepareRegisterOptions() {
    const resp = await fetch("/api/passkeys/options/register/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({}),
    });
    if (!resp.ok) {
      throw new Error("Kon registratie-opties niet ophalen.");
    }
    const options = await resp.json();
    options.challenge = b64uToArrayBuffer(options.challenge);
    options.user.id = new TextEncoder().encode(options.user.id);

    if (options.excludeCredentials) {
      options.excludeCredentials = options.excludeCredentials.map((c) => ({
        ...c,
        id: b64uToArrayBuffer(c.id),
      }));
    }
    return options;
  }

  async function sendRegisterCredential(attResp) {
    const resp = await fetch("/api/passkeys/register/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify(attResp),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error(data.error || "Passkey registratie mislukt.");
    }
    return data;
  }

  // Publieke setup functie (op setup pagina)
  window.setupPasskey = async function (nextUrl) {
    if (!onHttps) {
      setPasskeyStatus("Passkeys werken alleen via HTTPS of op localhost.", "error");
      return;
    }
    if (!isWebAuthnSupported()) {
      setPasskeyStatus("Dit apparaat ondersteunt geen passkeys.", "error");
      return;
    }

    try {
      setPasskeyStatus("Passkey wordt ingesteld. Even geduld...", "waiting");

      const options = await prepareRegisterOptions();
      const cred = await navigator.credentials.create({ publicKey: options });
      if (!cred) {
        setPasskeyStatus("Instellen van passkey is afgebroken.", "error");
        return;
      }

      const attResp = {
        id: cred.id,
        rawId: arrayBufferToB64u(cred.rawId),
        type: cred.type,
        clientExtensionResults: cred.getClientExtensionResults(),
        response: {
          attestationObject: arrayBufferToB64u(cred.response.attestationObject),
          clientDataJSON: arrayBufferToB64u(cred.response.clientDataJSON),
        },
      };

      await sendRegisterCredential(attResp);
      setPasskeyStatus("Passkey succesvol ingesteld. Je wordt doorgestuurd…", "ok");
      window.location.href = nextUrl || "/";
    } catch (e) {
      console.error(e);
      if (e && (e.name === "AbortError" || e.name === "NotAllowedError")) {
        setPasskeyStatus("Passkey instellen geannuleerd.", "error");
      } else {
        setPasskeyStatus("Passkey instellen mislukt. Probeer het opnieuw.", "error");
      }
    }
  };

  // ---------- LOGIN FLOW (passkey eerst, daarna password fallback) ----------
  async function passkeyLoginOptions(identifier) {
    const next = getNextParam();
    const resp = await fetch("/api/passkeys/login/options/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ identifier, next }),
    });

    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Passkey inloggen mislukt.");
    }
    return data;
  }

  async function sendAuthCredential(assertion) {
    const resp = await fetch("/api/passkeys/authenticate/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify(assertion),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error("Authenticatie mislukt.");
    }
    return data;
  }

  async function tryPasskeyOnLoginForm() {
    const form = findLoginForm();
    if (!form) return;
    if (isCapacitorNative()) return;

    const usernameInput = form.querySelector(
      'input[name="username"], input[name$="-username"], input[name="identifier"], input[name$="-identifier"]'
    );
    const passwordInput = form.querySelector('input[name="password"], input[name$="-password"]');
    if (!usernameInput || !passwordInput) return;

    const passwordBlock = document.getElementById("passwordBlock");
    const errorEl = document.getElementById("passkeyLoginError");

    const setError = (txt) => {
      if (!errorEl) return;
      if (!txt) {
        errorEl.textContent = "";
        errorEl.style.display = "none";
      } else {
        errorEl.textContent = txt;
        errorEl.style.display = "block";
      }
    };

    const showPasswordAndFocus = () => {
      if (passwordBlock) passwordBlock.style.display = "block";
      setTimeout(() => passwordInput.focus(), 0);
    };

    // Prefill identifier
    try {
      const last = localStorage.getItem("lastIdentifier") || "";
      if (last && !usernameInput.value) usernameInput.value = last;
    } catch {}

    // init: password verborgen
    if (passwordBlock) passwordBlock.style.display = "none";

    // geen webauthn -> password
    if (!onHttps || !isWebAuthnSupported()) {
      showPasswordAndFocus();
      return;
    }

    form.addEventListener("submit", async (ev) => {
      const identifier = (usernameInput.value || "").trim();
      const passwordVisible = passwordBlock ? passwordBlock.style.display !== "none" : true;

      // password zichtbaar -> normale submit
      if (passwordVisible) {
        setError("");
        try {
          if (identifier) localStorage.setItem("lastIdentifier", identifier);
        } catch {}
        return;
      }

      if (!identifier) {
        setError("");
        return;
      }

      // passkey pad
      ev.preventDefault();
      setError("");
      clearPasskeyStatus();

      try {
        const data = await passkeyLoginOptions(identifier);

        if (!data.has_passkey) {
          showPasswordAndFocus();
          return;
        }

        setPasskeyStatus("Wachten op bevestiging via passkey...", "waiting");

        // ---- USER-FRIENDLY: QR/hybrid check (desktop) ----
        const hybrid = await supportsHybridTransport();

        // 1) Zeker: browser zegt "geen hybrid"
        if (hybrid === false) {
          clearPasskeyStatus();
          setError(
            "Deze browser ondersteunt geen QR-login via je telefoon. " +
              "Gebruik Chrome, Edge of Safari of log in met je wachtwoord en vul daarna je 2FA-code in."
          );
          showPasswordAndFocus();
          return;
        }

        // -----------------------------------------------

        const options = data.options;
        options.challenge = b64uToArrayBuffer(options.challenge);

        if (options.allowCredentials) {
          options.allowCredentials = options.allowCredentials.map((c) => ({
            ...c,
            id: b64uToArrayBuffer(c.id),
          }));
        }

        // Hint: prefer hybrid (mag genegeerd worden)
        if (Array.isArray(options.hints) === false) {
          options.hints = ["hybrid"];
        }

        const assertion = await navigator.credentials.get({ publicKey: options });

        if (!assertion) {
          clearPasskeyStatus();
          showPasswordAndFocus();
          return;
        }

        const authResp = {
          id: assertion.id,
          rawId: arrayBufferToB64u(assertion.rawId),
          type: assertion.type,
          clientExtensionResults: assertion.getClientExtensionResults(),
          response: {
            authenticatorData: arrayBufferToB64u(assertion.response.authenticatorData),
            clientDataJSON: arrayBufferToB64u(assertion.response.clientDataJSON),
            signature: arrayBufferToB64u(assertion.response.signature),
            userHandle: assertion.response.userHandle ? arrayBufferToB64u(assertion.response.userHandle) : null,
          },
        };

        const result = await sendAuthCredential(authResp);

        try {
          localStorage.setItem("lastIdentifier", identifier);
        } catch {}

        setPasskeyStatus("Passkey-login geslaagd. Je wordt doorgestuurd…", "ok");
        window.location.href = result.redirect_url || "/";
      } catch (e) {
        console.error(e);
        clearPasskeyStatus();

        let friendly =
          "Er ging iets mis met inloggen via je passkey. " +
          "Log in met je wachtwoord en voer daarna je 2FA-code in.";

        if (e && (e.name === "NotAllowedError" || e.name === "AbortError")) {
          friendly =
            "Inloggen met passkey is geannuleerd. " +
            "Log in met je wachtwoord en voer daarna je 2FA-code in.";
        }

        setError(friendly);
        showPasswordAndFocus();
      }
    });
  }

  // ---------- OFFER PASSKEY (mobiel-only + platform auth check) ----------
  async function checkOfferPasskey() {
    if (!onHttps || !isWebAuthnSupported()) return;
    if (isCapacitorNative()) return;

    if (
      !window.PublicKeyCredential ||
      typeof PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable !== "function"
    ) {
      return;
    }

    let hasPlatform = false;
    try {
      hasPlatform = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch {
      return;
    }
    if (!hasPlatform) return;

    const next = window.location.pathname + window.location.search;

    const resp = await fetch("/api/passkeys/should-offer/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ next }),
    });

    if (!resp.ok) return;
    const data = await resp.json();
    if (data.offer && data.setup_url) {
      window.location.href = data.setup_url;
    }
  }

  // ---------- PUBLIC API ----------
  window._passkeys = window._passkeys || {};
  window._passkeys.tryPasskeyOnLoginForm = tryPasskeyOnLoginForm;
  window._passkeys.checkOfferPasskey = checkOfferPasskey;

  document.addEventListener("DOMContentLoaded", () => {
    tryPasskeyOnLoginForm();
    // checkOfferPasskey() niet automatisch op login scherm
  });

  // --------- BUGFIX: helper typo guard ----------
  function arrayBufferToBu64(buf) {
    return arrayBufferToB64u(buf);
  }
})();