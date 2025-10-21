from datetime import date, timedelta
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone, translation
from django.utils.formats import date_format
from ._helpers import can
from core.models import Availability
from core.views.mijnbeschikbaarheid import _monday_of_iso_week, _clamp_week


def _user_group(u):
    g = u.groups.first() if hasattr(u, "groups") else None
    return g.name if g else "Onbekend"


def _user_firstname_cap(u):
    fn = (u.first_name or "").strip()
    if fn:
        return fn[:1].upper() + fn[1:].lower()
    un = (getattr(u, "username", "") or "").strip()
    return un[:1].upper() + un[1:].lower() if un else "Onbekend"


@login_required
def personeelsdashboard_view(request):
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return HttpResponseForbidden("Geen toegang.")

    translation.activate("nl")
    today = timezone.localdate()
    WEEKS_AHEAD = 26

    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

    # ✅ Housekeeping (globaal, voor alle users)
    Availability.objects.filter(date__lt=min_monday).delete()

    # Weekselectie (alleen huidige → +6mnd)
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
            y_str, w_str = qs_week.split("-W")
            monday = date.fromisocalendar(int(y_str), int(w_str), 1)
        except Exception:
            monday = min_monday
    else:
        monday = min_monday

    monday = _clamp_week(monday, min_monday, max_monday)
    week_end = monday + timedelta(days=4)

    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    days = [monday + timedelta(days=i) for i in range(5)]

    av_qs = (
        Availability.objects
        .filter(date__in=days)
        .select_related("user")
        .prefetch_related("user__groups")
    )

    # Users met invoer in deze week
    users = sorted(
        {av.user for av in av_qs},
        key=lambda u: (_user_group(u).lower(), _user_firstname_cap(u).lower())
    )

    # Matrix
    from collections import defaultdict
    matrix = defaultdict(lambda: {d: {"morning": False, "afternoon": False} for d in days})
    for av in av_qs:
        matrix[av.user][av.date]["morning"] = bool(av.morning)
        matrix[av.user][av.date]["afternoon"] = bool(av.afternoon)

    # Tellen
    counts = {d: {"morning": 0, "afternoon": 0} for d in days}
    for u in users:
        for d in days:
            if matrix[u][d]["morning"]:
                counts[d]["morning"] += 1
            if matrix[u][d]["afternoon"]:
                counts[d]["afternoon"] += 1

    # Dag-context voor template
    days_ctx = []
    for d in days:
        days_ctx.append({
            "date": d,
            "iso": d.isoformat(),
            "weekday_label": date_format(d, "l").capitalize(),
            "morning_count": counts[d]["morning"],
            "afternoon_count": counts[d]["afternoon"],
        })

    # Rijen
    rows = []
    for u in users:
        cells = []
        for d in days:
            cells.append({
                "date": d,
                "morning": matrix[u][d]["morning"],
                "afternoon": matrix[u][d]["afternoon"],
            })
        # data-attrs voor sorteer-JS
        data_attrs_parts = []
        for d in days:
            iso = d.strftime("%Y-%m-%d")
            data_attrs_parts.append(f'data-{iso}-morning="{"1" if matrix[u][d]["morning"] else "0"}"')
            data_attrs_parts.append(f'data-{iso}-afternoon="{"1" if matrix[u][d]["afternoon"] else "0"}"')
        rows.append({
            "group": _user_group(u),
            "firstname": _user_firstname_cap(u),
            "cells": cells,
            "data_attrs": " ".join(data_attrs_parts),
        })

    # Week dropdown alleen huidige → +6mnd
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
    default_sort_slot = f"{days[0].isoformat()}|morning"

    return render(request, "personeelsdashboard/index.html", {
        "monday": monday,
        "week_end": week_end,
        "days_ctx": days_ctx,
        "rows": rows,
        "week_options": week_options,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
        "header_title": header_title,
        "default_sort_slot": default_sort_slot,
    })