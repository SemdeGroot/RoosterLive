# core/views/admin.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction

from ..forms import GroupWithPermsForm, SimpleUserCreateForm, SimpleUserEditForm
from ._helpers import can, PERM_LABELS, PERM_SECTIONS, sync_custom_permissions
from core.tasks import send_invite_email_task
from core.models import UserProfile

User = get_user_model()

@login_required
def admin_panel(request):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    # Zorg dat permissies in DB overeenkomen met PERM_LABELS
    sync_custom_permissions()

    # ---- Groepen (bewerken/opslaan) ----
    editing_group = None
    gid_get = request.GET.get("group_id")
    if gid_get:
        editing_group = Group.objects.filter(pk=gid_get).first()

    group_form = GroupWithPermsForm(prefix="group", instance=editing_group)
    user_form  = SimpleUserCreateForm(prefix="user")

    if request.method == "POST" and request.POST.get("form_kind") == "group":
        gid_post = request.POST.get("group_id")
        instance = Group.objects.filter(pk=gid_post).first() if gid_post else None
        group_form = GroupWithPermsForm(request.POST, instance=instance, prefix="group")
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Groep opgeslagen.")
            return redirect("admin_panel")
        messages.error(request, "Groep opslaan mislukt.")

    # ---- Gebruiker aanmaken + uitnodiging sturen ----
    if request.method == "POST" and request.POST.get("form_kind") == "user_create":
        user_form = SimpleUserCreateForm(request.POST, prefix="user")
        if user_form.is_valid():
            first_name = (user_form.cleaned_data.get("first_name") or "").strip().lower()
            email = (user_form.cleaned_data.get("email") or "").strip().lower()
            birth_date = user_form.cleaned_data.get("birth_date")
            group = user_form.cleaned_data.get("group")

            if not email:
                messages.error(request, "E-mail is verplicht.")
                return redirect("admin_panel")

            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Er bestaat al een gebruiker met dit e-mailadres.")
                return redirect("admin_panel")

            user = User.objects.create(
                username=email,          # username = email
                first_name=first_name,   # opgeslagen in lowercase
                email=email,             # opgeslagen in lowercase
                is_active=True,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            if birth_date:
                from core.models import UserProfile
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={"birth_date": birth_date},
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
                # Zet de taak pas in de queue na succesvolle DB-commit
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

            return redirect("admin_panel")
        else:
            messages.error(request, "Gebruiker aanmaken mislukt.")

    # ---- Lijsten voor de tabel(len) ----
    groups = Group.objects.all().order_by("name")
    users = User.objects.all().select_related("profile").order_by("username")

    group_rows = []
    for g in groups:
        codes = set(g.permissions.values_list("codename", flat=True))
        labels = [PERM_LABELS.get(c, c) for c in codes]
        labels.sort()
        member_count = g.user_set.count()
        group_rows.append({"group": g, "perm_labels": labels, "member_count": member_count})

    return render(request, "admin/admin_panel.html", {
        "groups": groups,
        "group_rows": group_rows,
        "users": users,
        "group_form": group_form,
        "user_form": user_form,
        "editing_group": bool(editing_group),
        "editing_group_id": editing_group.id if editing_group else "",
        "perm_sections": PERM_SECTIONS,
        "perm_labels": PERM_LABELS,
    })

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
        return redirect("admin_panel")
    g.delete()
    messages.success(request, "Groep verwijderd.")
    return redirect("admin_panel")

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
    return redirect("admin_panel")

@login_required
@require_POST
def user_delete(request, user_id: int):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")
    u = get_object_or_404(User, pk=user_id)
    username = u.first_name
    u.delete()
    messages.success(request, f"Gebruiker {username} verwijderd.")
    return redirect("admin_panel")