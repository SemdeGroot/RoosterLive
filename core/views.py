import os
import re
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
from django.contrib.auth.models import User, Group, Permission
from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .forms import (
    GroupWithPermsForm, SimpleUserCreateForm, SimpleUserEditForm,
    AvailabilityUploadForm, EmailOrUsernameLoginForm
)

# ===== PATHS =====
DATA_DIR = settings.DATA_DIR
MEDIA_ROOT = settings.MEDIA_ROOT
CACHE_DIR = settings.CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rooster enkel-bestand
ROSTER_DIR = Path(MEDIA_ROOT) / "rooster"
ROSTER_DIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = ROSTER_DIR / "rooster.pdf"

# Beschikbaarheid
AV_DIR = Path(MEDIA_ROOT) / "availability"
AV_DIR.mkdir(parents=True, exist_ok=True)

# ===== PERM LABELS =====
PERM_LABELS = {
    "can_access_admin":        "Mag beheer openen",
    "can_manage_users":        "Mag gebruikers beheren",
    "can_view_roster":         "Mag rooster bekijken",
    "can_upload_roster":       "Mag roosters uploaden",
    "can_access_availability": "Mag Beschikbaarheid openen",
    "can_view_av_medications": "Mag subtab Geneesmiddelen zien",
    "can_view_av_nazendingen": "Mag subtab Nazendingen zien",
    "can_view_news":           "Mag Nieuws bekijken",
    "can_view_policies":       "Mag Werkafspraken bekijken",
}

def _can(user, codename):
    return user.is_superuser or user.has_perm(f"core.{codename}")

def _logo_url():
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        p = settings.MEDIA_ROOT / f"logo.{ext}"
        if p.exists():
            return settings.MEDIA_URL + f"logo.{ext}"
    return None

# ===== LOGIN/LOGOUT =====
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = EmailOrUsernameLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identifier"].strip()
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
    return render(request, "auth/login.html", {"form": form, "logo_url": _logo_url()})

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
    if _can(request.user, "can_view_news"):
        tiles.append({"name": "Nieuws", "img": "nieuws.png", "url_name": "news"})
    if _can(request.user, "can_view_policies"):
        tiles.append({"name": "Werkafspraken", "img": "afspraken.png", "url_name": "policies"})
    if _can(request.user, "can_access_admin"):
        tiles.append({"name": "Beheer", "img": "beheer.png", "url_name": "admin_panel"})
    return render(request, "home.html", {"tiles": tiles, "logo_url": _logo_url()})

# ===== ROSTER RENDER =====
def _pdf_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]

def _render_pdf_to_cache(pdf_bytes: bytes, zoom: float = 2.0):
    h = _pdf_hash(pdf_bytes)
    out = CACHE_DIR / h
    if not out.exists() or not any(out.glob("page_*.png")):
        out.mkdir(parents=True, exist_ok=True)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                (out / f"page_{i+1:03d}.png").write_bytes(pix.tobytes("png"))
    n_pages = len(list(out.glob("page_*.png")))
    return h, n_pages

def _clear_dir(p: Path):
    if not p.exists():
        return
    for item in p.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try: item.unlink()
            except: pass

@login_required
def rooster(request):
    if not _can(request.user, "can_view_roster"):
        return HttpResponseForbidden("Geen toegang tot rooster.")
    if not ROSTER_FILE.exists():
        return render(request, "rooster/empty.html", {"logo_url": _logo_url()})
    pdf_bytes = ROSTER_FILE.read_bytes()
    h, n = _render_pdf_to_cache(pdf_bytes, zoom=2.0)
    page_urls = [f"{settings.MEDIA_URL}cache/{h}/page_{i:03d}.png" for i in range(1, n+1)]
    return render(request, "rooster/index.html", {
        "page_urls": page_urls, "logo_url": _logo_url(), "year": datetime.now().year
    })

@login_required
def upload_roster(request):
    if not _can(request.user, "can_upload_roster"):
        return HttpResponseForbidden("Geen uploadrechten.")
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand.")
            return redirect("upload_roster")
        _clear_dir(ROSTER_DIR)   # geen versies bewaren
        _clear_dir(CACHE_DIR)    # cache leeg zodat nieuwe render verschijnt
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
    if df is None: return df
    work = df
    if q:
        ql = q.lower()
        mask = pd.Series(False, index=work.index)
        for col in work.columns:
            try:
                mask = mask | work[col].astype(str).str.lower().str.contains(ql, na=False)
            except: pass
        work = work[mask]
    if limit and limit > 0:
        work = work.head(limit)
    return work

def _availability_view(request, key: str, page_title: str, can_view_perm: str):
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
        if not _can(request.user, "can_access_admin"):  # upload-recht beperken tot admins
            return HttpResponseForbidden("Geen uploadrechten.")
        form = AvailabilityUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            ext = (Path(f.name).suffix or "").lower()
            if ext not in (".xlsx", ".xls", ".csv"):
                messages.error(request, "Alleen CSV of Excel (XLSX/XLS) toegestaan.")
                return redirect(request.path)
            # geen versies: wis oude varianten
            for oldext in (".xlsx", ".xls", ".csv"):
                p = AV_DIR / f"{key}{oldext}"
                if p.exists():
                    p.unlink()
            dest = AV_DIR / f"{key}{ext}"
            with dest.open("wb") as fh:
                for chunk in f.chunks():
                    fh.write(chunk)
            messages.success(request, f"Bestand geüpload: {f.name}")
            return redirect(request.path)

    df = None; error = None
    if existing_path:
        df, error = _read_table(existing_path)

    q = request.GET.get("q", "").strip()
    try: limit = int(request.GET.get("limit", "") or 50)
    except ValueError: limit = 50

    columns, rows = [], None
    if df is not None and error is None:
        filtered = _filter_and_limit(df, q, limit)
        columns = list(filtered.columns)
        rows = filtered.values.tolist()

    ctx = {
        "logo_url": _logo_url(),
        "form": form,
        "has_file": existing_path is not None,
        "file_name": existing_path.name if existing_path else None,
        "columns": columns, "rows": rows,
        "q": q, "limit": limit, "title": page_title,
    }
    return render(request, f"availability/{key}.html", ctx)

@login_required
def availability_home(request):
    if not _can(request.user, "can_access_availability"):
        return HttpResponseForbidden("Geen toegang.")
    subtiles = []
    if _can(request.user, "can_view_av_medications"):
        subtiles.append({"name":"Geneesmiddelen","img":"medicijn_zoeken.png","url_name":"availability_medications"})
    if _can(request.user, "can_view_av_nazendingen"):
        subtiles.append({"name":"Nazendingen","img":"nazendingen.png","url_name":"availability_nazendingen"})
    return render(request, "availability/home.html", {"tiles": subtiles, "logo_url": _logo_url()})

@login_required
def availability_medications(request):
    return _availability_view(request, "medications", "Beschikbaarheid • Geneesmiddelen", "can_view_av_medications")

@login_required
def availability_nazendingen(request):
    return _availability_view(request, "nazendingen", "Beschikbaarheid • Nazendingen", "can_view_av_nazendingen")

# ===== Nieuws & Werkafspraken =====
@login_required
def news(request):
    if not _can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")
    return render(request, "news/index.html", {"logo_url": _logo_url()})

@login_required
def policies(request):
    if not _can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")
    return render(request, "policies/index.html", {"logo_url": _logo_url()})

# ===== Admin panel & Users =====
@login_required
def admin_panel(request):
    if not _can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    group_form = GroupWithPermsForm(prefix="group")
    user_form  = SimpleUserCreateForm(prefix="user")

    if request.method == "POST" and request.POST.get("form_kind") == "group":
        gid = request.POST.get("group_id")
        instance = Group.objects.filter(pk=gid).first() if gid else None
        group_form = GroupWithPermsForm(request.POST, instance=instance, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_panel")
        messages.error(request, "Groep opslaan mislukt.")

    if request.method == "POST" and request.POST.get("form_kind") == "user_create":
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Gebruiker aangemaakt.")
            return redirect("admin_panel")
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
        "groups": groups, "group_rows": group_rows,
        "users": users, "group_form": group_form, "user_form": user_form,
        "logo_url": _logo_url(),
    })

@login_required
@require_POST
def group_delete(request, group_id: int):
    if not _can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    g = get_object_or_404(Group, pk=group_id)
    count = g.user_set.count()
    force = request.POST.get("force") == "1"
    if count > 0 and not force:
        messages.error(request, f"Kan groep “{g.name}” niet verwijderen: {count} gebruikers zijn nog lid.")
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