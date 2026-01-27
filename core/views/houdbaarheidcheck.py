from __future__ import annotations

import os
import re
import sqlite3
from typing import List, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from core.forms import HoudbaarheidCheckForm
from core.views._helpers import can


# lookup.db staat in BASE_DIR/lookup.db (zelfde patroon als je utils)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # -> .../core
BASE_DIR = os.path.dirname(BASE_DIR)  # -> project root
DB_PATH = os.path.join(BASE_DIR, "lookup.db")


def _norm_rvg(rvg: str) -> str:
    """
    Leading-zero onafhankelijk:
    - haal alles behalve cijfers weg
    - strip leading zeros
    - lege string -> ""
    """
    if not rvg:
        return ""
    digits = re.sub(r"\D+", "", rvg.strip())
    if digits == "":
        return ""
    normalized = digits.lstrip("0")
    return normalized if normalized != "" else "0"


def _query_houdbaarheid(rvg_input: str, category: int = 118) -> Tuple[str, List[str], List[str]]:
    """
    Returns:
      (rvg_norm, namen, teksten)
    """
    rvg_norm = _norm_rvg(rvg_input)
    if not rvg_norm:
        return "", [], []

    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"lookup.db niet gevonden op {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Veiligheids-PRAGMAs (read-only gedrag)
        cur.execute("PRAGMA query_only = ON;")
        cur.execute("PRAGMA temp_store = MEMORY;")

        rows = cur.execute(
            """
            SELECT DISTINCT
                n.nmnaam AS naam,
                t.bbetom AS tekst
            FROM g_bst004_articles a
            LEFT JOIN g_bst020_names n
                ON n.nmnr = a.atnmnr
            JOIN g_bst351_hpk_bbetnr hb
                ON hb.hpkode = a.hpkode
            JOIN g_bst371_bbetnr_category c
                ON c.bbetnr = hb.bbetnr AND c.bbtcnr = ?
            JOIN g_bst362_bbetnr_text t
                ON t.bbetnr = hb.bbetnr
            WHERE a.rvg_norm = ?
            ORDER BY n.nmnaam, t.bbetom
            """,
            (category, rvg_norm),
        ).fetchall()

        namen: List[str] = []
        teksten: List[str] = []

        seen_n = set()
        seen_t = set()

        for r in rows:
            naam = (r["naam"] or "").strip()
            tekst = (r["tekst"] or "").strip()
            if naam and naam not in seen_n:
                seen_n.add(naam)
                namen.append(naam)
            if tekst and tekst not in seen_t:
                seen_t.add(tekst)
                teksten.append(tekst)

        return rvg_norm, namen, teksten
    finally:
        conn.close()


@login_required
def houdbaarheidcheck(request):
    # Permissiecontrole
    if not can(request.user, "can_edit_houdbaarheidcheck"):
        return HttpResponseForbidden("Je hebt geen rechten om de Houdbaarheid Check uit te voeren.")

    form = HoudbaarheidCheckForm(request.GET or None)

    rvg_norm: str = ""
    namen: List[str] = []
    teksten: List[str] = []
    searched = False

    # GET-form: als bound (dus er is gezocht)
    if form.is_bound:
        searched = True

        if not form.is_valid():
            # zoals je andere views: één generieke message
            messages.error(request, "Controleer de invoer van het formulier.")
        else:
            try:
                rvg_input = form.cleaned_data["rvg"]
                rvg_norm, namen, teksten = _query_houdbaarheid(rvg_input, category=118)

                if not namen and not teksten:
                    messages.warning(request, "Geen houdbaarheidstekst gevonden voor dit RVG nummer.")
            except Exception as e:
                messages.error(request, f"Er ging iets mis bij het opzoeken: {e}")

    context = {
        "title": "Houdbaarheid Check",
        "form": form,
        "rvg_norm": rvg_norm,
        "namen": namen,
        "teksten": teksten,
        "searched": searched,
    }
    return render(request, "houdbaarheidcheck/index.html", context)
