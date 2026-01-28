from datetime import date, datetime, time as dtime
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import Dagdeel, Shift, UrenMaand, UrenRegel, UrenDag
from core.forms import UrenMaandForm, UrenDagInputForm
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
    dl_dt_naive = datetime.combine(dl_date, dtime(23, 59, 59))
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


# --------------------------
# NEW: helpers for deriving UrenRegel from 1 day input
# --------------------------
def _time_to_minutes(t: dtime) -> int:
    return t.hour * 60 + t.minute


def _interval_minutes(start_t: dtime, end_t: dtime) -> tuple[int, int]:
    """
    Represent (start,end) on a line where end may be +1440 if it crosses midnight.
    """
    s = _time_to_minutes(start_t)
    e = _time_to_minutes(end_t)
    if e <= s:
        e += 1440
    return s, e


def _dagdeel_interval_minutes(d: Dagdeel) -> tuple[int, int]:
    s = _time_to_minutes(d.start_time)
    e = _time_to_minutes(d.end_time)
    if e <= s:
        e += 1440
    return s, e


def _overlap(a_s, a_e, b_s, b_e) -> int:
    s = max(a_s, b_s)
    e = min(a_e, b_e)
    return max(0, e - s)


def _quantize_1_decimal(hours: Decimal) -> Decimal:
    return hours.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _compute_minutes_per_dagdeel(start_t: dtime, end_t: dtime, break_hours: Decimal, dagdelen: list[Dagdeel]) -> dict[int, int]:
    """
    Return minutes per dagdeel-id after distributing break time proportionally.
    """
    work_s, work_e = _interval_minutes(start_t, end_t)

    raw: dict[int, int] = {}
    total = 0

    for d in dagdelen:
        d_s, d_e = _dagdeel_interval_minutes(d)

        mins = _overlap(work_s, work_e, d_s, d_e)
        # also check shifted dagdeel interval (for midnight-crossing cases)
        mins = max(mins, _overlap(work_s, work_e, d_s + 1440, d_e + 1440))

        if mins > 0:
            raw[d.id] = mins
            total += mins

    if total <= 0:
        return {}

    # break in minutes
    bh = break_hours if break_hours is not None else Decimal("0.0")
    bh = _quantize_1_decimal(bh)
    break_mins = int((bh * Decimal(60)).to_integral_value(rounding=ROUND_HALF_UP))
    break_mins = max(0, break_mins)

    if break_mins >= total:
        raise ValueError("Pauze is groter dan of gelijk aan de gewerkte tijd.")

    if break_mins == 0:
        return raw

    # distribute break proportionally, ensure exact sum of reductions = break_mins
    items = list(raw.items())
    reductions: dict[int, int] = {}
    taken = 0

    for i, (did, mins) in enumerate(items):
        if i == len(items) - 1:
            red = break_mins - taken
        else:
            red = int(round((mins / total) * break_mins))
            red = min(red, mins)
            taken += red
        reductions[did] = red

    adjusted: dict[int, int] = {}
    for did, mins in raw.items():
        adjusted[did] = max(0, mins - reductions.get(did, 0))

    return adjusted


def _regen_urenregels_from_day_input(*, user, active_month, row_date, start_t, end_t, break_hours, dagdelen):
    """
    Delete existing UrenRegel for date, then recreate based on overlaps.
    """
    mins_map = _compute_minutes_per_dagdeel(start_t, end_t, break_hours, dagdelen)

    UrenRegel.objects.filter(user=user, date=row_date).delete()

    for d in dagdelen:
        mins = mins_map.get(d.id, 0)
        if mins <= 0:
            continue

        hours = _quantize_1_decimal(Decimal(mins) / Decimal(60))
        if hours <= 0:
            continue

        UrenRegel.objects.create(
            user=user,
            month=active_month,
            date=row_date,
            dagdeel=d,
            actual_hours=hours,
            shift=None,
            source="manual",
        )


@login_required
def urendoorgeven_view(request):
    if not can(request.user, "can_view_urendoorgeven"):
        return HttpResponseForbidden("Geen toegang.")

    today = timezone.localdate()
    active_month = _active_month(today)
    window_start, window_end = _window_for_month(active_month)
    deadline_dt = _deadline_dt_for_month(active_month)

    dagdelen = list(Dagdeel.objects.all().order_by("sort_order"))
    dagdeel_id_by_code = {d.code: d.id for d in dagdelen}

    # rows in window (NEW model)
    day_rows = list(
        UrenDag.objects.filter(
            user=request.user,
            date__gte=window_start,
            date__lt=window_end,
        ).order_by("date", "id")
    )

    # maand meta
    maand_obj, _ = UrenMaand.objects.get_or_create(user=request.user, month=active_month)
    maand_form = UrenMaandForm(instance=maand_obj)

    # planned shifts for calendar markers
    planned_by_date: dict[str, list[int]] = {}
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

    # existing map for modal prefill
    existing_by_date: dict[str, dict[str, str]] = {}
    for r in day_rows:
        iso = r.date.isoformat()
        existing_by_date[iso] = {
            "start": r.start_time.strftime("%H:%M"),
            "end": r.end_time.strftime("%H:%M"),
            "break": str(r.break_hours).replace(".", ","),
        }

    toeslag_rows = [{
        "dagdeel": d,
        "estimated_hours": _dagdeel_hours_1_decimal(d),
    } for d in dagdelen]

    # --------------------------
    # POST handlers
    # --------------------------
    if request.method == "POST":
        action = request.POST.get("action", "save_all")

        # Guard: periode verschoven
        current_active = _active_month(timezone.localdate())
        if current_active != active_month:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "Periode verlopen. Ververs de pagina."}, status=400)
            messages.error(request, "Deze urenperiode is verlopen. Ververs de pagina.")
            return redirect("urendoorgeven")

        # Guard: deadline verstreken
        if timezone.now() > deadline_dt:
            msg = "Deadline verstreken. Je kunt geen uren meer aanpassen voor deze maand."
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("urendoorgeven")

        # A) Modal upsert (per dag)
        if action == "modal_day_upsert":
            ds = (request.POST.get("date") or "").strip()
            start_s = (request.POST.get("start_time") or "").strip()
            end_s = (request.POST.get("end_time") or "").strip()
            break_s = (request.POST.get("break_hours") or "").strip()

            # parse date
            try:
                y, m, d = [int(p) for p in ds.split("-")]
                row_date = date(y, m, d)
            except Exception:
                return JsonResponse({"ok": False, "error": "Ongeldige datum."}, status=400)

            if not (window_start <= row_date < window_end):
                return JsonResponse({"ok": False, "error": "Datum valt buiten de periode."}, status=400)

            f = UrenDagInputForm({"start_time": start_s, "end_time": end_s, "break_hours": break_s})
            if not f.is_valid():
                return JsonResponse({"ok": False, "error": "Ongeldige invoer (tijd/pauze)."}, status=400)

            start_t = f.cleaned_data["start_time"]
            end_t = f.cleaned_data["end_time"]
            break_h = f.cleaned_data["break_hours"]

            try:
                with transaction.atomic():
                    obj, created = UrenDag.objects.get_or_create(
                        user=request.user,
                        date=row_date,
                        defaults={
                            "month": active_month,
                            "start_time": start_t,
                            "end_time": end_t,
                            "break_hours": break_h,
                        }
                    )
                    if not created:
                        obj.month = active_month
                        obj.start_time = start_t
                        obj.end_time = end_t
                        obj.break_hours = break_h
                        obj.save(update_fields=["month", "start_time", "end_time", "break_hours", "updated_at"])

                    _regen_urenregels_from_day_input(
                        user=request.user,
                        active_month=active_month,
                        row_date=row_date,
                        start_t=start_t,
                        end_t=end_t,
                        break_hours=break_h,
                        dagdelen=dagdelen,
                    )
            except ValueError as e:
                return JsonResponse({"ok": False, "error": str(e)}, status=400)

            return JsonResponse({
                "ok": True,
                "row": {
                    "date": row_date.isoformat(),
                    "date_label": row_date.strftime("%d-%m-%Y"),
                    "start": start_t.strftime("%H:%M"),
                    "end": end_t.strftime("%H:%M"),
                    "break": str(break_h).replace(".", ","),
                }
            })

        # B) Autosave (AJAX): per dag
        if action == "autosave_day":
            dates = request.POST.getlist("row_date")
            starts = request.POST.getlist("row_start")
            ends = request.POST.getlist("row_end")
            breaks = request.POST.getlist("row_break")

            if not (len(dates) == len(starts) == len(ends) == len(breaks)):
                return JsonResponse({"ok": False, "error": "Formulier ongeldig."}, status=400)

            maand_form = UrenMaandForm(request.POST, instance=maand_obj)
            if not maand_form.is_valid():
                return JsonResponse({"ok": False, "error": "Kilometers ongeldig."}, status=400)

            try:
                with transaction.atomic():
                    maand_form.save()

                    for ds, st, en, br in zip(dates, starts, ends, breaks):
                        # parse date
                        try:
                            y, m, d = [int(p) for p in ds.split("-")]
                            row_date = date(y, m, d)
                        except Exception:
                            continue

                        if not (window_start <= row_date < window_end):
                            continue

                        st = (st or "").strip()
                        en = (en or "").strip()
                        br = (br or "").strip()

                        # all empty -> delete day + derived regels
                        if st == "" and en == "" and br == "":
                            UrenDag.objects.filter(user=request.user, date=row_date).delete()
                            UrenRegel.objects.filter(user=request.user, date=row_date).delete()
                            continue

                        f = UrenDagInputForm({"start_time": st, "end_time": en, "break_hours": br})
                        if not f.is_valid():
                            return JsonResponse({"ok": False, "error": "Ongeldige invoer (tijd/pauze)."}, status=400)

                        start_t = f.cleaned_data["start_time"]
                        end_t = f.cleaned_data["end_time"]
                        break_h = f.cleaned_data["break_hours"]

                        obj, created = UrenDag.objects.get_or_create(
                            user=request.user,
                            date=row_date,
                            defaults={
                                "month": active_month,
                                "start_time": start_t,
                                "end_time": end_t,
                                "break_hours": break_h,
                            }
                        )
                        if not created:
                            obj.month = active_month
                            obj.start_time = start_t
                            obj.end_time = end_t
                            obj.break_hours = break_h
                            obj.save(update_fields=["month", "start_time", "end_time", "break_hours", "updated_at"])

                        _regen_urenregels_from_day_input(
                            user=request.user,
                            active_month=active_month,
                            row_date=row_date,
                            start_t=start_t,
                            end_t=end_t,
                            break_hours=break_h,
                            dagdelen=dagdelen,
                        )
            except ValueError as e:
                return JsonResponse({"ok": False, "error": str(e)}, status=400)

            return JsonResponse({"ok": True})

        # C) Save all (normale submit) – zelfde logica als autosave
        if action == "save_all":
            dates = request.POST.getlist("row_date")
            starts = request.POST.getlist("row_start")
            ends = request.POST.getlist("row_end")
            breaks = request.POST.getlist("row_break")

            if not (len(dates) == len(starts) == len(ends) == len(breaks)):
                messages.error(request, "Formulier ongeldig.")
                return redirect("urendoorgeven")

            maand_form = UrenMaandForm(request.POST, instance=maand_obj)
            if not maand_form.is_valid():
                messages.error(request, "Kilometers ongeldig.")
                return redirect("urendoorgeven")

            try:
                with transaction.atomic():
                    maand_form.save()

                    for ds, st, en, br in zip(dates, starts, ends, breaks):
                        try:
                            y, m, d = [int(p) for p in ds.split("-")]
                            row_date = date(y, m, d)
                        except Exception:
                            continue

                        if not (window_start <= row_date < window_end):
                            continue

                        st = (st or "").strip()
                        en = (en or "").strip()
                        br = (br or "").strip()

                        if st == "" and en == "" and br == "":
                            UrenDag.objects.filter(user=request.user, date=row_date).delete()
                            UrenRegel.objects.filter(user=request.user, date=row_date).delete()
                            continue

                        f = UrenDagInputForm({"start_time": st, "end_time": en, "break_hours": br})
                        if not f.is_valid():
                            messages.error(request, "Ongeldige invoer (tijd/pauze).")
                            return redirect("urendoorgeven")

                        start_t = f.cleaned_data["start_time"]
                        end_t = f.cleaned_data["end_time"]
                        break_h = f.cleaned_data["break_hours"]

                        obj, created = UrenDag.objects.get_or_create(
                            user=request.user,
                            date=row_date,
                            defaults={
                                "month": active_month,
                                "start_time": start_t,
                                "end_time": end_t,
                                "break_hours": break_h,
                            }
                        )
                        if not created:
                            obj.month = active_month
                            obj.start_time = start_t
                            obj.end_time = end_t
                            obj.break_hours = break_h
                            obj.save(update_fields=["month", "start_time", "end_time", "break_hours", "updated_at"])

                        _regen_urenregels_from_day_input(
                            user=request.user,
                            active_month=active_month,
                            row_date=row_date,
                            start_t=start_t,
                            end_t=end_t,
                            break_hours=break_h,
                            dagdelen=dagdelen,
                        )
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("urendoorgeven")

            messages.success(request, "Uren opgeslagen.")
            return redirect("urendoorgeven")

        # fallback
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
        "rows": day_rows,
        "maand_form": maand_form,
        "planned_dates": planned_dates,
        "planned_by_date": planned_by_date,
        "existing_by_date": existing_by_date,
        "dagdelen": dagdelen,  # handig voor JSON meta
    }
    return render(request, "urendoorgeven/index.html", context)