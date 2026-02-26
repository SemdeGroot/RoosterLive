# core/views/kompasgpt.py
import os
import re
from typing import List, Dict, Tuple
import random
import time
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from google import genai
from google.genai import types

from core.models import ScrapedPage
from core.views._helpers import can

_BRON_LINE_RE = re.compile(r"^\*\*Bron:\*\*\s*(https?://\S+)\s*$", re.MULTILINE)


def _extract_chunk_titles_from_response(resp) -> list[str]:
    titles = []
    seen = set()
    try:
        for ch in resp.candidates[0].grounding_metadata.grounding_chunks or []:
            t = getattr(ch.retrieved_context, "title", None)
            if t and t not in seen:
                seen.add(t)
                titles.append(t)
    except Exception:
        pass
    return titles


def _fallback_urls_from_chunks(resp) -> list[str]:
    urls = []
    seen = set()
    try:
        for ch in resp.candidates[0].grounding_metadata.grounding_chunks or []:
            txt = getattr(ch.retrieved_context, "text", None) or ""
            for m in _BRON_LINE_RE.finditer(txt):
                u = m.group(1).strip()
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
    except Exception:
        pass
    return urls


def _sources_from_chunk_titles(titles: list[str], resp=None) -> list[dict]:
    if not titles:
        return []
    try:
        pages = {
            p.title: p
            for p in ScrapedPage.objects.filter(title__in=titles)
        }
        sources = [
            {"source_url": p.url, "category": p.category, "display_name": title}
            for title in titles
            if (p := pages.get(title))
        ]
        if sources:
            return sources
    except Exception:
        pass

    # Fallback bij DB-fout of geen resultaten
    if resp is not None:
        return [
            {"source_url": u, "category": None, "display_name": None}
            for u in _fallback_urls_from_chunks(resp)
        ]
    return []


def _format_history_for_prompt(history: List[Dict], max_turns: int = 8) -> str:
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
        "503" in msg or "unavailable" in msg or "overloaded" in msg
        or "resource_exhausted" in msg or "429" in msg
        or "internal" in msg or "500" in msg or "502" in msg or "504" in msg
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
            sleep_s = min(base_sleep * (2 ** i), 10.0) + random.uniform(0, 0.4)
            time.sleep(sleep_s)
    raise last


def _ask_gemini_with_store(question: str, history: List[Dict]) -> Tuple[str, List[dict]]:
    api_key = os.getenv("GOOGLE_API_KEY")
    store_name = os.getenv("GEMINI_STORE_ID")

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY ontbreekt in env.")
    if not store_name:
        raise RuntimeError("GEMINI_STORE_ID ontbreekt in env (verwacht: fileSearchStores/<id>).")

    client = genai.Client(api_key=api_key)

    history_text = _format_history_for_prompt(history, max_turns=8)

    system_rules = (
        "Je bent ApotheekGPT. Gebruik uitsluitend informatie uit de opgehaalde passages "
        "van het Farmacotherapeutisch Kompas en het Nederlands Huisartsen Genootschap (NHG).\n"
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
        attempts=4,
        base_sleep=1.0,
    )

    answer = (getattr(resp, "text", None) or "").strip() or str(resp)
    titles = _extract_chunk_titles_from_response(resp)
    sources = _sources_from_chunk_titles(titles, resp=resp)

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

            request.session["kompasgpt_history"] = [
                {"role": h["role"], "content": h["content"]}
                for h in history[-8:]
            ]

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