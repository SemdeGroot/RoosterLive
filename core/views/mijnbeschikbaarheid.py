from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone, translation

from ._helpers import can
from core.models import Availability


def _monday_of_iso_week(some_date: date) -> date:
    return some_date - timedelta(days=some_date.weekday())


def _clamp_week(target_monday: date, min_monday: date, max_monday: date) -> date:
    if target_monday < min_monday:
        return min_monday
    if target_monday > max_monday:
        return max_monday
    return target_monday


@login_required
def mijnbeschikbaarheid_view(request):
    if not can(request.user, "can_send_beschikbaarheid"):
        return HttpResponseForbidden("Geen toegang.")

    translation.activate("nl")

    today = timezone.localdate()
    WEEKS_AHEAD = 12  # 6 maanden vooruit

    min_monday = _monday_of_iso_week(today)                     # huidige week (ma)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

    # ✅ Housekeeping: wis alle oude weken (alles vóór huidige maandag)
    Availability.objects.filter(date__lt=min_monday).delete()

    # ---- weekselectie (ongewijzigd) ----
    qs_week = request.GET.get("week")
    qs_monday = request.GET.get("monday")
    if qs_monday:
        try:
            y, m, d = map(int, qs_monday.split("-"))
            monday = date(y, m, d)
        except Exception:
            monday = min_monday
    elif qs_week:
        try:
            year_str, wstr = qs_week.split("-W")
            monday = date.fromisocalendar(int(year_str), int(wstr), 1)
        except Exception:
            monday = min_monday
    else:
        monday = min_monday

    monday = _clamp_week(monday, min_monday, max_monday)
    week_end = monday + timedelta(days=4)

    # Navigatie (alleen tussen huidige week en +6 maanden)
    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    # Ma–vr
    days = [monday + timedelta(days=i) for i in range(5)]

    if request.method == "POST":
        redirect_to = request.POST.get("redirect_to_monday")
        for d in days:
            key_m = f"morning_{d.isoformat()}"
            key_a = f"afternoon_{d.isoformat()}"
            morning = key_m in request.POST
            afternoon = key_a in request.POST

            if morning or afternoon:
                Availability.objects.update_or_create(
                    user=request.user,
                    date=d,
                    defaults={"morning": morning, "afternoon": afternoon},
                )
            else:
                Availability.objects.filter(user=request.user, date=d).delete()

        messages.success(request, "Beschikbaarheid opgeslagen.")
        if redirect_to:
            try:
                y, m, d = map(int, redirect_to.split("-"))
                target = _clamp_week(date(y, m, d), min_monday, max_monday)
                return HttpResponseRedirect(f"{reverse('mijnbeschikbaarheid')}?monday={target.isoformat()}")
            except Exception:
                pass
        return HttpResponseRedirect(f"{reverse('mijnbeschikbaarheid')}?monday={monday.isoformat()}")

    # Bestaande waarden voor deze week
    existing = {
        av.date: av
        for av in Availability.objects.filter(user=request.user, date__in=days)
    }

    rows = []
    for d in days:
        av = existing.get(d)
        rows.append({
            "date": d,
            "morning": bool(av and av.morning),
            "afternoon": bool(av and av.afternoon),
        })

    # Dropdown: huidige week → +6 maanden
    week_options = []
    cur = min_monday
    while cur <= max_monday:
        week_options.append({
            "value": cur.isoformat(),
            "start": cur,
            "end": cur + timedelta(days=4),
            "iso_week": cur.isocalendar()[1],
            "iso_year": cur.isocalendar()[0],
        })
        cur += timedelta(weeks=1)

    iso_year, iso_week, _ = monday.isocalendar()
    header_title = f"Week {iso_week} – {iso_year}"

    return render(request, "mijnbeschikbaarheid/index.html", {
        "monday": monday,
        "week_end": week_end,
        "rows": rows,
        "week_options": week_options,
        "min_monday": min_monday,
        "max_monday": max_monday,
        "header_title": header_title,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
    })