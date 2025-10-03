import os, hashlib
from pathlib import Path
import fitz  # PyMuPDF
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.decorators import login_required, permission_required
from .forms import RosterUploadForm, SimpleUserCreateForm, GroupWithPermsForm
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .forms import SimpleUserCreateForm, GroupWithPermsForm, SimpleUserUpdateForm

from .models import Roster
from .forms import RosterUploadForm, UserForm

# NAV-helper voor templates
def _can(user, perm_codename):
    return user.is_superuser or user.has_perm(f"core.{perm_codename}")

@login_required
def admin_panel(request):
    """
    Eén scherm: links 'Groepen', rechts 'Gebruikers'.
    Alleen zichtbaar voor users met 'can_manage_users'.
    """
    if not _can(request.user, "can_manage_users"):
        return HttpResponseForbidden("Geen toegang.")

    group_form = GroupWithPermsForm(prefix="group")
    user_form  = SimpleUserCreateForm(prefix="user")

    # submit groep
    if request.method == "POST" and "group-name" in request.POST:
        # create or update (als ?group_id= meegegeven is)
        gid = request.GET.get("group_id")
        if gid:
            grp = Group.objects.get(pk=gid)
            group_form = GroupWithPermsForm(request.POST, instance=grp, prefix="group")
        else:
            group_form = GroupWithPermsForm(request.POST, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_panel")

    # submit user
    if request.method == "POST" and "user-first_name" in request.POST:
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Gebruiker aangemaakt.")
            return redirect("admin_panel")

    groups = Group.objects.all().order_by("name")
    users = User.objects.all().order_by("username")

    # Als er ?group_id= staat: laad bestaande groep in het formulier
    gid = request.GET.get("group_id")
    if gid and request.method != "POST":
        try:
            group_form = GroupWithPermsForm(instance=Group.objects.get(pk=gid), prefix="group")
        except Group.DoesNotExist:
            pass

    return render(request, "admin_panel.html", {
        "groups": groups,
        "users": users,
        "group_form": group_form,
        "user_form": user_form,
        "logo_url": _logo_url(),
        "can_upload": _can(request.user, "can_upload_roster"),
        "can_users": _can(request.user, "can_view_users_tab"),
        "can_upload_tab": _can(request.user, "can_view_upload_tab"),
    })

# Pas bestaande rechtenchecks aan:
@login_required
def upload_roster(request):
    if not _can(request.user, "can_upload_roster"):
        return HttpResponseForbidden("Geen toegang.")

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
    if not _can(request.user, "can_view_roster"):
        return HttpResponseForbidden("Geen toegang tot rooster.")
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

def _can(user, perm_codename):
    return user.is_superuser or user.has_perm(f"core.{perm_codename}")

@login_required
def admin_panel(request):
    if not _can(request.user, "can_manage_users"):
        return HttpResponseForbidden("Geen toegang.")

    group_form = GroupWithPermsForm(prefix="group")
    user_form  = SimpleUserCreateForm(prefix="user")

    # Groep aanmaken/bijwerken
    if request.method == "POST" and request.POST.get("form_kind") == "group":
        gid = request.POST.get("group_id")
        instance = Group.objects.filter(pk=gid).first() if gid else None
        group_form = GroupWithPermsForm(request.POST, instance=instance, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_panel")
        messages.error(request, "Groep opslaan mislukt.")

    # Nieuwe user aanmaken
    if request.method == "POST" and request.POST.get("form_kind") == "user_create":
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Gebruiker aangemaakt.")
            return redirect("admin_panel")
        messages.error(request, "Gebruiker aanmaken mislukt.")

    groups = Group.objects.all().order_by("name")
    users = User.objects.all().order_by("username")

    return render(request, "admin_panel.html", {
        "groups": groups,
        "users": users,
        "group_form": group_form,
        "user_form": user_form,
        "logo_url": _logo_url(),
    })

@login_required
@require_POST
def user_update(request, user_id: int):
    if not _can(request.user, "can_manage_users"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    form = SimpleUserUpdateForm(request.POST, instance=u)
    if form.is_valid():
        # Voorkom dat je jezelf uitzet of je eigen laatste admin rechten verliest
        if u.id == request.user.id and not form.cleaned_data.get("is_active", True):
            messages.error(request, "Je kunt je eigen account niet deactiveren.")
            return redirect("admin_panel")
        form.save()
        messages.success(request, "Gebruiker bijgewerkt.")
    else:
        messages.error(request, "Gebruiker bijwerken mislukt.")
    return redirect("admin_panel")

@login_required
@require_POST
def user_delete(request, user_id: int):
    if not _can(request.user, "can_manage_users"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    if u.id == request.user.id:
        messages.error(request, "Je kunt je eigen account niet verwijderen.")
        return redirect("admin_panel")
    u.delete()
    messages.success(request, "Gebruiker verwijderd.")
    return redirect("admin_panel")

# Vriendelijke labels per permission-codename (zelfde tekst als in je formulier)
PERM_LABELS = {
    "can_access_admin":        "Mag beheer openen",
    "can_manage_users":        "Mag gebruikers beheren",
    "can_view_roster":         "Mag rooster bekijken",
    "can_upload_roster":       "Mag roosters uploaden",
    "can_access_availability": "Mag Beschikbaarheid openen",
    "can_view_av_medications": "Mag subtab Geneesmiddelen zien",
    "can_view_av_nazendingen": "Mag subtab Nazendingen zien",
}

@login_required
def admin_panel(request):
    if not _can(request.user, "can_manage_users"):
        return HttpResponseForbidden("Geen toegang.")

    group_form = GroupWithPermsForm(prefix="group")
    user_form  = SimpleUserCreateForm(prefix="user")

    # Groep opslaan (create/update)
    if request.method == "POST" and request.POST.get("form_kind") == "group":
        gid = request.POST.get("group_id")
        instance = Group.objects.filter(pk=gid).first() if gid else None
        group_form = GroupWithPermsForm(request.POST, instance=instance, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_panel")
        messages.error(request, "Groep opslaan mislukt.")

    # Nieuwe user aanmaken
    if request.method == "POST" and request.POST.get("form_kind") == "user_create":
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Gebruiker aangemaakt.")
            return redirect("admin_panel")
        messages.error(request, "Gebruiker aanmaken mislukt.")

    groups = Group.objects.all().order_by("name")
    users = User.objects.all().order_by("username")

    # Bouw een lijst met vriendelijke perm-teksten per groep
    group_rows = []
    for g in groups:
        codes = set(g.permissions.values_list("codename", flat=True))
        labels = [PERM_LABELS.get(c, c) for c in codes]  # fallback naar codename
        labels.sort()
        group_rows.append({"group": g, "perm_labels": labels})

    return render(request, "admin_panel.html", {
        "groups": groups,            # nog beschikbaar
        "group_rows": group_rows,    # gebruik dit in de tabel
        "users": users,
        "group_form": group_form,
        "user_form": user_form,
        "logo_url": _logo_url(),
    })


@login_required
@require_POST
def group_delete(request, group_id: int):
    """Groep definitief verwijderen."""
    if not _can(request.user, "can_manage_users"):
        return HttpResponseForbidden("Geen toegang.")
    g = get_object_or_404(Group, pk=group_id)
    g.delete()
    messages.success(request, "Groep verwijderd.")
    return redirect("admin_panel")

@login_required
def availability_home(request):
    if not _can(request.user, "can_access_availability"):
        return HttpResponseForbidden("Geen toegang tot Beschikbaarheid.")
    return render(request, "availability/home.html", {"logo_url": _logo_url()})

@login_required
def availability_medications(request):
    if not _can(request.user, "can_access_availability") or not _can(request.user, "can_view_av_medications"):
        return HttpResponseForbidden("Geen toegang tot Geneesmiddelen.")
    return render(request, "availability/medications.html", {"logo_url": _logo_url()})

@login_required
def availability_nazendingen(request):
    if not _can(request.user, "can_access_availability") or not _can(request.user, "can_view_av_nazendingen"):
        return HttpResponseForbidden("Geen toegang tot Nazendingen.")
    return render(request, "availability/nazendingen.html", {"logo_url": _logo_url()})