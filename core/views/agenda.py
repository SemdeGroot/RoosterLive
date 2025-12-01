# core/views/agenda.py
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from core.models import UserProfile
from ._helpers import can


# Gebruik constante uit settings, fallback = 1
ORG_ID_APOTHEEK_JANSEN = getattr(settings, "APOTHEEK_JANSEN_ORG_ID", 1)


def format_dutch_name_from_user(user) -> str:
    """
    Bouw een naam op vanuit standaard Django User (first_name, last_name).

    Regels:
    - Voornaam: eerste letter hoofdletter, rest klein
    - Achternaam: alleen het laatste woord kapitaliseren, tussenvoegsels klein
      bv. first_name='sem', last_name='de groot' -> 'Sem de Groot'
    """
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    username = (user.username or "").strip()

    # fallback als alles leeg is
    if not first and not last:
        return username

    # Voornaam
    if first:
        first_fmt = first.lower().capitalize()
    else:
        first_fmt = ""

    # Achternaam
    if last:
        parts = last.lower().split()
        if len(parts) == 1:
            last_fmt = parts[0].capitalize()
        else:
            # tussenvoegsels klein
            for i in range(len(parts) - 1):
                parts[i] = parts[i].lower()
            # laatste deel (echt achternaam) capitalizen
            parts[-1] = parts[-1].capitalize()
            last_fmt = " ".join(parts)
    else:
        last_fmt = ""

    full = (first_fmt + " " + last_fmt).strip()
    return full or username


@login_required
def agenda(request):
    """
    Verjaardagen van de komende twee weken voor organisatie met org_id = APOTHEEK_JANSEN_ORG_ID.
    Resultaat wordt gecached per organisatie + dag.
    """
    if not can(request.user, "can_view_agenda"):
        return HttpResponseForbidden("Geen toegang tot agenda.")

    today = timezone.localdate()
    two_weeks_later = today + timedelta(days=14)

    cache_key = f"agenda_birthdays:{ORG_ID_APOTHEEK_JANSEN}:{today.isoformat()}"
    birthdays = cache.get(cache_key)

    if birthdays is None:
        profiles = (
            UserProfile.objects
            .select_related("user")
            .filter(
                birth_date__isnull=False,
                organization_id=ORG_ID_APOTHEEK_JANSEN,
            )
        )

        upcoming: list[dict] = []

        for profile in profiles:
            dob = profile.birth_date  # datetime.date

            # Volgende verjaardag in huidig jaar
            try:
                next_bday = dob.replace(year=today.year)
            except ValueError:
                # 29 feb -> 28 feb op niet-schrikkeljaar
                next_bday = date(today.year, 2, 28)

            # Als die al geweest is: volgend jaar
            if next_bday < today:
                try:
                    next_bday = dob.replace(year=today.year + 1)
                except ValueError:
                    next_bday = date(today.year + 1, 2, 28)

            if today <= next_bday <= two_weeks_later:
                age = next_bday.year - dob.year
                name = format_dutch_name_from_user(profile.user)

                upcoming.append(
                    {
                        "name": name,
                        "date": next_bday,
                        "age": age,
                        "is_today": next_bday == today,
                        "is_tomorrow": next_bday == today + timedelta(days=1),
                    }
                )

        upcoming.sort(key=lambda x: x["date"])
        birthdays = upcoming

        # cache bv. 1 uur
        cache.set(cache_key, birthdays, 60 * 60)

    context = {
        "year": today.year,
        "today": today,
        "two_weeks_later": two_weeks_later,
        "birthdays": birthdays,
    }
    return render(request, "agenda/index.html", context)