# app.py
# Donkere rooster-app (PDF → PNG's, geen embed)
# - Render server-side met PyMuPDF
# - Geen auto-refresh; client checkt periodiek /hash en herlaadt ALLEEN bij wijziging
# - Brede logo-weergave uit ./data/logo.*
# - Config via .env

import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
import fitz  # PyMuPDF
from flask import Flask, render_template_string, send_from_directory, abort, Response
from dotenv import load_dotenv

# === Config ===
load_dotenv()
ROOSTER_FILE_ID = os.getenv("ROOSTER_FILE_ID", "").strip()  # mag Drive-URL of alleen ID zijn
PORT = int(os.getenv("PORT", "5000"))
HASH_POLL_SECONDS = int(os.getenv("HASH_POLL_SECONDS", "60"))

app = Flask(__name__)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# ---------- Helpers ----------
def extract_id(maybe_url: str) -> str:
    if not maybe_url:
        return ""
    m = re.search(r"/file/d/([A-Za-z0-9_\-]{10,})", maybe_url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_\-]{10,}", maybe_url):
        return maybe_url
    return ""

def parse_drive_info(inp: str):
    """Return (file_id, resourcekey|None) from Drive URL or ID."""
    fid = extract_id(inp) or inp
    rkey = None
    if inp.startswith("http"):
        qs = parse_qs(urlparse(inp).query)
        if "resourcekey" in qs and qs["resourcekey"]:
            rkey = qs["resourcekey"][0]
    return fid, rkey

def _is_pdf_response(resp: requests.Response) -> bool:
    ct = (resp.headers.get("Content-Type") or "").lower()
    return ct.startswith("application/pdf") or resp.content.startswith(b"%PDF")

def fetch_pdf_bytes(file_id_or_url: str) -> bytes:
    """Robuust downloaden zonder Drive API (usercontent + uc confirm-flow)."""
    if not file_id_or_url:
        abort(400, "ROOSTER_FILE_ID ontbreekt.")
    fid, rkey = parse_drive_info(file_id_or_url)

    urls = []
    base_usercontent = f"https://drive.usercontent.google.com/download?id={fid}&export=download"
    if rkey:
        base_usercontent += f"&resourcekey={rkey}"
    urls.append(base_usercontent)

    base_uc = f"https://drive.google.com/uc?export=download&id={fid}"
    if rkey:
        base_uc += f"&resourcekey={rkey}"
    urls.append(base_uc)

    s = requests.Session()
    for url in urls:
        r = s.get(url, timeout=60, allow_redirects=True)
        if _is_pdf_response(r):
            return r.content
        # Grote-bestand confirm-token (uc).
        if "uc?export=download" in url and "text/html" in (r.headers.get("Content-Type") or "").lower():
            m = re.search(r'confirm=([0-9A-Za-z_]+)', r.text) or re.search(r'name="confirm"\s+value="([0-9A-Za-z_]+)"', r.text)
            if m:
                confirm = m.group(1)
                r2 = s.get(f"{base_uc}&confirm={confirm}", timeout=60, allow_redirects=True)
                if _is_pdf_response(r2):
                    return r2.content

    abort(502, "Kon PDF niet downloaden. Zet het bestand op 'Anyone with the link can view'.")

def pdf_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]

def render_pdf_to_cache(pdf_bytes: bytes, zoom: float = 2.0):
    """Render PDF → PNG's in cache/<hash>/page_XXX.png. Return (hash, num_pages)."""
    h = pdf_hash(pdf_bytes)
    out_dir = CACHE_DIR / h
    if not out_dir.exists() or not any(out_dir.glob("page_*.png")):
        out_dir.mkdir(parents=True, exist_ok=True)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                (out_dir / f"page_{i+1:03d}.png").write_bytes(pix.tobytes("png"))
    num_pages = len(list(out_dir.glob("page_*.png")))
    return h, num_pages

def find_local_logo() -> str | None:
    for ext in ("jpg", "jpeg", "png", "svg", "webp", "gif"):
        p = Path("data") / f"logo.{ext}"
        if p.exists():
            return f"/data/logo.{ext}"
    return None

# ---------- Static serving ----------
@app.route("/data/<path:filename>")
def serve_data(filename):
    return send_from_directory("data", filename)

@app.route("/cache/<doc_hash>/<path:filename>")
def serve_cache(doc_hash, filename):
    return send_from_directory(CACHE_DIR / doc_hash, filename)

# ---------- Views ----------
HTML = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Rooster • Apotheek Jansen</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --bg:#0b0f14; --panel:#10161d; --panel-2:#0f141a; --text:#e6edf3; --muted:#9fb2c8; --border:#233041; --shadow:rgba(0,0,0,.55); }
    * { box-sizing: border-box; }
    html, body { height:100%; margin:0; background:var(--bg); color:var(--text); font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, "Helvetica Neue", Arial, "Noto Sans", sans-serif; }
    .app { display:grid; grid-template-rows:auto 1fr auto; min-height:100dvh; }

    .header {
    position: sticky;
    top: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    gap: 20px;
    background: linear-gradient(180deg, var(--panel), rgba(16,22,29,.85));
    backdrop-filter: blur(6px);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px; /* meer padding rondom */
    box-shadow: 0 4px 14px var(--shadow);
    }

    .logo-wrap {
    background: #fff;         /* witte achtergrond */
    padding: 10px 16px;       /* lucht rondom */
    border-radius: 16px;      /* afgeronde hoeken */
    display: flex;
    align-items: center;
    justify-content: center;
    }

    .logo {
    max-height: 45px;         /* groter */
    width: auto;
    object-fit: contain;
    display: block;
    }

    .title {
    font-size: 1.8rem;   /* maak groter, bv. 28-30px */
    font-weight: 700;    /* extra dik */
    letter-spacing: 0.5px;
    }

    .content { padding:18px; display:grid; gap:18px; }
    .card { background:linear-gradient(180deg, var(--panel), var(--panel-2)); border:1px solid var(--border); border-radius:16px; box-shadow:0 8px 24px var(--shadow); overflow:hidden; }
    .card-head { display:flex; align-items:center; justify-content:space-between; padding:14px 16px; border-bottom:1px solid var(--border); }
    .pages { display:grid; gap:12px; padding:16px; }
    .page { width:100%; border:1px solid var(--border); border-radius:12px; background:#0a0f14; box-shadow:0 4px 12px var(--shadow); overflow:hidden; }
    .page img { display:block; width:100%; height:auto; }

    .footer { position:sticky; bottom:0; z-index:1000; display:flex; justify-content:space-between; align-items:center; gap:6px;
      padding:8px 10px; background:linear-gradient(0deg, var(--panel), rgba(16,22,29,.85)); border-top:1px solid var(--border); box-shadow:0 -4px 14px var(--shadow); color:var(--muted); font-size:12px; }
  </style>
</head>
<body>
  <div class="app">
    <header class="header">
    {% if logo_url %}<div class="logo-wrap"><img class="logo" src="{{ logo_url }}" alt="Apotheek Jansen logo"></div>{% endif %}
    <div class="title">Rooster</div>
    </header>

    <main class="content">
      <div class="card">
        <div class="pages">
          {% for url in page_urls %}
            <div class="page"><img src="{{ url }}" alt="Rooster pagina {{ loop.index }}" loading="lazy"></div>
          {% endfor %}
        </div>
      </div>
    </main>

    <footer class="footer">
      <div>© {{ year }} Sem de Groot</div>
      <div></div>
    </footer>
  </div>

  <script>
    // Alleen herladen wanneer hash verandert
    const initialHash = "{{ doc_hash }}";
    const intervalSec = {{ hash_poll }};
    async function checkHash() {
      try {
        const r = await fetch("/hash", { cache: "no-store" });
        if (r.ok) {
          const latest = (await r.text()).trim();
          if (latest && latest !== initialHash) {
            location.reload();
          }
        }
      } catch (e) { /* stil falen */ }
    }
    setInterval(checkHash, intervalSec * 1000);
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    if not ROOSTER_FILE_ID:
        abort(400, "Zet ROOSTER_FILE_ID in je .env (Drive file-id of volledige publieke URL).")

    # Download PDF en render (of hergebruik cache) voor huidige view
    pdf_bytes = fetch_pdf_bytes(ROOSTER_FILE_ID)
    doc_hash, num_pages = render_pdf_to_cache(pdf_bytes, zoom=2.0)

    page_urls = [f"/cache/{doc_hash}/page_{i:03d}.png" for i in range(1, num_pages + 1)]
    logo_url = find_local_logo()

    return render_template_string(
        HTML,
        year=datetime.now().year,
        page_urls=page_urls,
        logo_url=logo_url,
        doc_hash=doc_hash,
        hash_poll=HASH_POLL_SECONDS
    )

@app.route("/hash")
def hash_endpoint():
    """Geeft de actuele hash van de PDF-inhoud terug (zonder render)."""
    if not ROOSTER_FILE_ID:
        return Response("", mimetype="text/plain")
    try:
        pdf_bytes = fetch_pdf_bytes(ROOSTER_FILE_ID)
        return Response(pdf_hash(pdf_bytes), mimetype="text/plain")
    except Exception:
        # Bij fout: geen reload forceren
        return Response("", mimetype="text/plain")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))  # fallback naar 5000 lokaal
    app.run(host="0.0.0.0", port=port, debug=True)