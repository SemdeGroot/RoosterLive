// login.js
document.addEventListener("DOMContentLoaded", () => {
  const idInput = document.getElementById("id_identifier");
  if (idInput) idInput.focus();

  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                    || window.navigator.standalone === true;
  const onHttps = location.protocol === 'https:' || location.hostname === 'localhost';

  // Helpers
  const getCSRF = () => {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  };
  const b64uToBuf = (b64u) => {
    const s = b64u.replace(/-/g,'+').replace(/_/g,'/');
    const pad = s.length % 4 === 2 ? '==' : s.length % 4 === 3 ? '=' : '';
    const str = atob(s + pad);
    const buf = new ArrayBuffer(str.length);
    const view = new Uint8Array(buf);
    for (let i=0;i<str.length;i++) view[i] = str.charCodeAt(i);
    return buf;
  };
  const bufToB64u = (buf) => {
    const bytes = new Uint8Array(buf);
    let s = ''; for (let i=0;i<bytes.byteLength;i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  };

  async function tryWebAuthn(username) {
    // ⚠️ Vereist username en HTTPS; anders NIET proberen (voorkomt discoverable chooser)
    if (!onHttps) return false;
    if (!('PublicKeyCredential' in window)) return false;
    username = (username || '').trim();
    if (!username) return false;

    try {
      const csrf = getCSRF();

      // 1) begin – ALTIJD met username (non-discoverable, geen keuze-prompt)
      const res = await fetch('/webauthn/auth/begin/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ username }), // ← nooit leeg body sturen
      });
      if (!res.ok) return false;
      const options = await res.json();
      const pubKey = options.publicKey || options;

      // 2) ArrayBuffers
      pubKey.challenge = b64uToBuf(pubKey.challenge);
      if (Array.isArray(pubKey.allowCredentials)) {
        pubKey.allowCredentials = pubKey.allowCredentials.map(c => ({ ...c, id: b64uToBuf(c.id) }));
      }

      // 3) Vraag direct de platform-biometrie; mediation 'required' = geen extra UI/chooser
      const cred = await navigator.credentials.get({
        publicKey: pubKey,
        mediation: 'required'
      });

      const assertion = cred.response;
      const payload = {
        id: cred.id,
        rawId: bufToB64u(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: bufToB64u(assertion.clientDataJSON),
          authenticatorData: bufToB64u(assertion.authenticatorData),
          signature: bufToB64u(assertion.signature),
          userHandle: assertion.userHandle ? bufToB64u(assertion.userHandle) : null,
        }
      };

      // 4) complete
      const fin = await fetch('/webauthn/auth/complete/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });
      if (!fin.ok) return false;

      const data = await fin.json();
      // Username onthouden (sneller bij volgende logins)
      try {
        const u = (data && data.username) ? data.username : username;
        if (u) localStorage.setItem('lastUsername', u);
      } catch {}

      // Respecteer ?next=
      const params = new URLSearchParams(window.location.search);
      const next = params.get('next') || '/';
      window.location.assign(next);
      return true;
    } catch {
      return false;
    }
  }

  // AUTO-TRIGGER in standalone met onthouden username
  try {
    const lastUsername = localStorage.getItem('lastUsername') || '';
    if (isStandalone && lastUsername) {
      if (idInput) idInput.value = lastUsername;
      void tryWebAuthn(lastUsername); // ← start direct Face ID / passkey
    }
  } catch {}

  // (Optioneel) op Enter in het usernameveld direct WebAuthn proberen
  const form = document.querySelector('form');
  if (form && idInput) {
    idInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        void tryWebAuthn(idInput.value.trim());
      }
    });
  }
});