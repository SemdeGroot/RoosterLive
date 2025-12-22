# core/views/agenda.py
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages  # Toegevoegd
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect

from ._helpers import can

from core.models import UserProfile, AgendaItem
from core.forms import AgendaItemForm
from core.tasks import send_agenda_uploaded_push_task

# Gebruik constante uit settings, fallback = 1
ORG_ID_APOTHEEK_JANSEN = getattr(settings, "APOTHEEK_JANSEN_ORG_ID", 1)


def format_dutch_name_from_user(user) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    username = (user.username or "").strip()

    if not first and not last:
        return username

    if first:
        first_fmt = first.lower().capitalize()
    else:
        first_fmt = ""

    if last:
        parts = last.lower().split()
        if len(parts) == 1:
            last_fmt = parts[0].capitalize()
        else:
            for i in range(len(parts) - 1):
                parts[i] = parts[i].lower()
            parts[-1] = parts[-1].capitalize()
            last_fmt = " ".join(parts)
    else:
        last_fmt = ""

    full = (first_fmt + " " + last_fmt).strip()
    return full or username


@login_required
def agenda(request):
    if not can(request.user, "can_view_agenda"):
        return HttpResponseForbidden("Geen toegang tot agenda.")

    today = timezone.localdate()

    # Verwijder automatisch items in het verleden
    AgendaItem.objects.filter(date__lt=today).delete()

    # Standaard lege forms (GET)
    new_general_form = AgendaItemForm(prefix="general")
    new_outing_form = AgendaItemForm(prefix="outing")

    open_edit_id = None

    # --- POST Logica ---

    # 1. Verwijderen van items
    if request.method == "POST" and "delete_item" in request.POST:
        if not can(request.user, "can_upload_agenda"):
            return HttpResponseForbidden("Geen toegang.")

        item_id = request.POST.get("delete_item")
        # Expliciete check of het gelukt is
        deleted_count, _ = AgendaItem.objects.filter(id=item_id).delete()
        
        if deleted_count > 0:
            messages.success(request, "Agendapunt verwijderd.")
        else:
            messages.error(request, "Item kon niet worden verwijderd (reeds weg?).")
            
        return redirect("agenda")

    # 2. Bewerken van items
    if request.method == "POST" and "edit_item" in request.POST:
        if not can(request.user, "can_upload_agenda"):
            return HttpResponseForbidden("Geen toegang.")

        try:
            item_id = int(request.POST.get("edit_item"))
        except (TypeError, ValueError):
            return redirect("agenda")

        item = AgendaItem.objects.filter(id=item_id).first()
        if not item:
            messages.error(request, "Item niet gevonden.")
            return redirect("agenda")

        open_edit_id = item_id
        edit_form = AgendaItemForm(request.POST, prefix=f"edit-{item_id}", instance=item)

        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, "Wijzigingen opgeslagen.")
            return redirect("agenda")
        else:
            messages.error(request, "Er staan fouten in het formulier.")

    # 3. Toevoegen van items
    if request.method == "POST" and "add_category" in request.POST:
        if not can(request.user, "can_upload_agenda"):
            return HttpResponseForbidden("Geen toegang.")

        category = request.POST.get("add_category")
        if category == "general":
            new_general_form = AgendaItemForm(request.POST, prefix="general")
            form = new_general_form
        elif category == "outing":
            new_outing_form = AgendaItemForm(request.POST, prefix="outing")
            form = new_outing_form
        else:
            form = None

        if form is not None and form.is_valid():
            item = form.save(commit=False)
            item.category = category
            item.created_by = request.user
            item.save()

            send_agenda_uploaded_push_task.delay(category)
            messages.success(request, "Nieuw agendapunt toegevoegd.")
            return redirect("agenda")
        else:
            messages.error(request, "Item toevoegen mislukt. Controleer de velden.")

    # --- Data ophalen voor GET (of render na invalid POST) ---
    general_qs = AgendaItem.objects.filter(category="general", date__gte=today).order_by("date")
    outing_qs = AgendaItem.objects.filter(category="outing", date__gte=today).order_by("date")

    general_rows = []
    for item in general_qs:
        if open_edit_id == item.id and request.method == "POST" and "edit_item" in request.POST:
            form = AgendaItemForm(request.POST, prefix=f"edit-{item.id}", instance=item)
        else:
            form = AgendaItemForm(prefix=f"edit-{item.id}", instance=item)
        general_rows.append((item, form))

    outing_rows = []
    for item in outing_qs:
        if open_edit_id == item.id and request.method == "POST" and "edit_item" in request.POST:
            form = AgendaItemForm(request.POST, prefix=f"edit-{item.id}", instance=item)
        else:
            form = AgendaItemForm(prefix=f"edit-{item.id}", instance=item)
        outing_rows.append((item, form))

    # Voor verjaardagen caching
    four_weeks_later = today + timedelta(days=28)
    cache_key = f"agenda_birthdays:{ORG_ID_APOTHEEK_JANSEN}:{today.isoformat()}"
    birthdays = cache.get(cache_key)

    if birthdays is None:
        profiles = UserProfile.objects.select_related("user").filter(
            birth_date__isnull=False, organization_id=ORG_ID_APOTHEEK_JANSEN
        )
        upcoming = []
        for profile in profiles:
            dob = profile.birth_date
            try:
                next_bday = dob.replace(year=today.year)
            except ValueError:
                next_bday = date(today.year, 2, 28)
            if next_bday < today:
                try:
                    next_bday = dob.replace(year=today.year + 1)
                except ValueError:
                    next_bday = date(today.year + 1, 2, 28)

            if today <= next_bday <= four_weeks_later:
                upcoming.append({
                    "name": format_dutch_name_from_user(profile.user),
                    "date": next_bday,
                    "age": next_bday.year - dob.year,
                    "is_today": next_bday == today,
                    "is_tomorrow": next_bday == today + timedelta(days=1),
                })
        upcoming.sort(key=lambda x: x["date"])
        birthdays = upcoming
        cache.set(cache_key, birthdays, 60 * 60 * 8)

    context = {
        "today": today,
        "four_weeks_later": four_weeks_later,
        "birthdays": birthdays,
        "general_rows": general_rows,
        "outing_rows": outing_rows,
        "general_items": [i for i, _ in general_rows],
        "outing_items": [i for i, _ in outing_rows],
        "new_general_form": new_general_form,
        "new_outing_form": new_outing_form,
        "open_edit_id": open_edit_id,
    }
    return render(request, "agenda/index.html", context)