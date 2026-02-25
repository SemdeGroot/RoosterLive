import json
import zoneinfo
from datetime import date, time, timedelta, datetime as dt

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import BaxterProductie, BaxterProductieSnapshotPunt
from core.views._helpers import can

AMSTERDAM = zoneinfo.ZoneInfo("Europe/Amsterdam")


# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------

def _check_api_key(request) -> bool:
    auth_header = request.headers.get("Authorization", "")
    expected    = f"Token {settings.BAXTER_WATCHDOG_API_KEY}"
    return auth_header == expected


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _iso_week_bounds(iso_year: int, iso_week: int) -> tuple[date, date]:
    # ISO week: maandag..zondag
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    sunday = date.fromisocalendar(iso_year, iso_week, 7)
    return monday, sunday

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

    # Watchdog levert lokale Amsterdam-tijd als naive string.
    # make_aware zorgt dat Django dit correct als UTC opslaat (USE_TZ=True).
    aware_timestamp = timezone.make_aware(
        dt.combine(record_date, record_time), AMSTERDAM
    )

    BaxterProductieSnapshotPunt.objects.update_or_create(
        machine_id=machine_id,
        timestamp=aware_timestamp,
        defaults={"aantal_zakjes": aantal},
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

    # Dagrecords (per machine per dag)
    records = BaxterProductie.objects.filter(date=vandaag)
    machines = {r.machine_id: r.aantal_zakjes for r in records}

    # Week totalen
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

    # Snapshot window: vandaag in Amsterdam tijd, maar DB is UTC aware
    dag_start = timezone.make_aware(dt.combine(vandaag, time.min), AMSTERDAM)
    dag_eind  = timezone.make_aware(dt.combine(vandaag, time.max), AMSTERDAM)

    snapshot_qs = (
        BaxterProductieSnapshotPunt.objects
        .filter(timestamp__gte=dag_start, timestamp__lte=dag_eind)
        .order_by("timestamp")
    )

    # Laatste snapshot = "laatst bijgewerkt" (zakjes/file tijd)
    last_snapshot = snapshot_qs.last()
    last_snapshot_local_iso = (
        last_snapshot.timestamp.astimezone(AMSTERDAM).isoformat()
        if last_snapshot else None
    )

    intradag = []
    for s in snapshot_qs:
        lokale_ts = s.timestamp.astimezone(AMSTERDAM)
        intradag.append({
            "tijd":       lokale_ts.strftime("%H:%M"),  # blijft handig voor labels
            "timestamp":  lokale_ts.isoformat(),        # robuust voor parsing/ordering
            "machine_id": s.machine_id,
            "zakjes":     s.aantal_zakjes,
        })

    return JsonResponse({
        "datum":              str(vandaag),
        "machines":           machines,
        "week_totaal":        week_totaal,
        "week_dagen":         week_dagen,
        "intradag":           intradag,
        "last_snapshot_time": last_snapshot_local_iso,
    })

# -------------------------------------------------------
# API: GESCHIEDENIS
# -------------------------------------------------------

@login_required
def machine_statistieken_api_geschiedenis(request):
    if not can(request.user, "can_view_machine_statistieken"):
        return JsonResponse({"error": "Forbidden"}, status=403)

    bereik  = request.GET.get("bereik", "dagen7")
    vandaag = timezone.localdate()

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
    # Laatste N "datums met data" (ongeacht weekdag).
    # Vandaag telt mee als er records voor vandaag bestaan.
    # We tonen geen lege dagen (geen records).

    lookback_days = 365 if dagen <= 30 else 730
    vanaf = vandaag - timedelta(days=lookback_days)

    records = (
        BaxterProductie.objects
        .filter(date__gte=vanaf, date__lte=vandaag)
        .order_by("date", "machine_id")
    )

    per_datum: dict[date, dict] = {}
    for r in records:
        per_datum.setdefault(r.date, {})
        per_datum[r.date][r.machine_id] = r.aantal_zakjes

    # Neem de laatste N datums die bestaan in het model (dus met data)
    datums = sorted(per_datum.keys(), reverse=True)[:dagen]
    datums.sort()  # output chronologisch

    return [{"datum": str(d), "machines": per_datum[d]} for d in datums]

def _week_bereik(vandaag: date, weken: int) -> list:
    # Toon altijd: week n, n-1, ... (exact 'weken' weken).
    # Week n mag lopend zijn; alle voorgaande weken zijn volledige ISO-weken (Ma..Zo).
    # We query-en bewust t/m zondag van de huidige week zodat het fetch-window elke week Ma..Zo kan afdekken.

    current_ma = _week_start(vandaag)
    current_zo = current_ma + timedelta(days=6)

    fetch_start = current_ma - timedelta(weeks=weken + 4)
    fetch_end = current_zo  # niet vandaag, maar zondag van huidige week

    records = (
        BaxterProductie.objects
        .filter(date__gte=fetch_start, date__lte=fetch_end)
        .order_by("date", "machine_id")
    )

    per_week: dict[tuple[int, int], dict[str, int]] = {}

    for r in records:
        iso_year, iso_week, _ = r.date.isocalendar()
        key = (iso_year, iso_week)
        per_week.setdefault(key, {})
        per_week[key][r.machine_id] = per_week[key].get(r.machine_id, 0) + r.aantal_zakjes

    # Bouw expliciet de wekenlijst: n, n-1, ..., n-(weken-1)
    week_keys: list[tuple[int, int]] = []
    cursor_ma = current_ma
    for _ in range(weken):
        iso_year, iso_week, _ = cursor_ma.isocalendar()
        week_keys.append((iso_year, iso_week))
        cursor_ma -= timedelta(weeks=1)

    # Output chronologisch (oud -> nieuw) voor de grafieken
    week_keys.reverse()

    out = []
    for (jaar, week) in week_keys:
        out.append({
            "week": f"W{week:02d}",
            "jaar": jaar,
            "machines": per_week.get((jaar, week), {}),
        })

    return out