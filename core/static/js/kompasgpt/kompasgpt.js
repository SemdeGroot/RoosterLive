// core/static/js/kompasgpt/kompasgpt.js
(function () {
  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }

  function scrollChatToBottom() {
    const el = qs("#chatBox");
    if (!el) return;
    el.scrollTop = el.scrollHeight;
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

    // marked config: behoud line breaks
    if (window.marked && typeof window.marked.setOptions === "function") {
      window.marked.setOptions({
        gfm: true,
        breaks: true,     // <-- behoud enters als <br>
        mangle: false,
        headerIds: false,
      });
    }

    let html = "";
    if (window.marked) {
      html = window.marked.parse(safeMd);
    } else {
      // fallback: plain text
      html = `<div>${escapeHtml(safeMd).replace(/\n/g, "<br>")}</div>`;
    }

    if (window.DOMPurify) {
      html = window.DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
    }
    return html;
  }

  function renderAllMarkdownInHistory() {
    qsa(".js-md").forEach((el) => {
      // Pak exact de originele tekst (inclusief newlines/spaties zoals in DOM)
      const md = el.textContent ?? "";
      el.innerHTML = renderMarkdownToHtml(md);
      el.classList.add("kgpt-md-rendered");
    });
  }

  function buildSourcesDetails(sources) {
    if (!sources || !sources.length) return "";

    const items = sources.map((u) => {
      const safeU = escapeHtml(u);
      return `<a class="kgpt-source-link" href="${safeU}" target="_blank" rel="noopener noreferrer">${safeU}</a>`;
    }).join("");

    return `
      <details class="kgpt-sources">
        <summary class="kgpt-sources-summary">Bronnen (${sources.length})</summary>
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
      <div class="kgpt-bubble">${escapeHtml(content).replace(/\n/g, "<br>")}</div>
    `;
    chat.appendChild(wrap);
    scrollChatToBottom();
  }

  function appendAssistantTyping() {
    const chat = qs("#chatBox");
    if (!chat) return null;

    const wrap = document.createElement("div");
    wrap.className = "kgpt-msg kgpt-assistant kgpt-typing";
    wrap.innerHTML = `
      <div class="kgpt-meta">KompasGPT</div>
      <div class="kgpt-bubble">${thinkingHtml()}</div>
    `;
    chat.appendChild(wrap);
    scrollChatToBottom();
    return wrap;
  }

  function appendAssistantFinal(answer, sources) {
    const chat = qs("#chatBox");
    if (!chat) return;

    const wrap = document.createElement("div");
    wrap.className = "kgpt-msg kgpt-assistant";
    wrap.innerHTML = `
      <div class="kgpt-meta">KompasGPT</div>
      <div class="kgpt-bubble">
        <div class="kgpt-md js-md"></div>
      </div>
      ${buildSourcesDetails(sources)}
    `;

    chat.appendChild(wrap);

    const mdEl = wrap.querySelector(".js-md");
    if (mdEl) {
      // Zet eerst textContent (veilig) en render dan markdown -> HTML
      mdEl.textContent = answer || "";
      mdEl.innerHTML = renderMarkdownToHtml(mdEl.textContent);
    }

    scrollChatToBottom();
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
      const msg = data && data.error ? data.error : "Er ging iets mis.";
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
      appendAssistantFinal(data.answer || "", data.sources || []);
    } catch (err) {
      if (typingNode) typingNode.remove();
      appendAssistantFinal(`Fout: ${err.message}`, []);
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
        Nog geen berichten. Stel een vraag over een geneesmiddel, groepstekst of indicatie die in het Farmacotherapeutisch Kompas staat.
      </div>`;
      scrollChatToBottom();
    } catch (err) {
      appendAssistantFinal(`Fout bij wissen: ${err.message}`, []);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // 1) Render markdown van bestaande history direct bij page load
    renderAllMarkdownInHistory();

    // 2) bindings
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