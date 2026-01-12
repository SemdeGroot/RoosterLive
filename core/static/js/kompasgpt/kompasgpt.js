// core/static/js/kompasgpt/kompasgpt.js
(function () {
  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }

  function scrollChatToBottom() {
    const el = qs("#chatBox");
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }

  // Alleen automatisch scrollen als user al (bijna) onderaan zit
  function isNearBottom(el, threshold = 80) {
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) < threshold;
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function getCsrfToken() {
    const el = document.querySelector("input[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function normalizeMarkdown(md) {
    const s = (md ?? "").toString();
    // Normaliseer "*" bullets naar "-" bullets (alleen begin van een regel)
    return s.replace(/^(\s*)\*\s+/gm, "$1- ");
  }

  function renderMarkdownToHtml(md) {
    const safeMd = normalizeMarkdown(md);

    if (window.marked && typeof window.marked.setOptions === "function") {
      window.marked.setOptions({
        gfm: true,
        breaks: true,
        mangle: false,
        headerIds: false,
      });
    }

    let html = "";
    if (window.marked) {
      html = window.marked.parse(safeMd);
    } else {
      html = `<div>${escapeHtml(safeMd).replace(/\n/g, "<br>")}</div>`;
    }

    if (window.DOMPurify) {
      html = window.DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
    }
    return html;
  }

  function renderAllMarkdownInHistory() {
    qsa(".js-md").forEach((el) => {
      const md = el.textContent ?? "";
      el.innerHTML = renderMarkdownToHtml(md);
      el.classList.add("kgpt-md-rendered");
    });
  }

  function buildSourcesDetails(sources) {
    if (!sources || !sources.length) return "";

    // sources = [{document, source_url, display_name, category}, ...]
    const links = sources
      .map((s) => (s && s.source_url) ? String(s.source_url) : "")
      .filter(Boolean);

    if (!links.length) return "";

    const items = links.map((url) => {
      const safeUrl = escapeHtml(url);
      return `<a class="kgpt-source-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a>`;
    }).join("");

    return `
      <details class="kgpt-sources">
        <summary class="kgpt-sources-summary">Bronnen (${links.length})</summary>
        <div class="kgpt-sources-list">${items}</div>
      </details>
    `;
  }

  function thinkingHtml() {
    return `
      <span class="kgpt-thinking" aria-label="KompasGPT is aan het denken">
        <span class="kgpt-dot"></span>
        <span class="kgpt-dot"></span>
        <span class="kgpt-dot"></span>
      </span>
    `;
  }

  function appendUserMessage(content) {
    const chat = qs("#chatBox");
    if (!chat) return;

    const empty = qs("#emptyState");
    if (empty) empty.remove();

    const wrap = document.createElement("div");
    wrap.className = "kgpt-msg kgpt-user";
    wrap.innerHTML = `
      <div class="kgpt-meta kgpt-user-meta">Jij</div>
      <div class="kgpt-bubble kgpt-bubble-user">
        ${escapeHtml(content).replace(/\n/g, "<br>")}
      </div>
    `;
    chat.appendChild(wrap);

    if (isNearBottom(chat)) scrollChatToBottom();
  }

  function appendAssistantTyping() {
    const chat = qs("#chatBox");
    if (!chat) return null;

    const empty = qs("#emptyState");
    if (empty) empty.remove();

    const wrap = document.createElement("div");
    wrap.className = "kgpt-msg kgpt-assistant kgpt-typing";
    wrap.innerHTML = `
      <div class="kgpt-meta">KompasGPT</div>
      <div class="kgpt-bubble kgpt-bubble-assistant">
        ${thinkingHtml()}
      </div>
    `;

    chat.appendChild(wrap);
    if (isNearBottom(chat)) scrollChatToBottom();
    return wrap;
  }

  /**
   * Typewriter met live markdown (woord-chunks):
   * - voegt meerdere "tokens" (woorden + spaties/newlines) per tick toe
   * - rendert markdown throttled (renderEveryMs)
   */
  async function typewriterMarkdown(
    el,
    fullMd,
    {
      wps = 40,           // words per second (hoger = sneller)
      chunkWords = 4,     // hoeveel woorden per tick (hoger = "meer in 1 keer")
      renderEveryMs = 60, // hoe vaak live markdown renderen (lager = sneller "visueel", maar duurder)
    } = {}
  ) {
    if (!el) return;

    const md = (fullMd ?? "").toString();

    // Split in "tokens" zodat spaties/newlines behouden blijven
    // Resultaat: ["Woord", " ", "Woord", "\n", ...]
    const tokens = md.match(/\S+|\s+/g) || [];
    let idx = 0;
    let buffer = "";
    let lastRender = performance.now();

    // Tick snelheid: hoeveel ticks per seconde we willen
    // (wps / chunkWords) ticks per seconde
    const ticksPerSec = Math.max(1, wps / Math.max(1, chunkWords));
    const delay = Math.max(1, Math.round(1000 / ticksPerSec));

    while (idx < tokens.length) {
      // voeg tokens toe totdat we chunkWords "woorden" hebben toegevoegd
      let wordsAdded = 0;
      while (idx < tokens.length && wordsAdded < chunkWords) {
        const t = tokens[idx++];
        buffer += t;
        if (!/^\s+$/.test(t)) wordsAdded += 1; // alleen niet-whitespace telt als "woord"
      }

      const now = performance.now();
      const timeToRender = (now - lastRender) >= renderEveryMs;
      const isDone = idx >= tokens.length;

      if (timeToRender || isDone) {
        el.innerHTML = renderMarkdownToHtml(buffer);
        lastRender = now;
      }

      await sleep(delay);
    }

  }

  async function appendAssistantFinal(answer, sources) {
    const chat = qs("#chatBox");
    if (!chat) return;

    const wasAtBottom = isNearBottom(chat);

    const wrap = document.createElement("div");
    wrap.className = "kgpt-msg kgpt-assistant";
    wrap.innerHTML = `
      <div class="kgpt-meta">KompasGPT</div>
      <div class="kgpt-bubble kgpt-bubble-assistant">
        <div class="kgpt-md js-md"></div>
      </div>
      ${buildSourcesDetails(sources)}
    `;

    chat.appendChild(wrap);

    const mdEl = wrap.querySelector(".js-md");
    if (mdEl) {
      await typewriterMarkdown(mdEl, answer || "", {
        wps: 55,        // sneller
        chunkWords: 6,  // meer woorden per "sprong"
        renderEveryMs: 50
      });
    }

    // Alleen aan het einde scrollen als user al onderaan zat
    if (wasAtBottom) scrollChatToBottom();
  }

  async function postForm(params) {
    const res = await fetch(window.location.href, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams(params),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = (data && data.error) ? data.error : "Er ging iets mis.";
      throw new Error(msg);
    }
    return data;
  }

  function setSendingState(isSending) {
    const btn = qs("#sendBtn");
    if (!btn) return;
    btn.disabled = isSending;
    btn.innerText = isSending ? "Bezig…" : "Versturen";
  }

  async function handleSubmit(e) {
    e.preventDefault();

    const messageEl = qs("#messageInput");
    const msg = (messageEl?.value || "");
    if (!msg.trim()) return;

    appendUserMessage(msg);
    messageEl.value = "";

    setSendingState(true);
    const typingNode = appendAssistantTyping();

    try {
      const data = await postForm({
        "csrfmiddlewaretoken": getCsrfToken(),
        "message": msg,
      });

      if (typingNode) typingNode.remove();
      await appendAssistantFinal(data.answer || "", data.sources || []);
    } catch (err) {
      if (typingNode) typingNode.remove();
      await appendAssistantFinal(`**Fout:** ${err.message}`, []);
    } finally {
      setSendingState(false);
    }
  }

  async function handleClear() {
    const chat = qs("#chatBox");
    if (!chat) return;

    const ok = confirm("Weet je zeker dat je de chat wilt wissen?");
    if (!ok) return;

    try {
      await postForm({
        "csrfmiddlewaretoken": getCsrfToken(),
        "action": "clear",
      });

      chat.innerHTML = `<div class="kgpt-empty" id="emptyState">
        Stel een vraag over een geneesmiddel, groepstekst of indicatie die in het Farmacotherapeutisch Kompas staat.
      </div>`;
      scrollChatToBottom();
    } catch (err) {
      await appendAssistantFinal(`**Fout bij wissen:** ${err.message}`, []);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // bestaande history renderen
    renderAllMarkdownInHistory();

    const form = qs("#chatForm");
    const clearBtn = qs("#clearBtn");
    const messageEl = qs("#messageInput");

    // Enter = send, Shift+Enter = newline
    if (messageEl) {
      messageEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          const f = qs("#chatForm");
          if (f) f.requestSubmit();
        }
      });
    }

    if (form) form.addEventListener("submit", handleSubmit);
    if (clearBtn) clearBtn.addEventListener("click", handleClear);

    scrollChatToBottom();
  });
})();