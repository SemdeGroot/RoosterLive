# core/views/admin.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.db import transaction

from ..forms import GroupWithPermsForm, SimpleUserCreateForm, SimpleUserEditForm, OrganizationEditForm, AfdelingEditForm
from ._helpers import can, PERM_LABELS, PERM_SECTIONS, sync_custom_permissions
from core.tasks import send_invite_email_task
from core.models import UserProfile, Organization, MedicatieReviewAfdeling
from core.tiles import build_tiles
User = get_user_model()

# ==========================================
# 1. DASHBOARD (TILES)
# ==========================================
@login_required
def admin_dashboard(request):
    """
    Landingspagina voor beheer: Toont tiles voor Users, Groepen, Orgs.
    """
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    tiles = build_tiles(request.user, group="beheer")
    
    context = {
        "page_title": "Beheer",
        "intro": "Beheer gebruikers, rechten en organisaties.",
        "tiles": tiles,
        # Eventueel een 'back_url' als je tiles_page.html dat ondersteunt:
        "back_url": "home", 
    }
    # We gebruiken hier de generieke tiles template die je ook voor medicatiebeoordeling gebruikt
    return render(request, "tiles_page.html", context)


# ==========================================
# 2. USERS VIEW
# ==========================================
@login_required
def admin_users(request):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    user_form = SimpleUserCreateForm(prefix="user")

    # ---- Gebruiker aanmaken + uitnodiging sturen ----
    if request.method == "POST" and request.POST.get("form_kind") == "user_create":
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            first_name = (user_form.cleaned_data.get("first_name") or "").strip().lower()
            last_name = (user_form.cleaned_data.get("last_name") or "").strip().lower()
            email = (user_form.cleaned_data.get("email") or "").strip().lower()
            birth_date = user_form.cleaned_data.get("birth_date")
            group = user_form.cleaned_data.get("group")
            organization = user_form.cleaned_data.get("organization")

            if not email:
                messages.error(request, "E-mail is verplicht.")
                return redirect("admin_users")

            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Er bestaat al een gebruiker met dit e-mailadres.")
                return redirect("admin_users")

            user = User.objects.create(
                username=email,
                first_name=first_name,
                last_name=last_name,
                email=email,
                is_active=True,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            if birth_date or organization:
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "birth_date": birth_date,
                        "organization": organization,
                    },
                )
            if group:
                if isinstance(group, Group):
                    user.groups.add(group)
                else:
                    try:
                        grp = Group.objects.get(pk=group)
                        user.groups.add(grp)
                    except Group.DoesNotExist:
                        pass

            try:
                transaction.on_commit(lambda: send_invite_email_task.delay(user.id))
                messages.success(
                    request,
                    f"Gebruiker {first_name} aangemaakt. Uitnodiging verzonden naar {email}."
                )
            except Exception as e:
                messages.warning(
                    request,
                    f"Gebruiker aangemaakt, maar verzenden van de uitnodiging mislukte: {e}"
                )
            return redirect("admin_users")
        else:
            messages.error(request, "Gebruiker aanmaken mislukt.")

    users = User.objects.all().select_related("profile").order_by("username")
    groups = Group.objects.all().order_by("name")
    organizations = Organization.objects.all().order_by("name")

    return render(request, "admin/users.html", {
        "users": users,
        "user_form": user_form,
        "groups": groups,
        "organizations": organizations,
    })


# ==========================================
# 3. GROUPS VIEW
# ==========================================
@login_required
def admin_groups(request):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    # Zorg dat permissies in DB overeenkomen met PERM_LABELS
    sync_custom_permissions()

    editing_group = None
    gid_get = request.GET.get("group_id")
    if gid_get:
        editing_group = Group.objects.filter(pk=gid_get).first()

    group_form = GroupWithPermsForm(prefix="group", instance=editing_group)

    # ---- Groep Opslaan ----
    if request.method == "POST" and request.POST.get("form_kind") == "group":
        gid_post = request.POST.get("group_id")
        instance = Group.objects.filter(pk=gid_post).first() if gid_post else None
        group_form = GroupWithPermsForm(request.POST, instance=instance, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_groups")
        messages.error(request, "Groep opslaan mislukt.")

    # Data voor tabel
    groups = Group.objects.all().order_by("name")
    group_rows = []
    for g in groups:
        codes = set(g.permissions.values_list("codename", flat=True))
        labels = [PERM_LABELS.get(c, c) for c in codes]
        labels.sort()
        member_count = g.user_set.count()
        group_rows.append({"group": g, "perm_labels": labels, "member_count": member_count})

    return render(request, "admin/groups.html", {
        "groups": groups,
        "group_rows": group_rows,
        "group_form": group_form,
        "editing_group": bool(editing_group),
        "editing_group_id": editing_group.id if editing_group else "",
        "perm_sections": PERM_SECTIONS,
        "perm_labels": PERM_LABELS,
    })


# ==========================================
# 4. ORGANIZATIONS VIEW
# ==========================================
@login_required
def admin_orgs(request):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    if request.method == "POST" and request.POST.get("form_kind") == "org":
        name = (request.POST.get("name") or "").strip()
        org_type = (request.POST.get("org_type") or "").strip()
        email = (request.POST.get("email") or "").strip()
        email2 = (request.POST.get("email2") or "").strip()
        phone = (request.POST.get("phone") or "").strip()

        if not name:
            messages.error(request, "Organisatienaam is verplicht.")
            return redirect("admin_orgs")

        if not email:
            messages.error(request, "E-mailadres is verplicht.")
            return redirect("admin_orgs")

        if Organization.objects.filter(name__iexact=name).exists():
            messages.error(request, "Er bestaat al een organisatie met deze naam.")
            return redirect("admin_orgs")

        Organization.objects.create(
            name=name,
            org_type=org_type,
            email=email,
            email2=email2 or "",
            phone=phone or "",
        )
        messages.success(request, f"Organisatie “{name}” aangemaakt.")
        return redirect("admin_orgs")

    organizations = Organization.objects.all().order_by("name")

    return render(request, "admin/organizations.html", {
        "organizations": organizations,
    })

# ==========================================
# 5. AFDELINGEN BEHEER
# ==========================================
@login_required
def admin_afdelingen(request):
    """
    Beheer van MedicatieReview afdelingen.
    Top formulier = Create.
    Tabel = List + Inline Edit.
    """
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen toegang.")

    afdeling_form = AfdelingEditForm()

    # ---- Nieuwe aanmaken (Create) ----
    if request.method == "POST" and request.POST.get("form_kind") == "afdeling":
        afdeling_form = AfdelingEditForm(request.POST)
        if afdeling_form.is_valid():
            obj = afdeling_form.save(commit=False)
            obj.created_by = request.user
            obj.updated_by = request.user
            obj.save()
            messages.success(request, f"Afdeling '{obj.afdeling}' aangemaakt.")
            return redirect("admin_afdelingen")
        else:
            messages.error(request, "Kon afdeling niet aanmaken. Controleer de velden.")

    # Data ophalen
    afdelingen = MedicatieReviewAfdeling.objects.select_related('organisatie').order_by('afdeling', 'organisatie__name')
    
    # We hebben alle organisaties nodig voor de dropdown in de inline-edit rijen
    all_organizations = Organization.objects.filter(
        org_type=Organization.ORG_TYPE_ZORGINSTELLING
    ).order_by('name')

    return render(request, "admin/afdelingen.html", {
        "afdelingen": afdelingen,
        "afdeling_form": afdeling_form,
        "all_organizations": all_organizations, # Belangrijk voor de loop in HTML
    })

@login_required
@require_POST
def afdeling_update(request, pk):
    """
    Verwerkt de inline edit vanuit de tabel.
    """
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen toegang.")

    afd = get_object_or_404(MedicatieReviewAfdeling, pk=pk)
    
    # We vullen het formulier met de POST data en de bestaande instance
    form = AfdelingEditForm(request.POST, instance=afd)
    
    if form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, f"Afdeling '{obj.afdeling}' is bijgewerkt.")
    else:
        # Fouten tonen via messages framework
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Fout in {field}: {error}")
                
    return redirect("admin_afdelingen")

# ==========================================
# ACTIES (DELETE / UPDATE)
# ==========================================
# Let op de redirects: deze wijzen nu naar de specifieke pagina's!

@login_required
@require_POST
def group_delete(request, group_id: int):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    g = get_object_or_404(Group, pk=group_id)
    count = g.user_set.count()
    if count > 0:
        messages.error(
            request,
            f"Kan groep “{g.name}” niet verwijderen: {count} gebruiker(s) zijn nog lid. "
            "Wijs deze gebruikers eerst een andere groep toe."
        )
        return redirect("admin_groups")
    g.delete()
    messages.success(request, "Groep verwijderd.")
    return redirect("admin_groups")

@login_required
@require_POST
def user_update(request, user_id: int):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    form = SimpleUserEditForm(request.POST, instance=u)
    if form.is_valid():
        form.save()
        messages.success(request, "Gebruiker opgeslagen.")
    else:
        messages.error(request, "Opslaan mislukt.")
    return redirect("admin_users")

@login_required
@require_POST
def user_delete(request, user_id: int):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    username = u.first_name
    u.delete()
    messages.success(request, f"Gebruiker {username} verwijderd.")
    return redirect("admin_users")

@login_required
@require_POST
def org_delete(request, org_id: int):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    org = get_object_or_404(Organization, pk=org_id)
    linked = UserProfile.objects.filter(organization=org).count()
    if linked > 0:
        messages.error(
            request,
            f"Kan organisatie “{org.name}” niet verwijderen: "
            f"{linked} profiel(en) zijn nog gekoppeld. "
            "Pas eerst deze gebruikers aan."
        )
        return redirect("admin_orgs")

    org.delete()
    messages.success(request, "Organisatie verwijderd.")
    return redirect("admin_orgs")

@login_required
@require_POST
def org_update(request, org_id: int):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    org = get_object_or_404(Organization, pk=org_id)
    form = OrganizationEditForm(request.POST, instance=org)
    if form.is_valid():
        form.save()
        messages.success(request, "Organisatie opgeslagen.")
    else:
        messages.error(request, "Opslaan mislukt.")
    return redirect("admin_orgs")

@login_required
def delete_afdeling(request, pk):
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden()
    
    if request.method == "POST":
        afd = get_object_or_404(MedicatieReviewAfdeling, pk=pk)
        naam = afd.afdeling
        afd.delete()
        messages.success(request, f"Afdeling '{naam}' verwijderd.")
    
    # Redirect nu naar de admin pagina
    return redirect("admin_afdelingen")