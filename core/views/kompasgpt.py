# core/views/kompasgpt.py
import os
from typing import List, Dict, Tuple
import re
import random
import time
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from google import genai
from google.genai import types

from core.views._helpers import can
from django.core.cache import cache

DOCMETA_TTL = 30 * 60  # 0.5 uur
DOCMETA_KEY_PREFIX = "kompas:docmeta:"

_DOC_RE = re.compile(r"^fileSearchStores/[^/]+/documents/[^/]+$")
_BRON_LINE_RE = re.compile(r"^\*\*Bron:\*\*\s*(https?://\S+)\s*$", re.MULTILINE)

def _extract_doc_names_from_response(resp) -> list[str]:
    doc_names: list[str] = []

    try:
        candidates = getattr(resp, "candidates", None) or []
        if not candidates:
            return []

        c0 = candidates[0]
        gm = getattr(c0, "grounding_metadata", None)
        if not gm:
            return []

        chunks = getattr(gm, "grounding_chunks", None) or []
        for ch in chunks:
            rc = getattr(ch, "retrieved_context", None)
            if not rc:
                continue

            uri = getattr(rc, "uri", None) or getattr(rc, "document_name", None)
            if not uri:
                continue

            # normaliseer naar .../documents/<id> als er extra pad aan hangt
            if "/documents/" in uri and not _DOC_RE.match(uri):
                base, rest = uri.split("/documents/", 1)
                doc_id = rest.split("/", 1)[0]
                uri = f"{base}/documents/{doc_id}"

            if _DOC_RE.match(uri):
                doc_names.append(uri)

    except Exception:
        pass

    # dedupe keep order
    seen = set()
    out: list[str] = []
    for d in doc_names:
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out

def _extract_source_urls_from_grounding_text(resp) -> list[str]:
    """
    Fallback: zoek '**Bron:** <url>' in de opgehaalde chunk-teksten.
    """
    urls: list[str] = []
    try:
        candidates = getattr(resp, "candidates", None) or []
        if not candidates:
            return []

        c0 = candidates[0]
        gm = getattr(c0, "grounding_metadata", None)
        if not gm:
            return []

        chunks = getattr(gm, "grounding_chunks", None) or []
        for ch in chunks:
            rc = getattr(ch, "retrieved_context", None)
            if not rc:
                continue
            txt = getattr(rc, "text", None) or ""
            for m in _BRON_LINE_RE.finditer(txt):
                u = (m.group(1) or "").strip()
                if u:
                    urls.append(u)
    except Exception:
        return []

    # dedupe keep order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def _docmeta_cached(client, doc_name: str) -> dict:
    key = DOCMETA_KEY_PREFIX + doc_name
    cached = cache.get(key)
    if cached:
        return cached

    doc = client.file_search_stores.documents.get(name=doc_name)

    md = getattr(doc, "custom_metadata", None) or getattr(doc, "customMetadata", None) or []
    meta = {}
    for kv in md:
        k = getattr(kv, "key", None) or (kv.get("key") if isinstance(kv, dict) else None)
        v = (
            getattr(kv, "string_value", None)
            or getattr(kv, "stringValue", None)
            or (kv.get("string_value") if isinstance(kv, dict) else None)
            or (kv.get("stringValue") if isinstance(kv, dict) else None)
        )
        if k and v:
            meta[k] = v

    payload = {
        "document": doc_name,
        "source_url": meta.get("source_url"),
        "category": meta.get("category"),
        "atc": meta.get("atc"),
        "display_name": getattr(doc, "display_name", None) or getattr(doc, "displayName", None),
    }
    cache.set(key, payload, timeout=DOCMETA_TTL)
    return payload

def _merge_and_dedupe_sources(doc_sources: list[dict], fallback_urls: list[str]) -> list[dict]:
    """
    Dedupe op source_url. Docmeta heeft voorrang (bevat category/display_name/atc).
    """
    out: list[dict] = []
    seen = set()

    # 1) eerst doc sources (rijker)
    for s in doc_sources or []:
        url = (s or {}).get("source_url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(s)

    # 2) daarna fallback-only urls
    for u in fallback_urls or []:
        if not u or u in seen:
            continue
        seen.add(u)
        out.append({
            "document": None,
            "source_url": u,
            "category": None,
            "atc": None,
            "display_name": None,
        })

    return out

def _unique_sources_with_metadata(client, doc_names: list[str]) -> list[dict]:
    out = []
    seen_urls = set()
    seen_docs = set()

    for name in doc_names:
        if not name or name in seen_docs:
            continue
        seen_docs.add(name)

        meta = _docmeta_cached(client, name)
        url = meta.get("source_url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        out.append(meta)

    return out


def _format_history_for_prompt(history: List[Dict], max_turns: int = 8) -> str:
    """
    Neem laatste N messages mee zodat doorvragen werkt.
    We nemen user+assistant beurtjes mee als tekst.
    """
    h = history[-max_turns:] if max_turns and len(history) > max_turns else history

    lines = []
    for m in h:
      role = m.get("role")
      content = (m.get("content") or "").strip()
      if not content:
        continue
      if role == "user":
        lines.append(f"Gebruiker: {content}")
      else:
        lines.append(f"Assistent: {content}")
    return "\n".join(lines).strip()

def _should_retry_gemini_exc(e: Exception) -> bool:
    msg = str(e).lower()
    return (
        "503" in msg
        or "unavailable" in msg
        or "overloaded" in msg
        or "resource_exhausted" in msg
        or "429" in msg
        or "internal" in msg
        or "500" in msg
        or "502" in msg
        or "504" in msg
    )

def _generate_with_retry(client, *, model: str, contents: str, config, attempts: int = 5, base_sleep: float = 1.0):
    last = None
    for i in range(attempts):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            last = e
            if not _should_retry_gemini_exc(e) or i == attempts - 1:
                raise
            # 1s, 2s, 4s, 8s... (max 10s) + beetje jitter
            sleep_s = min(base_sleep * (2 ** i), 10.0) + random.uniform(0, 0.4)
            time.sleep(sleep_s)
    raise last  # theoretisch

def _ask_gemini_with_store(question: str, history: List[Dict]) -> Tuple[str, List[dict]]:
    api_key = os.getenv("GOOGLE_API_KEY")
    store_name = os.getenv("GEMINI_STORE_ID")  # "fileSearchStores/...."

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY ontbreekt in env.")
    if not store_name:
        raise RuntimeError("GEMINI_STORE_ID ontbreekt in env (verwacht: fileSearchStores/<id>).")

    client = genai.Client(api_key=api_key)

    history_text = _format_history_for_prompt(history, max_turns=8)

    system_rules = (
        "Je bent KompasGPT. Gebruik uitsluitend informatie uit de opgehaalde passages "
        "van het Farmacotherapeutisch Kompas.\n"
        "Als de passages onvoldoende informatie bevatten, zeg dan duidelijk dat je het niet zeker weet "
        "op basis van de bronnen en geef alleen wat je wél kunt afleiden uit de bronnen.\n"
        "Schrijf je antwoord in Markdown.\n"
        "Noem geen dingen die niet in de bronnen staan.\n"
    )

    prompt = (
        f"{system_rules}\n"
        f"Chatgeschiedenis (samenvatting/laatste berichten):\n{history_text}\n\n"
        f"Nieuwe vraag van gebruiker:\n{question}\n"
    )

    config = types.GenerateContentConfig(
        temperature=0.2,
        tools=[
            types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[store_name]
                )
            )
        ],
    )

    resp = _generate_with_retry(
        client,
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
        attempts=4, # max 4 pogingen
        base_sleep=1.0, # start met 1sec, verhoogt exponentieel
    )

    text = getattr(resp, "text", None)
    answer = (text or "").strip() or str(resp)

    doc_names = _extract_doc_names_from_response(resp)
    doc_sources = _unique_sources_with_metadata(client, doc_names)
    fallback_urls = _extract_source_urls_from_grounding_text(resp)
    sources = _merge_and_dedupe_sources(doc_sources, fallback_urls)

    return answer, sources

@login_required
@require_http_methods(["GET", "POST"])
def kompasgpt(request):
    if not can(request.user, "can_view_kompasgpt"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    history = request.session.get("kompasgpt_history", [])
    if not isinstance(history, list):
        history = []

    error = None

    if request.method == "POST":
        is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        action = (request.POST.get("action") or "").strip().lower()
        if action == "clear":
            request.session["kompasgpt_history"] = []
            if is_xhr:
                return JsonResponse({"ok": True})
            return render(request, "kompasgpt/index.html", {
                "page_title": "KompasGPT",
                "history": [],
                "error": None,
            })

        user_msg = (request.POST.get("message") or "").strip()
        if not user_msg:
            if is_xhr:
                return JsonResponse({"error": "Typ eerst een vraag."}, status=400)
            error = "Typ eerst een vraag."
        else:
            history.append({"role": "user", "content": user_msg})

            try:
                answer, sources = _ask_gemini_with_store(question=user_msg, history=history)
                history.append({"role": "assistant", "content": answer, "sources": sources})
            except Exception as e:
                error = str(e)
                history.append({"role": "assistant", "content": f"**Fout:** {error}", "sources": []})

            history_for_session = [
                {"role": h["role"], "content": h["content"]} 
                for h in history[-8:]
            ]
            request.session["kompasgpt_history"] = history_for_session

            if is_xhr:
                last = history[-1] if history else {}
                return JsonResponse({
                    "answer": last.get("content", ""),
                    "sources": last.get("sources", []) or [],
                })

    return render(request, "kompasgpt/index.html", {
        "page_title": "KompasGPT",
        "history": history,
        "error": error,
    })