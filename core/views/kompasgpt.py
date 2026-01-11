import os
from typing import List, Dict, Tuple

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from google import genai
from google.genai import types

from core.views._helpers import can


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


def _extract_sources_from_response(resp) -> List[str]:
    """
    Probeert links/uri’s te halen uit grounding metadata.
    Dit is 'best effort' omdat SDK structs kunnen verschillen per versie.
    """
    urls = []

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
            # vaak: ch.web.uri of ch.retrieved_context.uri etc.
            web = getattr(ch, "web", None)
            if web:
                uri = getattr(web, "uri", None)
                if uri:
                    urls.append(uri)

            rc = getattr(ch, "retrieved_context", None)
            if rc:
                uri = getattr(rc, "uri", None)
                if uri:
                    urls.append(uri)

        # fallback: sommige structs hebben 'sources'
        srcs = getattr(gm, "sources", None) or []
        for s in srcs:
            uri = getattr(s, "uri", None) or getattr(s, "url", None)
            if uri:
                urls.append(uri)

    except Exception:
        pass

    # dedupe keep order
    seen = set()
    out = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _ask_gemini_with_store(question: str, history: List[Dict]) -> Tuple[str, List[str]]:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    store_name = os.getenv("GEMINI_STORE_ID")  # "fileSearchStores/...."

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY (of GEMINI_API_KEY) ontbreekt in env.")
    if not store_name:
        raise RuntimeError("GEMINI_STORE_ID ontbreekt in env (verwacht: fileSearchStores/<id>).")

    client = genai.Client(api_key=api_key)

    history_text = _format_history_for_prompt(history, max_turns=10)

    system_rules = (
        "Je bent KompasGPT. Gebruik uitsluitend informatie uit de opgehaalde passages "
        "van het Farmacotherapeutisch Kompas via de File Search tool.\n"
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

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )

    text = getattr(resp, "text", None)
    answer = (text or "").strip() or str(resp)
    sources = _extract_sources_from_response(resp)
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

            history = history[-30:]  # wat ruimer, zodat doorvragen werkt
            request.session["kompasgpt_history"] = history

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