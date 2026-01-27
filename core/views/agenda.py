# core/views/agenda.py
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages  # Toegevoegd
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect
from django.urls import reverse

from ._helpers import can

from core.models import UserProfile, AgendaItem
from core.forms import AgendaItemForm
from core.tasks import send_agenda_uploaded_push_task
from core.utils.calendar_active import get_calendar_sync_status

# Gebruik constante uit settings, fallback = 1
ORG_ID_APOTHEEK_JANSEN = getattr(settings, "APOTHEEK_JANSEN_ORG_ID", 1)

def format_dutch_name_from_user(user) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    username = (user.username or "").strip()

    full_name = f"{first} {last}".strip()
    if not full_name:
        return username

    # Als er al een mix van hoofd- en kleine letters in zit: niets doen
    has_upper = any(c.isupper() for c in full_name)
    has_lower = any(c.islower() for c in full_name)
    if has_upper and has_lower:
        return full_name

    # Alles upper/lower: alleen minimale normalisatie, zonder alles te lowercaseden
    def cap_first_letter_keep_rest(word: str) -> str:
        return (word[:1].upper() + word[1:]) if word else word

    parts = full_name.split()
    if not parts:
        return full_name or username

    parts[0] = cap_first_letter_keep_rest(parts[0])
    if len(parts) > 1:
        parts[-1] = cap_first_letter_keep_rest(parts[-1])

    return " ".join(parts) or username

@login_required
def agenda(request):
    if not can(request.user, "can_view_agenda"):
        return HttpResponseForbidden("Geen toegang tot agenda.")
    
    can_edit = can(request, "can_upload_agenda")

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
        if not can_edit:
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
        if not can_edit:
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
        if not can_edit:
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

    # --- Webcal link + sync status ---
    token = request.user.profile.calendar_token
    ics_path = reverse("diensten_webcal", args=[token])
    https_url = request.build_absolute_uri(ics_path)
    webcal_url = https_url.replace("https://", "webcal://").replace("http://", "webcal://")

    sync_status = get_calendar_sync_status(request.user.id)
    context = {
        "can_edit": can_edit,
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
        "webcal_https_url": https_url,
        "webcal_url": webcal_url,
        "calendar_active": sync_status.active,
        "calendar_last_synced": sync_status.last_synced,
    }
    return render(request, "agenda/index.html", context)