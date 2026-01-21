from datetime import date, datetime, time
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import Dagdeel, Shift, UrenMaand, UrenRegel
from core.forms import UrenMaandForm, Hours1DecimalField
from ._helpers import can


def _month_first(d: date) -> date:
    return d.replace(day=1)


def _active_month(today: date) -> date:
    # window 10e -> 10e
    if today.day < 10:
        return _month_first(today + relativedelta(months=-1))
    return _month_first(today)


def _window_for_month(month_first: date):
    # kalendermaand: 1e t/m 1e volgende maand (end exclusive)
    start = month_first
    end = month_first + relativedelta(months=1)
    return start, end

def _deadline_dt_for_month(month_first: date) -> datetime:
    next_month = month_first + relativedelta(months=1)
    dl_date = next_month.replace(day=10)
    dl_dt_naive = datetime.combine(dl_date, time(23, 59, 59))
    return timezone.make_aware(dl_dt_naive, timezone.get_current_timezone())


def _dagdeel_minutes(d: Dagdeel) -> int:
    def to_minutes(t):
        return t.hour * 60 + t.minute

    s = to_minutes(d.start_time)
    e = to_minutes(d.end_time)
    if e == s:
        return 0
    if e > s:
        return e - s
    return (1440 - s) + e


def _dagdeel_hours_1_decimal(d: Dagdeel) -> Decimal:
    mins = _dagdeel_minutes(d)
    if mins <= 0:
        return Decimal("0.0")
    hrs = Decimal(mins) / Decimal(60)
    return hrs.quantize(Decimal("0.1"))


def _shift_period_to_dagdeel_code(period: str) -> str:
    """
    Mapping volgens jouw opmerking:
    - shift.morning -> dagdeel.morning
    - shift.afternoon -> dagdeel.afternoon
    - shift.evening -> dagdeel.pre_evening
    """
    if period == "morning":
        return Dagdeel.CODE_MORNING
    if period == "afternoon":
        return Dagdeel.CODE_AFTERNOON
    return Dagdeel.CODE_PRE_EVENING


@login_required
def urendoorgeven_view(request):
    if not can(request.user, "can_view_urendoorgeven"):
        return HttpResponseForbidden("Geen toegang.")

    today = timezone.localdate()
    active_month = _active_month(today)
    window_start, window_end = _window_for_month(active_month)
    deadline_dt = _deadline_dt_for_month(active_month)

    dagdelen = list(Dagdeel.objects.all().order_by("sort_order"))
    dagdeel_by_id = {d.id: d for d in dagdelen}
    dagdeel_id_by_code = {d.code: d.id for d in dagdelen}

    rows = list(
        UrenRegel.objects.filter(
            user=request.user,
            date__gte=window_start,
            date__lt=window_end,
        ).select_related("dagdeel").order_by("date", "dagdeel__sort_order", "id")
    )

    # maand meta
    maand_obj, _ = UrenMaand.objects.get_or_create(user=request.user, month=active_month)
    maand_form = UrenMaandForm(instance=maand_obj)

    # shifts in window -> planned_by_date: {"YYYY-MM-DD": [dagdeel_id, ...]}
    planned_by_date = {}
    shifts = Shift.objects.filter(
        user=request.user,
        date__gte=window_start,
        date__lt=window_end,
    ).values("date", "period")

    for s in shifts:
        code = _shift_period_to_dagdeel_code(s["period"])
        did = dagdeel_id_by_code.get(code)
        if not did:
            continue
        iso = s["date"].isoformat()
        planned_by_date.setdefault(iso, set()).add(did)

    planned_by_date = {k: sorted(list(v)) for k, v in planned_by_date.items()}
    planned_dates = sorted(list(planned_by_date.keys()))

    # existing hours map for modal prefill: {"YYYY-MM-DD": {"<dagdeel_id>": "8,0"}}
    existing_by_date = {}
    for r in rows:
        iso = r.date.isoformat()
        existing_by_date.setdefault(iso, {})[str(r.dagdeel_id)] = (
            "" if r.actual_hours is None else str(r.actual_hours).replace(".", ",")
        )

    toeslag_rows = [{
        "dagdeel": d,
        "estimated_hours": _dagdeel_hours_1_decimal(d),
    } for d in dagdelen]

    # ------------- POST handlers -------------
    if request.method == "POST":
        action = request.POST.get("action", "save_all")

        # Guard: als periode is doorgeschoven terwijl tab open stond
        current_active = _active_month(timezone.localdate())
        if current_active != active_month:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "Periode verlopen. Ververs de pagina."}, status=400)
            messages.error(request, "Deze urenperiode is verlopen. Ververs de pagina.")
            return redirect("urendoorgeven")
        
        # Guard: deadline verstreken (server-side)
        if timezone.now() > deadline_dt:
            msg = "Deadline verstreken. Je kunt geen uren meer aanpassen voor deze maand."
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("urendoorgeven")

        # A) MODAL batch upsert: één klik -> direct opslaan (date + meerdere dagdelen+hours)
        if action == "modal_batch_upsert":
            ds = (request.POST.get("date") or "").strip()
            dagdeel_ids = request.POST.getlist("dagdeel_id")
            hours_list = request.POST.getlist("hours")

            # parse date
            try:
                y, m, d = [int(p) for p in ds.split("-")]
                row_date = date(y, m, d)
            except Exception:
                return JsonResponse({"ok": False, "error": "Ongeldige datum."}, status=400)

            if not (window_start <= row_date < window_end):
                return JsonResponse({"ok": False, "error": "Datum valt buiten de periode."}, status=400)

            if len(dagdeel_ids) != len(hours_list):
                return JsonResponse({"ok": False, "error": "Ongeldige modal data."}, status=400)

            saved_rows = []
            with transaction.atomic():
                for did, hs in zip(dagdeel_ids, hours_list):
                    try:
                        dagdeel_id = int(did)
                    except Exception:
                        continue

                    dagdeel = dagdeel_by_id.get(dagdeel_id)
                    if not dagdeel:
                        continue

                    # leeg -> skip (geen save vanuit modal)
                    hs = (hs or "").strip()
                    if hs == "":
                        continue

                    f = Hours1DecimalField({"hours": hs})
                    if not f.is_valid():
                        return JsonResponse({"ok": False, "error": "Ongeldige uren (max 1 decimaal)."}, status=400)
                    cleaned_hours = f.cleaned_data["hours"]
                    if cleaned_hours is None:
                        continue

                    obj, created = UrenRegel.objects.get_or_create(
                        user=request.user,
                        date=row_date,
                        dagdeel=dagdeel,
                        defaults={
                            "month": active_month,
                            "actual_hours": cleaned_hours,
                            "shift": None,
                            "source": "manual",
                        }
                    )
                    if not created:
                        obj.month = active_month
                        obj.actual_hours = cleaned_hours
                        obj.shift = None
                        obj.source = "manual"
                        obj.save(update_fields=["month", "actual_hours", "shift", "source", "updated_at"])

                    saved_rows.append({
                        "date": obj.date.isoformat(),
                        "date_label": obj.date.strftime("%d-%m-%Y"),
                        "dagdeel_id": obj.dagdeel_id,
                        "dagdeel_label": obj.dagdeel.get_code_display(),
                        "start": obj.dagdeel.start_time.strftime("%H:%M"),
                        "end": obj.dagdeel.end_time.strftime("%H:%M"),
                        "allowance_pct": obj.dagdeel.allowance_pct,
                        "actual_hours": str(obj.actual_hours).replace(".", ","),
                    })

            return JsonResponse({"ok": True, "rows": saved_rows})

        # B) Autosave (AJAX): uren + km
        if action == "autosave":
            dates = request.POST.getlist("row_date")
            dagdeel_ids = request.POST.getlist("row_dagdeel_id")
            hours_list = request.POST.getlist("row_hours")

            if not (len(dates) == len(dagdeel_ids) == len(hours_list)):
                return JsonResponse({"ok": False, "error": "Formulier ongeldig."}, status=400)

            maand_form = UrenMaandForm(request.POST, instance=maand_obj)
            if not maand_form.is_valid():
                return JsonResponse({"ok": False, "error": "Kilometers ongeldig."}, status=400)

            with transaction.atomic():
                maand_form.save()

                for ds, did, hs in zip(dates, dagdeel_ids, hours_list):
                    # parse date
                    try:
                        y, m, d = [int(p) for p in ds.split("-")]
                        row_date = date(y, m, d)
                    except Exception:
                        continue

                    if not (window_start <= row_date < window_end):
                        continue

                    try:
                        dagdeel_id = int(did)
                    except Exception:
                        continue

                    dagdeel = dagdeel_by_id.get(dagdeel_id)
                    if not dagdeel:
                        continue

                    f = Hours1DecimalField({"hours": hs})
                    if not f.is_valid():
                        return JsonResponse({"ok": False, "error": "Ongeldige uren (max 1 decimaal)."}, status=400)
                    cleaned_hours = f.cleaned_data["hours"]

                    existing_obj = UrenRegel.objects.filter(
                        user=request.user,
                        date=row_date,
                        dagdeel_id=dagdeel_id
                    ).first()

                    # leeg = delete
                    if cleaned_hours is None:
                        if existing_obj:
                            existing_obj.delete()
                        continue

                    if existing_obj:
                        existing_obj.actual_hours = cleaned_hours
                        existing_obj.month = active_month
                        existing_obj.shift = None
                        existing_obj.source = "manual"
                        existing_obj.save(update_fields=["actual_hours", "month", "shift", "source", "updated_at"])
                    else:
                        UrenRegel.objects.create(
                            user=request.user,
                            month=active_month,
                            date=row_date,
                            dagdeel=dagdeel,
                            actual_hours=cleaned_hours,
                            shift=None,
                            source="manual",
                        )

            return JsonResponse({"ok": True})

        # C) Save all (normale submit)
        dates = request.POST.getlist("row_date")
        dagdeel_ids = request.POST.getlist("row_dagdeel_id")
        hours_list = request.POST.getlist("row_hours")

        if not (len(dates) == len(dagdeel_ids) == len(hours_list)):
            messages.error(request, "Formulier is ongeldig.")
            return redirect("urendoorgeven")

        maand_form = UrenMaandForm(request.POST, instance=maand_obj)
        if not maand_form.is_valid():
            messages.error(request, "Kilometers ongeldig.")
            return redirect("urendoorgeven")

        with transaction.atomic():
            maand_form.save()

            for ds, did, hs in zip(dates, dagdeel_ids, hours_list):
                try:
                    y, m, d = [int(p) for p in ds.split("-")]
                    row_date = date(y, m, d)
                except Exception:
                    continue

                if not (window_start <= row_date < window_end):
                    continue

                try:
                    dagdeel_id = int(did)
                except Exception:
                    continue

                dagdeel = dagdeel_by_id.get(dagdeel_id)
                if not dagdeel:
                    continue

                f = Hours1DecimalField({"hours": hs})
                if not f.is_valid():
                    messages.error(request, "Ongeldige uren (max 1 decimaal).")
                    return redirect("urendoorgeven")
                cleaned_hours = f.cleaned_data["hours"]

                existing_obj = UrenRegel.objects.filter(
                    user=request.user,
                    date=row_date,
                    dagdeel_id=dagdeel_id
                ).first()

                if cleaned_hours is None:
                    if existing_obj:
                        existing_obj.delete()
                    continue

                if existing_obj:
                    existing_obj.actual_hours = cleaned_hours
                    existing_obj.month = active_month
                    existing_obj.shift = None
                    existing_obj.source = "manual"
                    existing_obj.save(update_fields=["actual_hours", "month", "shift", "source", "updated_at"])
                else:
                    UrenRegel.objects.create(
                        user=request.user,
                        month=active_month,
                        date=row_date,
                        dagdeel=dagdeel,
                        actual_hours=cleaned_hours,
                        shift=None,
                        source="manual",
                    )

        messages.success(request, "Uren opgeslagen.")
        return redirect("urendoorgeven")

    context = {
        "active_month": active_month,
        "window_start": window_start,
        "window_end": window_end,
        "window_start_iso": window_start.isoformat(),
        "window_end_iso": window_end.isoformat(),  # exclusive
        "deadline_local_str": timezone.localtime(deadline_dt).strftime("%d-%m-%Y %H:%M"),
        "deadline_iso": deadline_dt.isoformat(),
        "toeslag_rows": toeslag_rows,
        "rows": rows,
        "maand_form": maand_form,
        "planned_dates": planned_dates,
        "planned_by_date": planned_by_date,
        "existing_by_date": existing_by_date,
    }
    return render(request, "urendoorgeven/index.html", context)
