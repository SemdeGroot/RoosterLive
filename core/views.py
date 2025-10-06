import os
import hashlib
import shutil
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .forms import (
    GroupWithPermsForm, SimpleUserCreateForm, SimpleUserEditForm,
    AvailabilityUploadForm, EmailOrUsernameLoginForm
)

# ===== PATHS =====
DATA_DIR = settings.DATA_DIR
MEDIA_ROOT = Path(settings.MEDIA_ROOT)
MEDIA_URL = settings.MEDIA_URL

# Cache: als settings.CACHE_DIR ontbreekt, gebruik MEDIA_ROOT/cache
# Cache basis (bestaat al)
CACHE_DIR = settings.CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Gescheiden caches
CACHE_ROSTER_DIR = CACHE_DIR / "rooster"
CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

CACHE_AVAIL_DIR = CACHE_DIR / "availability"
CACHE_AVAIL_DIR.mkdir(parents=True, exist_ok=True)

# Policies (stapelbare PDF's)
POL_DIR = MEDIA_ROOT / "policies"
POL_DIR.mkdir(parents=True, exist_ok=True)

# Gescheiden cache voor policies
CACHE_POLICIES_DIR = CACHE_DIR / "policies"
CACHE_POLICIES_DIR.mkdir(parents=True, exist_ok=True)

# Rooster (enkel huidig bestand)
ROSTER_DIR = MEDIA_ROOT / "rooster"
ROSTER_DIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = ROSTER_DIR / "rooster.pdf"

# Beschikbaarheid
AV_DIR = MEDIA_ROOT / "availability"
AV_DIR.mkdir(parents=True, exist_ok=True)

# ===== PERM LABELS =====
PERM_LABELS = {
    "can_access_admin":        "Mag beheer openen",
    "can_manage_users":        "Mag gebruikers beheren",
    "can_view_roster":         "Mag rooster bekijken",
    "can_upload_roster":       "Mag roosters uploaden",
    "can_access_availability": "Mag Beschikbaarheid openen",
    "can_view_av_medications": "Mag subtab Voorraad zien",
    "can_upload_voorraad":     "Mag Voorraad uploaden",
    "can_view_av_nazendingen": "Mag subtab Nazendingen zien",
    "can_upload_nazendingen":  "Mag Nazendingen uploaden",
    "can_view_news":           "Mag Nieuws bekijken",
    "can_upload_news": "Mag Nieuws uploaden",
    "can_view_policies":       "Mag Werkafspraken bekijken",
    "can_upload_werkafspraken": "Mag Werkafspraken uploaden",
}

def _can(user, codename):
    return user.is_superuser or user.has_perm(f"core.{codename}")

def _logo_url():
    """Zoekt het logo in MEDIA_ROOT/_data/logo.*"""
    logo_dir = settings.MEDIA_ROOT / "_data"
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        p = logo_dir / f"logo.{ext}"
        if p.exists():
            return f"{settings.MEDIA_URL}_data/logo.{ext}"
    return None

# ===== LOGIN/LOGOUT =====
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = EmailOrUsernameLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identifier"].strip().lower()
        pwd = form.cleaned_data["password"]
        username = ident
        if "@" in ident:
            u = User.objects.filter(email__iexact=ident).first()
            if u:
                username = u.username
        user = authenticate(request, username=username, password=pwd)
        if user is not None and user.is_active:
            login(request, user)
            return redirect(request.GET.get("next") or "home")
        messages.error(request, "Ongeldige inloggegevens.")

    ctx = {
        "form": form,
        "logo_url": _logo_url(),                         # bv. /media/_data/logo.png
        "bg_url": settings.MEDIA_URL + "_data/achtergrond.jpg",  # /media/_data/achtergrond.jpg
    }
    return render(request, "auth/login.html", ctx)

@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")

# ===== HOME (TEGELS) =====
@login_required
def home(request):
    tiles = []
    if _can(request.user, "can_view_roster"):
        tiles.append({"name": "Rooster", "img": "rooster.png", "url_name": "rooster"})
    if _can(request.user, "can_access_availability"):
        tiles.append({"name": "Beschikbaarheid", "img": "beschikbaarheid.png", "url_name": "availability_home"})
    if _can(request.user, "can_view_policies"):
        tiles.append({"name": "Werkafspraken", "img": "afspraken.png", "url_name": "policies"})
    if _can(request.user, "can_view_news"):
        tiles.append({"name": "Nieuws", "img": "nieuws.png", "url_name": "news"})
    if _can(request.user, "can_access_admin"):
        tiles.append({"name": "Beheer", "img": "beheer.png", "url_name": "admin_panel"})
    return render(request, "home.html", {"tiles": tiles, "logo_url": _logo_url()})

# ===== ROSTER RENDER =====
def _pdf_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]

def _clear_dir(p: Path):
    if not p.exists():
        return
    for item in p.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except Exception:
                pass

def _render_pdf_to_cache(pdf_bytes: bytes, zoom: float = 2.0, cache_root: Path = CACHE_DIR):
    """
    Render PDF -> PNG's in een submap op basis van hash binnen cache_root.
    Geeft (hash, n_pages) terug. Bestanden komen in: cache_root/<hash>/page_XXX.png
    """
    h = _pdf_hash(pdf_bytes)
    out = cache_root / h
    # Render alleen als nog niet aanwezig
    if not out.exists() or not any(out.glob("page_*.png")):
        out.mkdir(parents=True, exist_ok=True)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                (out / f"page_{i+1:03d}.png").write_bytes(pix.tobytes("png"))
    n_pages = len(list(out.glob("page_*.png")))
    return h, n_pages

@login_required
def rooster(request):
    if not _can(request.user, "can_view_roster"):
        return HttpResponseForbidden("Geen toegang tot rooster.")

    # Upload rechtstreeks vanaf index.html
    if request.method == "POST":
        if not _can(request.user, "can_upload_roster"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand (.pdf).")
            return redirect("rooster")

        # Oude rooster + cache opruimen
        _clear_dir(ROSTER_DIR)
        _clear_dir(CACHE_ROSTER_DIR)

        # Nieuw rooster opslaan
        ROSTER_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROSTER_FILE, "wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        messages.success(request, "Rooster geüpload.")
        return redirect("rooster")  # PRG: voorkomt herposten

    # GET: tonen (met of zonder rooster)
    context = {"logo_url": _logo_url(), "year": datetime.now().year}
    if not ROSTER_FILE.exists():
        context["page_urls"] = []
        context["no_roster"] = True
        return render(request, "rooster/index.html", context)

    pdf_bytes = ROSTER_FILE.read_bytes()
    h, n = _render_pdf_to_cache(pdf_bytes, zoom=2.0, cache_root=CACHE_ROSTER_DIR)
    context["page_urls"] = [
        f"{settings.MEDIA_URL}cache/rooster/{h}/page_{i:03d}.png"
        for i in range(1, n + 1)
    ]
    return render(request, "rooster/index.html", context)

@login_required
def upload_roster(request):
    if not _can(request.user, "can_upload_roster"):
        return HttpResponseForbidden("Geen uploadrechten.")
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand.")
            return redirect("upload_roster")

        # Oude rooster + cache opruimen
        _clear_dir(ROSTER_DIR)
        _clear_dir(CACHE_ROSTER_DIR)

        # Nieuw rooster opslaan
        ROSTER_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROSTER_FILE, "wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        messages.success(request, "Rooster geüpload.")
        return redirect("rooster")
    return render(request, "rooster/upload.html", {"logo_url": _logo_url()})

# ===== Beschikbaarheid helpers =====
def _read_table(fp: Path):
    try:
        if fp.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(fp)
        else:
            df = pd.read_csv(fp, sep=None, engine="python", encoding="utf-8-sig")
        df.columns = [str(c) for c in df.columns]
        return df, None
    except Exception as e:
        return None, f"Kon bestand niet lezen: {e}"

def _filter_and_limit(df, q, limit):
    if df is None:
        return df
    work = df
    if q:
        ql = q.lower()
        mask = pd.Series(False, index=work.index)
        for col in work.columns:
            try:
                mask = mask | work[col].astype(str).str.lower().str.contains(ql, na=False)
            except Exception:
                pass
        work = work[mask]
    if limit and limit > 0:
        work = work.head(limit)
    return work

def _availability_table_view(request, key: str, page_title: str, can_view_perm: str):
    """Algemene view voor tabellen (Excel/CSV)."""
    if not _can(request.user, "can_access_availability") or not _can(request.user, can_view_perm):
        return HttpResponseForbidden("Geen toegang.")

    existing_path = None
    for ext in (".xlsx", ".xls", ".csv"):
        c = AV_DIR / f"{key}{ext}"
        if c.exists():
            existing_path = c
            break

    form = AvailabilityUploadForm()
    if request.method == "POST":
        if not _can(request.user, "can_upload_voorraad"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form = AvailabilityUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            ext = (Path(f.name).suffix or "").lower()
            if ext not in (".xlsx", ".xls", ".csv"):
                messages.error(request, "Alleen CSV of Excel (XLSX/XLS) toegestaan.")
                return redirect(request.path)

            # oude bestanden wissen
            for oldext in (".xlsx", ".xls", ".csv"):
                p = AV_DIR / f"{key}{oldext}"
                if p.exists():
                    p.unlink()

            # nieuw opslaan
            dest = AV_DIR / f"{key}{ext}"
            with dest.open("wb") as fh:
                for chunk in f.chunks():
                    fh.write(chunk)

            messages.success(request, f"Bestand geüpload: {f.name}")
            return redirect(request.path)

    # tabel lezen
    df, error = None, None
    if existing_path:
        df, error = _read_table(existing_path)

    columns, rows = [], None
    if df is not None and error is None:
        columns = [str(c) for c in df.columns]
        rows = df.values.tolist()

    ctx = {
        "logo_url": _logo_url(),
        "form": form,
        "has_file": existing_path is not None,
        "file_name": existing_path.name if existing_path else None,
        "columns": columns,
        "rows": rows,
        "title": page_title,
    }

    return render(request, f"availability/{key}.html", ctx)

@login_required
def _availability_pdf_view(request, key: str, page_title: str, can_view_perm: str):
    if not _can(request.user, "can_access_availability") or not _can(request.user, can_view_perm):
        return HttpResponseForbidden("Geen toegang.")

    pdf_path = AV_DIR / f"{key}.pdf"
    cache_root = CACHE_AVAIL_DIR / key
    cache_root.mkdir(parents=True, exist_ok=True)

    # Upload
    if request.method == "POST":
        if not _can(request.user, "can_upload_nazendingen"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF-bestanden toegestaan.")
            return redirect(request.path)

        # Overschrijf oude PDF
        with pdf_path.open("wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        # LEEN ALLEEN DEZE CACHE LEEG (niet de globale)
        _clear_dir(cache_root)

        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect(request.path)

    # Geen PDF aanwezig?
    if not pdf_path.exists():
        return render(request, f"availability/{key}.html", {
            "logo_url": _logo_url(),
            "title": page_title,
            "no_nazending": True,
            "page_urls": [],
        })

    # Renderen naar eigen cache-submap
    pdf_bytes = pdf_path.read_bytes()
    h, n = _render_pdf_to_cache(pdf_bytes, zoom=2.0, cache_root=cache_root)
    page_urls = [
        f"{settings.MEDIA_URL}cache/availability/{key}/{h}/page_{i:03d}.png"
        for i in range(1, n+1)
    ]

    return render(request, f"availability/{key}.html", {
        "logo_url": _logo_url(),
        "title": page_title,
        "no_nazending": False,
        "page_urls": page_urls,
    })



@login_required
def availability_home(request):
    if not _can(request.user, "can_access_availability"):
        return HttpResponseForbidden("Geen toegang.")
    subtiles = []
    if _can(request.user, "can_view_av_medications"):
        subtiles.append({"name": "Voorraad", "img": "medicijn_zoeken.png", "url_name": "availability_medications"})
    if _can(request.user, "can_view_av_nazendingen"):
        subtiles.append({"name": "Nazendingen", "img": "nazendingen.png", "url_name": "availability_nazendingen"})
    return render(request, "availability/home.html", {"tiles": subtiles, "logo_url": _logo_url()})

@login_required
def availability_medications(request):
    return _availability_table_view(request, "medications", "Voorraad", "can_view_av_medications")

@login_required
def availability_nazendingen(request):
    return _availability_pdf_view(request, "nazendingen", "Nazendingen", "can_view_av_nazendingen")

# ===== Nieuws & Werkafspraken =====
@login_required
def news(request):
    if not _can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")
    return render(request, "news/index.html", {"logo_url": _logo_url()})

def _hash_from_img_url(img_url: str) -> str | None:
    """
    Verwacht een URL als /media/cache/policies/<hash>/page_001.png
    Geeft <hash> terug of None.
    """
    prefix = f"{settings.MEDIA_URL}cache/policies/"
    if not img_url.startswith(prefix):
        return None
    rest = img_url[len(prefix):]  # "<hash>/page_001.png"
    parts = rest.split("/")
    return parts[0] if parts else None

def _delete_policies_by_hash(hash_str: str) -> int:
    """
    Verwijder alle PDF's in POL_DIR die dezelfde content-hash hebben,
    en wis de bijbehorende cachemap cache/policies/<hash>.
    Retourneert aantal verwijderde PDF's.
    """
    removed = 0
    # 1) Cachemap opruimen
    cache_path = (CACHE_POLICIES_DIR / hash_str)
    if cache_path.exists():
        shutil.rmtree(cache_path, ignore_errors=True)

    # 2) Vind PDF's met deze hash en verwijder
    for pdf_fp in list(POL_DIR.glob("*.pdf")):
        try:
            if _pdf_hash(pdf_fp.read_bytes()) == hash_str:
                pdf_fp.unlink(missing_ok=True)
                removed += 1
        except Exception:
            pass
    return removed

@login_required
def policies(request):
    if not _can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")

    # --- Inline DELETE (AJAX op dezelfde URL) ---
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not _can(request.user, "can_upload_werkafspraken"):
            return JsonResponse({"ok": False, "error": "Geen rechten."}, status=403)
        if request.POST.get("action") != "delete":
            return JsonResponse({"ok": False, "error": "Ongeldig verzoek."}, status=400)
        img_url = request.POST.get("img", "")
        h = _hash_from_img_url(img_url)
        if not h:
            return JsonResponse({"ok": False, "error": "Ongeldige afbeelding."}, status=400)
        removed = _delete_policies_by_hash(h)
        if removed > 0:
            return JsonResponse({"ok": True, "hash": h, "removed": removed})
        else:
            return JsonResponse({"ok": False, "error": "PDF niet gevonden."}, status=404)

    # --- Upload PDF (stapelen) ---
    if request.method == "POST" and "file" in request.FILES:
        if not _can(request.user, "can_upload_werkafspraken"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF toegestaan.")
            return redirect("policies")

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = Path(str(f.name)).name.replace(" ", "_")
        dest = POL_DIR / f"{ts}__{safe_name}"
        with dest.open("wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)
        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect("policies")

    # --- GET: render alle policy-PDF’s naar PNG’s (gecentreerd) ---
    page_urls = []
    for pdf_fp in sorted(POL_DIR.glob("*.pdf")):
        try:
            pdf_bytes = pdf_fp.read_bytes()
        except Exception:
            continue
        h, n = _render_pdf_to_cache(pdf_bytes, zoom=2.0, cache_root=CACHE_POLICIES_DIR)
        # 1 hash-map per PDF; voeg alle pagina’s toe
        for i in range(1, n+1):
            page_urls.append(f"{settings.MEDIA_URL}cache/policies/{h}/page_{i:03d}.png")

    return render(request, "policies/index.html", {
        "logo_url": _logo_url(),
        "page_urls": page_urls,   # template centreert & schaalt
    })

# ===== Admin panel & Users =====
@login_required
def admin_panel(request):
    if not _can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    # ▼ 1) GET: vul form met geselecteerde groep
    editing_group = None
    gid_get = request.GET.get("group_id")
    if gid_get:
        editing_group = Group.objects.filter(pk=gid_get).first()

    # default forms
    group_form = GroupWithPermsForm(prefix="group", instance=editing_group)
    user_form  = SimpleUserCreateForm(prefix="user")

    # ▼ 2) POST: opslaan van groep (create/update)
    if request.method == "POST" and request.POST.get("form_kind") == "group":
        gid_post = request.POST.get("group_id")
        instance = Group.objects.filter(pk=gid_post).first() if gid_post else None
        group_form = GroupWithPermsForm(request.POST, instance=instance, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_panel")
        messages.error(request, "Groep opslaan mislukt.")

    # (… user_create code ongewijzigd …)
    if request.method == "POST" and request.POST.get("form_kind") == "user_create":
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Gebruiker aangemaakt.")
            return redirect("admin_panel")
        else:
            messages.error(request, "Gebruiker aanmaken mislukt.")

    groups = Group.objects.all().order_by("name")
    users = User.objects.all().order_by("username")

    group_rows = []
    for g in groups:
        codes = set(g.permissions.values_list("codename", flat=True))
        labels = [PERM_LABELS.get(c, c) for c in codes]
        labels.sort()
        member_count = g.user_set.count()
        group_rows.append({"group": g, "perm_labels": labels, "member_count": member_count})

    return render(request, "admin_panel.html", {
        "groups": groups,
        "group_rows": group_rows,
        "users": users,
        "group_form": group_form,
        "user_form": user_form,
        # ▼ 3) flags voor template
        "editing_group": bool(editing_group),
        "editing_group_id": editing_group.id if editing_group else "",
        "logo_url": _logo_url(),
    })


@login_required
@require_POST
def group_delete(request, group_id: int):
    if not _can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    g = get_object_or_404(Group, pk=group_id)
    count = g.user_set.count()
    if count > 0:
        messages.error(
            request,
            f"Kan groep “{g.name}” niet verwijderen: {count} gebruiker(s) zijn nog lid. "
            "👉 Wijs deze gebruikers eerst een andere groep toe."
        )
        return redirect("admin_panel")
    g.delete()
    messages.success(request, "Groep verwijderd.")
    return redirect("admin_panel")

@login_required
@require_POST
def user_update(request, user_id: int):
    if not _can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    form = SimpleUserEditForm(request.POST, instance=u)
    if form.is_valid():
        form.save()
        messages.success(request, "Gebruiker opgeslagen.")
    else:
        messages.error(request, "Opslaan mislukt.")
    return redirect("admin_panel")

@login_required
@require_POST
def user_delete(request, user_id: int):
    if not _can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    username = u.username
    u.delete()
    messages.success(request, f"Gebruiker “{username}” verwijderd.")
    return redirect("admin_panel")

# ===== Hash endpoint (optioneel) =====
def hash_endpoint(request):
    # Laat lege respons terugkeren om geen onnodige reloads te veroorzaken
    return HttpResponse("", content_type="text/plain")