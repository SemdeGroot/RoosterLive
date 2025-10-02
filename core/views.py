import os, hashlib
from pathlib import Path
import fitz  # PyMuPDF
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User, Group

from .models import Roster
from .forms import RosterUploadForm, UserForm

def _ensure_roles():
    for name in ["Admin","Manager","Viewer"]:
        Group.objects.get_or_create(name=name)

def _pdf_hash16(pdf_path: Path) -> str:
    h = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
    return h[:16]

def _render_pdf_to_pngs(pdf_path: Path, out_dir: Path, zoom: float = 2.0) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("page_*.png"):
        p.unlink()
    with fitz.open(pdf_path) as doc:
        mat = fitz.Matrix(zoom, zoom)
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            (out_dir / f"page_{i:03d}.png").write_bytes(pix.tobytes("png"))
        return doc.page_count

def _logo_url():
    for ext in ("png","jpg","jpeg","svg","webp","gif"):
        p = settings.DATA_DIR / f"logo.{ext}"
        if p.exists():
            return f"/media/_data/logo.{ext}"
    return None

# maak logo bereikbaar via MEDIA door te kopiëren (optioneel)
(Path(settings.MEDIA_ROOT) / "_data").mkdir(parents=True, exist_ok=True)
for ext in ("png","jpg","jpeg","svg","webp","gif"):
    src = settings.DATA_DIR / f"logo.{ext}"
    dst = Path(settings.MEDIA_ROOT) / "_data" / f"logo.{ext}"
    if src.exists() and not dst.exists():
        dst.write_bytes(src.read_bytes())

@login_required
def index(request):
    _ensure_roles()
    roster = Roster.objects.order_by("-created_at").first()
    page_urls = []
    doc_hash = ""
    if roster:
        cache_dir = settings.CACHE_DIR / f"{roster.id}_{roster.hash16}"
        page_urls = [f"/media/cache/{roster.id}_{roster.hash16}/page_{i:03d}.png" for i in range(1, roster.page_count + 1)]
        doc_hash = roster.hash16
    ctx = dict(
        roster=roster,
        page_urls=page_urls,
        doc_hash=doc_hash,
        hash_poll=int(os.getenv("HASH_POLL_SECONDS", "60")),
        logo_url=_logo_url(),
    )
    return render(request, "index.html", ctx)

@login_required
def upload_roster(request):
    # Alleen Admin of Manager
    if not (request.user.is_superuser or request.user.groups.filter(name__in=["Admin","Manager"]).exists()):
        return HttpResponseForbidden("Geen toegang.")
    if request.method == "POST":
        form = RosterUploadForm(request.POST, request.FILES)
        if form.is_valid():
            roster = form.save()
            pdf_path = Path(roster.pdf.path)
            h = _pdf_hash16(pdf_path)
            cache_dir = settings.CACHE_DIR / f"{roster.id}_{h}"
            count = _render_pdf_to_pngs(pdf_path, cache_dir, zoom=2.0)
            roster.hash16 = h
            roster.page_count = count
            roster.save()
            messages.success(request, "Rooster geüpload en gerenderd.")
            return redirect("index")
        else:
            messages.error(request, "Upload mislukt. Controleer je bestand.")
    else:
        form = RosterUploadForm()
    return render(request, "upload.html", {"form": form, "logo_url": _logo_url()})

@login_required
def manage_users(request):
    # Alleen Admin
    if not (request.user.is_superuser or request.user.groups.filter(name="Admin").exists()):
        return HttpResponseForbidden("Geen toegang.")
    _ensure_roles()
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Gebruiker aangemaakt.")
            return redirect("manage_users")
        else:
            messages.error(request, "Kon gebruiker niet aanmaken.")
    else:
        form = UserForm()
    users = User.objects.all().order_by("username")
    return render(request, "users.html", {"form": form, "users": users, "logo_url": _logo_url()})

@login_required
def hash_endpoint(request):
    roster = Roster.objects.order_by("-created_at").first()
    if not roster:
        return HttpResponse("", content_type="text/plain")
    return HttpResponse(roster.hash16 or "", content_type="text/plain")

def healthz(request):
    return HttpResponse("ok", content_type="text/plain")
