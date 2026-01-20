# mijnbeschikbaarheid.py
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone, translation

from core.models import Availability, Dagdeel
from ._helpers import can


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
    WEEKS_AHEAD = 12

    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

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
    week_end = monday + timedelta(days=5)

    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    days = [monday + timedelta(days=i) for i in range(6)]

    # Dynamische dagdelen (alleen PLANNING_CODES)
    dagdelen = list(
        Dagdeel.objects.filter(code__in=Dagdeel.PLANNING_CODES).order_by("sort_order")
    )

    if request.method == "POST":
        redirect_to = request.POST.get("redirect_to_monday")

        for d in days:
            selected_codes = []
            for dd in dagdelen:
                key = f"{dd.code}_{d.isoformat()}"  # bv "morning_2026-01-20"
                if key in request.POST:
                    selected_codes.append(dd.code)

            if selected_codes:
                av, _ = Availability.objects.update_or_create(
                    user=request.user,
                    date=d,
                    defaults={"source": "manual"},
                )
                selected_dagdelen = Dagdeel.objects.filter(code__in=selected_codes)
                av.dagdelen.set(selected_dagdelen)
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

    # Prefetch dagdelen voor performance
    existing_qs = (
        Availability.objects.filter(user=request.user, date__in=days)
        .prefetch_related("dagdelen")
    )
    existing = {av.date: av for av in existing_qs}

    rows = []
    for d in days:
        av = existing.get(d)
        selected = set(av.dagdelen.values_list("code", flat=True)) if av else set()
        rows.append({
            "date": d,
            "selected_codes": selected,  # template checkt hierin
        })

    week_options = []
    cur = min_monday
    while cur <= max_monday:
        week_options.append({
            "value": cur.isoformat(),
            "start": cur,
            "end": cur + timedelta(days=5),
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
        "dagdelen": dagdelen,  # voor dynamische kolommen + tijden
        "week_options": week_options,
        "min_monday": min_monday,
        "max_monday": max_monday,
        "header_title": header_title,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
    })
