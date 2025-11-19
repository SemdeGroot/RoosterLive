// static/js/auth/passkeys.js
(function () {
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';

  function isMobile() {
    const ua = navigator.userAgent || "";
    return /Android|iPhone|iPad|iPod/i.test(ua);
  }

  function isWebAuthnSupported() {
    return (
      typeof window.PublicKeyCredential !== "undefined" &&
      typeof window.navigator.credentials !== "undefined" &&
      typeof window.navigator.credentials.get === "function"
    );
  }

  // ---------- device_hash (gekopieerd uit base.js) ----------
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

  // Globaal beschikbaar maken
  if (!window.getDeviceHash) {
    window.getDeviceHash = getDeviceHash;
  }

  // ---------- helpers ----------
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
      throw new Error("Kan registratie-opties niet ophalen");
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
      throw new Error(data.error || "Passkey registratie mislukt");
    }
    return data;
  }

  window.setupPasskey = async function (nextUrl, msgEl) {
    const target = msgEl || document.getElementById("passkeyMessage");

    const setMsg = (txt, type) => {
      if (!target) return;
      target.textContent = txt || "";

      // basisclass
      let cls = "passkey-message";
      if (type === "ok") {
        cls += " ok";
      } else if (type === "error") {
        cls += " error";
      }
      target.className = cls;

      // alleen ruimte innemen als er tekst is
      target.style.display = txt ? "block" : "none";
    };

    if (!onHttps) {
      setMsg("Passkeys werken alleen via HTTPS of op localhost.", "error");
      return;
    }
    if (!isWebAuthnSupported()) {
      setMsg("Dit apparaat ondersteunt geen passkeys.", "error");
      return;
    }

    try {
      setMsg("Passkey instellen, even wachten..."); // neutraal, muted

      const options = await prepareRegisterOptions();
      const cred = await navigator.credentials.create({ publicKey: options });
      if (!cred) {
        setMsg("Passkey instellen is afgebroken.", "error");
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
      setMsg("Passkey is ingesteld. Je wordt doorgestuurd...", "ok");
      window.location.href = nextUrl || "/";
    } catch (e) {
      console.error(e);
      setMsg("Passkey instellen is mislukt: " + e.message, "error");
    }
  };

    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      const err = (data && data.error) || "Login mislukt";
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
      throw new Error(data.error || "Authenticatie mislukt");
    }
    return data;
  }

  function findLoginForm() {
  // Eerst proberen de "mooie" variant, daarna fallbacks
  return (
    document.querySelector("main.login-app form") || // als je die hebt
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

  // Alleen op stap 1 (username + password), niet op 2FA-pagina
  if (!usernameInput || !passwordInput) return;

  // ⬇️ HIER: alleen doorgaan op mobiel + HTTPS + WebAuthn
  if (!onHttps || !isWebAuthnSupported() || !isMobile()) {
    return; // desktop of geen WebAuthn → normale 2FA-flow
  }

  const errorContainerId = "passkeyLoginError";
  let errorEl = document.getElementById(errorContainerId);
  if (!errorEl) {
    errorEl = document.createElement("p");
    errorEl.id = errorContainerId;
    errorEl.className = "twofa-logintext muted";
    errorEl.style.color = "#ff7f7f";
    errorEl.style.marginTop = "0.5rem";
    passwordInput.parentNode.insertAdjacentElement("afterend", errorEl);
  }

  const setError = (txt) => {
    errorEl.textContent = txt || "";
  };

  form.addEventListener("submit", async (ev) => {
    const username = (usernameInput.value || "").trim();
    const password = passwordInput.value || "";

    if (!username || !password) {
      setError("");
      return; // normale submit, Django regelt het
    }

    ev.preventDefault();
    setError("");

    try {
      const data = await passwordLoginWithPasskey(username, password);

      if (!data.has_passkey) {
        // user/device heeft geen passkey -> normale 2FA-flow
        form.submit();
        return;
      }

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
      const redirectUrl = result.redirect_url || "/";
      window.location.href = redirectUrl;
    } catch (e) {
      console.error(e);
      setError(
        e.message ||
          "Biometrisch inloggen is niet gelukt. Probeer het opnieuw of gebruik je 2FA-code."
      );
      form.submit();
    }
  });
}

  // ---------- EERSTE LOGIN → PASSKEY-SETUP ----------

  async function checkOfferPasskey() {
    if (!onHttps || !isWebAuthnSupported() || !isMobile()) {
      return;
    }
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

  // Publieke hooks
  window._passkeys = window._passkeys || {};
  window._passkeys.tryPasskeyOnLoginForm = tryPasskeyOnLoginForm;
  window._passkeys.checkOfferPasskey = checkOfferPasskey;

  document.addEventListener("DOMContentLoaded", () => {
    // login-pagina
    tryPasskeyOnLoginForm();
  });
});