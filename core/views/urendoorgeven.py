from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import UrenInvoer, UrenDoorgevenSettings
from core.forms import UrenInvoerForm, UrenDoorgevenSettingsForm
from ._helpers import can


def _month_first(d: date) -> date:
    return d.replace(day=1)


def _deadline_for_month(month_first: date) -> datetime:
    """
    Deadline = 10e van de maand ná de geregistreerde maand, 23:59:59 (lokale tz).
    Voor maand 2026-01-01 => deadline 2026-02-10 23:59:59.
    """
    next_month = month_first + relativedelta(months=1)
    dl_date = next_month.replace(day=10)
    dl_dt_naive = datetime.combine(dl_date, time(23, 59, 59))
    return timezone.make_aware(dl_dt_naive, timezone.get_current_timezone())


def _target_month_default(today: date) -> date:
    """
    Default: vorige kalendermaand doorgeven.
    """
    prev = today + relativedelta(months=-1)
    return prev.replace(day=1)


@login_required
def urendoorgeven_view(request):
    if not can(request.user, "can_view_urendoorgeven"):
        return HttpResponseForbidden("Geen toegang.")

    can_edit = can(request.user, "can_edit_urendoorgeven")

    today = timezone.localdate()
    target_month = _target_month_default(today)
    deadline_dt = _deadline_for_month(target_month)
    now = timezone.localtime()

    settings_obj = UrenDoorgevenSettings.load()

    instance = UrenInvoer.objects.filter(user=request.user, month=target_month).first()
    uren_form = UrenInvoerForm(instance=instance)
    settings_form = UrenDoorgevenSettingsForm(instance=settings_obj)

    if request.method == "POST":
        kind = request.POST.get("form_kind")

        # 1) Settings update (toeslag %)
        if kind == "settings":
            if not can_edit:
                messages.error(request, "Geen rechten om de toeslag aan te passen.")
                return redirect("urendoorgeven")

            settings_form = UrenDoorgevenSettingsForm(request.POST, instance=settings_obj)
            if settings_form.is_valid():
                obj = settings_form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                messages.success(request, "Toeslag percentage opgeslagen.")
                return redirect("urendoorgeven")

            messages.error(request, "Opslaan toeslag mislukt. Controleer het veld.")
            # fallthrough naar render

        # 2) Uren submit/update
        elif kind == "hours":
            # Deadline guard
            if now > deadline_dt:
                messages.error(
                    request,
                    f"Deadline overschreden. Uren voor {target_month.strftime('%m-%Y')} konden worden doorgegeven tot "
                    f"{timezone.localtime(deadline_dt).strftime('%d-%m-%Y %H:%M')}."
                )
                return redirect("urendoorgeven")

            uren_form = UrenInvoerForm(request.POST, instance=instance)
            if uren_form.is_valid():
                obj = uren_form.save(commit=False)
                obj.user = request.user
                obj.month = target_month

                # Snapshot van huidige toeslag instelling
                obj.evening_allowance_pct_used = settings_obj.evening_allowance_pct
                obj.save()

                messages.success(request, f"Uren opgeslagen voor {target_month.strftime('%m-%Y')}.")
                return redirect("urendoorgeven")

            messages.error(request, "Opslaan mislukt. Controleer de velden.")
        else:
            messages.error(request, "Onbekende actie.")
            return redirect("urendoorgeven")

    context = {
        "target_month": target_month,
        "deadline_iso": deadline_dt.isoformat(),
        "deadline_local_str": timezone.localtime(deadline_dt).strftime("%d-%m-%Y %H:%M"),
        "deadline_passed": now > deadline_dt,
        "uren_form": uren_form,
        "settings_obj": settings_obj,
        "settings_form": settings_form,
        "can_edit": can_edit,
    }
    return render(request, "urendoorgeven/index.html", context)
