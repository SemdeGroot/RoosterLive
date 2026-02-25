import json
from collections import defaultdict
from datetime import date, time, timedelta, datetime as dt
from django.utils import timezone

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import BaxterProductie, BaxterProductieSnapshot
from core.views._helpers import can


# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------

def _check_api_key(request) -> bool:
    auth_header = request.headers.get("Authorization", "")
    expected    = f"Token {settings.BAXTER_WATCHDOG_API_KEY}"
    return auth_header == expected


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _iso_week(d: date) -> str:
    return f"W{d.isocalendar()[1]:02d}"


# -------------------------------------------------------
# INGEST (watchdog → database)
# -------------------------------------------------------

@csrf_exempt
@require_POST
def machine_statistieken_ingest(request):
    if not _check_api_key(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    required = {"machine_id", "date", "time", "aantal_zakjes"}
    missing  = required - body.keys()
    if missing:
        return JsonResponse({"error": f"Missing fields: {missing}"}, status=400)

    try:
        record_date = date.fromisoformat(body["date"])
        record_time = time.fromisoformat(body["time"])
        aantal      = int(body["aantal_zakjes"])
        machine_id  = str(body["machine_id"]).strip().upper()
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": f"Invalid field value: {e}"}, status=400)

    obj, created = BaxterProductie.objects.update_or_create(
        machine_id=machine_id,
        date=record_date,
        defaults={
            "time":          record_time,
            "aantal_zakjes": aantal,
        },
    )

    # Sla meetpunt op als snapshot voor de intradag-grafiek.
    # Naive datetime: watchdog levert lokale tijd, geen UTC-conversie.
    BaxterProductieSnapshot.objects.create(
        machine_id=machine_id,
        timestamp=dt.combine(record_date, record_time),
        aantal_zakjes=aantal,
    )

    return JsonResponse({
        "status":  "created" if created else "updated",
        "machine": machine_id,
        "date":    str(record_date),
        "zakjes":  aantal,
    }, status=201 if created else 200)


# -------------------------------------------------------
# PAGINAWEERGAVE
# -------------------------------------------------------

@login_required
def machine_statistieken_view(request):
    if not can(request.user, "can_view_machine_statistieken"):
        return HttpResponseForbidden("Geen toegang.")

    return render(request, "machine-statistieken/machine_statistieken.html")


# -------------------------------------------------------
# API: VANDAAG
# -------------------------------------------------------

@login_required
def machine_statistieken_api_vandaag(request):
    if not can(request.user, "can_view_machine_statistieken"):
        return JsonResponse({"error": "Forbidden"}, status=403)

    vandaag = timezone.localdate()
    maandag = _week_start(vandaag)

    records     = BaxterProductie.objects.filter(date=vandaag)
    machines    = {r.machine_id: r.aantal_zakjes for r in records}
    last_update = max((r.updated_at for r in records), default=None)

    week_records = (
        BaxterProductie.objects
        .filter(date__gte=maandag, date__lte=vandaag)
        .order_by("date", "machine_id")
    )
    week_totaal = sum(r.aantal_zakjes for r in week_records)

    per_dag: dict[str, dict] = {}
    for r in week_records:
        key = str(r.date)
        per_dag.setdefault(key, {})
        per_dag[key][r.machine_id] = r.aantal_zakjes

    week_dagen = [
        {"datum": dag, "machines": mach}
        for dag, mach in sorted(per_dag.items())
    ]

    # Timestamps zijn naive lokale tijd opgeslagen - filter op naive daggrens
    # zodat Django geen UTC-vergelijking doet die een uur verschuift.
    dag_start = dt.combine(vandaag, time.min)
    dag_eind  = dt.combine(vandaag, time.max)

    snapshot_qs = (
        BaxterProductieSnapshot.objects
        .filter(timestamp__gte=dag_start, timestamp__lte=dag_eind)
        .order_by("timestamp")
    )

    intradag = []
    for s in snapshot_qs:
        intradag.append({
            "tijd":       s.timestamp.strftime("%H:%M"),
            "machine_id": s.machine_id,
            "zakjes":     s.aantal_zakjes,
        })

    return JsonResponse({
        "datum":               str(vandaag),
        "machines":            machines,
        "week_totaal":         week_totaal,
        "week_dagen":          week_dagen,
        "intradag":            intradag,
        "last_machine_update": last_update.isoformat() if last_update else None,
    })


# -------------------------------------------------------
# API: GESCHIEDENIS
# -------------------------------------------------------

@login_required
def machine_statistieken_api_geschiedenis(request):
    if not can(request.user, "can_view_machine_statistieken"):
        return JsonResponse({"error": "Forbidden"}, status=403)

    bereik  = request.GET.get("bereik", "dagen7")
    vandaag = date.today()

    bereik_map = {
        "dagen7":  lambda: _dag_bereik(vandaag, 7),
        "dagen30": lambda: _dag_bereik(vandaag, 30),
        "weken4":  lambda: _week_bereik(vandaag, 4),
        "weken26": lambda: _week_bereik(vandaag, 26),
        "weken52": lambda: _week_bereik(vandaag, 52),
    }

    handler = bereik_map.get(bereik)
    if not handler:
        return JsonResponse({"error": "Onbekend bereik"}, status=400)

    return JsonResponse({"data": handler()})


def _dag_bereik(vandaag: date, dagen: int) -> list:
    vanaf   = vandaag - timedelta(days=dagen - 1)
    records = (
        BaxterProductie.objects
        .filter(date__gte=vanaf, date__lte=vandaag)
        .order_by("date", "machine_id")
    )

    per_datum: dict[str, dict] = {}
    for r in records:
        key = str(r.date)
        per_datum.setdefault(key, {})
        per_datum[key][r.machine_id] = r.aantal_zakjes

    return [
        {"datum": datum, "machines": machines}
        for datum, machines in sorted(per_datum.items())
    ]


def _week_bereik(vandaag: date, weken: int) -> list:
    vanaf   = vandaag - timedelta(weeks=weken)
    records = (
        BaxterProductie.objects
        .filter(date__gte=vanaf, date__lte=vandaag)
        .order_by("date", "machine_id")
    )

    per_week: dict[str, dict]  = {}
    per_week_jaar: dict[str, int] = {}

    for r in records:
        iso        = r.date.isocalendar()
        week_key   = f"W{iso[1]:02d}"
        iso_jaar   = iso[0]  # ISO-jaar kan afwijken van kalenderjaar (week 1 grens)

        per_week.setdefault(week_key, {})
        per_week[week_key][r.machine_id] = (
            per_week[week_key].get(r.machine_id, 0) + r.aantal_zakjes
        )
        # Eerste datum in de week bepaalt het jaar-label
        if week_key not in per_week_jaar:
            per_week_jaar[week_key] = iso_jaar

    return [
        {"week": week, "jaar": per_week_jaar[week], "machines": machines}
        for week, machines in sorted(per_week.items())
    ]