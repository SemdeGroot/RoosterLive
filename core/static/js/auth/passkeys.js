// static/js/auth/passkeys.js
(function () {
  const onHttps = location.protocol === "https:" || location.hostname === "localhost";

  // ---------- PASSKEY STATUS UI (NIEUW) ----------
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

  // ---------- DEVICE DETECTIE ----------
  function isMobile() {
      const ua = navigator.userAgent || "";

      // 1. BLOKKEER WINDOWS (Jouw ThinkPad)
      // Dit blokkeert alles met 'Windows' in de browser-info,
      // ongeacht of het een touchscreen heeft of hoe breed het scherm is.
      if (/Windows/i.test(ua)) {
        return false;
      }

      // 2. BLOKKEER MACOS DESKTOP (MacBooks/iMacs)
      // MacBooks hebben 'Macintosh' maar géén touchpoints (of max 0).
      // (iPads hebben soms ook 'Macintosh' maar wel touchpoints > 0).
      const isMac = /Macintosh/i.test(ua);
      if (isMac && (!navigator.maxTouchPoints || navigator.maxTouchPoints === 0)) {
        return false; 
      }

      // 3. BLOKKEER LINUX DESKTOP
      // Android is ook Linux, dus we blokkeren Linux alleen als het GEEN Android is.
      if (/Linux/i.test(ua) && !/Android/i.test(ua)) {
          return false;
      }

      // 4. WAT OVERBLIJFT IS MOBIEL (Android / iOS / iPadOS)
      // Hier vallen ook brede foldables onder, want die hebben 'Android' in de ua.
      if (/Android|iPhone|iPad|iPod/i.test(ua) || (isMac && navigator.maxTouchPoints > 0)) {
          return true;
      }

      return false;
    }

  function isWebAuthnSupported() {
    return (
      typeof window.PublicKeyCredential !== "undefined" &&
      typeof window.navigator.credentials !== "undefined" &&
      typeof window.navigator.credentials.get === "function"
    );
  }

  // ---------- device_hash ----------
  async function getDeviceHash() {
    const ua = navigator.userAgent || "";
    const platform = navigator.platform || "";
    const vendor = navigator.vendor || "";
    const lang = navigator.language || "";
    const hw = [
      screen.width,
      screen.height,
      screen.colorDepth,
      navigator.hardwareConcurrency || 0,
    ].join("x");
    const touch = navigator.maxTouchPoints || 0;
    const data = [ua, platform, vendor, lang, hw, touch].join("|");

    const enc = new TextEncoder().encode(data);
    const buf = await crypto.subtle.digest("SHA-256", enc);
    const bytes = Array.from(new Uint8Array(buf));
    return bytes.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  if (!window.getDeviceHash) {
    window.getDeviceHash = getDeviceHash;
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

  // ---------- PASSKEY REGISTRATIE ----------
  async function prepareRegisterOptions() {
    const device_hash = await getDeviceHash();
    const resp = await fetch("/api/passkeys/options/register/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ device_hash }),
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

  window.setupPasskey = async function (nextUrl, msgEl) {
    // geen emoji’s, alleen kleuren via CSS classes
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

      // Speciaal afvangen als de gebruiker de passkey-actie annuleert
      if (e && (e.name === "AbortError" || e.name === "NotAllowedError")) {
        setPasskeyStatus("Passkey instellen geannuleerd.", "error");
      } else {
        setPasskeyStatus(
          "Passkey instellen mislukt: " + (e.message || ""),
          "error"
        );
      }
    }
  };

  // ---------- LOGIN FLOW ----------
  async function passwordLoginWithPasskey(username, password) {
    const device_hash = await getDeviceHash();
    const next = getNextParam();

    const resp = await fetch("/api/passkeys/password-login/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ username, password, device_hash, next }),
    });

    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      const err = (data && data.error) || "Login mislukt.";
      throw new Error(err);
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
      throw new Error(data.error || "Authenticatie mislukt.");
    }
    return data;
  }

  function findLoginForm() {
    return (
      document.querySelector("main.login-app form") ||
      document.querySelector("main form") ||
      document.querySelector("form")
    );
  }

  async function tryPasskeyOnLoginForm() {
    const form = findLoginForm();
    if (!form) return;

    const usernameInput = form.querySelector(
      'input[name="username"], input[name$="-username"]'
    );
    const passwordInput = form.querySelector(
      'input[name="password"], input[name$="-password"]'
    );

    if (!usernameInput || !passwordInput) return;

    // Foutmelding onder input, met display:none
    const errorId = "passkeyLoginError";
    let errorEl = document.getElementById(errorId);
    if (!errorEl) {
      errorEl = document.createElement("p");
      errorEl.id = errorId;
      errorEl.className = "passkey-message error"; // zelfde styling als waiting
      errorEl.style.display = "none"; // mag blijven
      passwordInput.parentNode.insertAdjacentElement("afterend", errorEl);
    }

    const setError = (txt) => {
      if (!txt) {
        errorEl.textContent = "";
        errorEl.style.display = "none";
      } else {
        errorEl.textContent = txt;
        errorEl.style.display = "block";
      }
    };

    if (!onHttps || !isWebAuthnSupported() || !isMobile()) return;

    form.addEventListener("submit", async (ev) => {
      const username = (usernameInput.value || "").trim();
      const password = passwordInput.value || "";

      if (!username || !password) {
        setError("");
        return; // normale submit, Django regelt de foutmelding
      }

      ev.preventDefault();
      setError("");
      clearPasskeyStatus(); // zorg dat er niks zichtbaar is bij start

      try {
        const data = await passwordLoginWithPasskey(username, password);

        // ✅ GEEN PASSKEYS INGESTELD → GEEN MELDING, GEWOON DOOR NAAR 2FA / normale flow
        if (!data.has_passkey) {
          form.submit();
          return;
        }

        // ✅ PAS HIER: device heeft passkeys én user heeft een passkey → nu wachten-melding tonen
        setPasskeyStatus(
          "Wachten op bevestiging via passkey...",
          "waiting"
        );

        const options = data.options;
        options.challenge = b64uToArrayBuffer(options.challenge);
        if (options.allowCredentials) {
          options.allowCredentials = options.allowCredentials.map((c) => ({
            ...c,
            id: b64uToArrayBuffer(c.id),
          }));
        }

        const assertion = await navigator.credentials.get({ publicKey: options });
        if (!assertion) {
          clearPasskeyStatus();
          form.submit();
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
            userHandle: assertion.response.userHandle
              ? arrayBufferToB64u(assertion.response.userHandle)
              : null,
          },
        };

        const result = await sendAuthCredential(authResp);

        setPasskeyStatus(
          "Passkey-login geslaagd. Je wordt doorgestuurd…",
          "ok"
        );

        const redirectUrl = result.redirect_url || "/";
        window.location.href = redirectUrl;
      } catch (e) {
        console.error(e);
        clearPasskeyStatus();

        let msg;
        if (e && (e.name === "AbortError" || e.name === "NotAllowedError")) {
          // Gebruiker heeft de passkey-prompt zelf geannuleerd
          msg = "Inloggen via passkey geannuleerd.";
        } else {
          msg =
            e.message ||
            "Inloggen via passkey is mislukt. Probeer het opnieuw of gebruik je 2FA-code.";
        }

        setError(msg);
        form.submit();
      }
    });
  }

  // ---------- OFFER PASSKEY ----------
  async function checkOfferPasskey() {
    if (!onHttps || !isWebAuthnSupported() || !isMobile()) return;
    if (!window.getDeviceHash) return;

    const device_hash = await window.getDeviceHash();
    const next = window.location.pathname + window.location.search;

    const resp = await fetch("/api/passkeys/should-offer/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ device_hash, next }),
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
  });
})();