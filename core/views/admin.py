# core/views/admin.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from ..forms import GroupWithPermsForm, SimpleUserCreateForm, SimpleUserEditForm
from ._helpers import can, PERM_LABELS, PERM_SECTIONS, sync_custom_permissions

@login_required
def admin_panel(request):
    if not can(request.user, "can_access_admin"):
        return HttpResponseForbidden("Geen toegang.")

    # ✨ Zorg dat permissies in DB overeenkomen met PERM_LABELS
    sync_custom_permissions()

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

    return render(request, "admin/admin_panel.html", {
        "groups": groups,
        "group_rows": group_rows,
        "users": users,
        "group_form": group_form,
        "user_form": user_form,
        "editing_group": bool(editing_group),
        "editing_group_id": editing_group.id if editing_group else "",

        # ▼ dynamisch voor de template
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
    username = u.username
    u.delete()
    messages.success(request, f"Gebruiker “{username}” verwijderd.")
    return redirect("admin_panel")