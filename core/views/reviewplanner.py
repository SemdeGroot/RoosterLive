from datetime import datetime
from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import ReviewPlanner, MedicatieReviewAfdeling
from core.forms import ReviewPlannerForm
from ._helpers import can


def _parse_dmy(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d-%m-%Y").date()
    except Exception:
        return None


def _parse_hhmm(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%H:%M").time()
    except Exception:
        return None


def _serialize_row(obj: ReviewPlanner):
    return {
        "id": obj.id,
        "datum": obj.datum.strftime("%d-%m-%Y") if obj.datum else "",
        "afdeling_id": obj.afdeling_id or "",
        "status": obj.status,
        "status_label": obj.get_status_display(),
        "arts": obj.arts or "",
        "tijd": obj.tijd.strftime("%H:%M") if obj.tijd else "",
        "bijzonderheden": obj.bijzonderheden or "",
    }


@login_required
def reviewplanner(request):
    if not can(request.user, "can_view_reviewplanner"):
        return HttpResponseForbidden("Geen toegang.")

    can_edit = can(request.user, "can_edit_reviewplanner")

    today = timezone.localdate()
    cutoff = today - relativedelta(weeks=8)

    # Alleen tonen vanaf today-8 weken (en niet verder terug)
    rows = list(
        ReviewPlanner.objects.filter(datum__gte=cutoff)
        .order_by("datum", "-updated_at", "-id")
    )

    # select2 data
    afdelingen = list(
        MedicatieReviewAfdeling.objects.all()
        .order_by("organisatie__name", "afdeling", "locatie")
    )

    if request.method == "POST":
        if not can_edit:
            return JsonResponse({"ok": False, "error": "Geen rechten om te bewerken."}, status=403)

        action = request.POST.get("action", "autosave")

        # ------------------------------------------------------------
        # A) Modal upsert (nieuwe regel of update)
        # ------------------------------------------------------------
        if action == "modal_upsert":
            rid = (request.POST.get("id") or "").strip()
            datum_s = (request.POST.get("datum") or "").strip()
            afdeling_id = (request.POST.get("afdeling_id") or "").strip()
            status = (request.POST.get("status") or ReviewPlanner.STATUS_PREP).strip()
            arts = (request.POST.get("arts") or "").strip()
            tijd_s = (request.POST.get("tijd") or "").strip()
            bijz = (request.POST.get("bijzonderheden") or "").strip()

            # datum verplicht via modal (aangezien je “review toevoegen” doet)
            d = _parse_dmy(datum_s)
            if not d:
                return JsonResponse({"ok": False, "error": "Datum is verplicht (dd-mm-jjjj)."}, status=400)

            # GEEN verleden toegestaan
            if d < today:
                return JsonResponse({"ok": False, "error": "Datum mag niet in het verleden liggen."}, status=400)

            # extra: ook niet ouder dan cutoff (redundant als je geen verleden toestaat, maar expliciet)
            if d < cutoff:
                return JsonResponse({"ok": False, "error": "Datum mag niet verder dan 8 weken terug liggen."}, status=400)

            t = _parse_hhmm(tijd_s)
            if tijd_s and not t:
                return JsonResponse({"ok": False, "error": "Ongeldige tijd."}, status=400)

            afd = None
            if afdeling_id:
                try:
                    afd = MedicatieReviewAfdeling.objects.get(id=int(afdeling_id))
                except Exception:
                    return JsonResponse({"ok": False, "error": "Ongeldige afdeling."}, status=400)

            if status not in dict(ReviewPlanner.STATUS_CHOICES):
                return JsonResponse({"ok": False, "error": "Ongeldige status."}, status=400)

            with transaction.atomic():
                if rid:
                    obj = ReviewPlanner.objects.select_for_update().get(id=int(rid))
                else:
                    obj = ReviewPlanner(created_by=request.user)

                obj.datum = d
                obj.afdeling = afd
                obj.status = status
                obj.arts = arts
                obj.tijd = t
                obj.bijzonderheden = bijz
                obj.updated_by = request.user
                obj.save()

            return JsonResponse({"ok": True, "row": _serialize_row(obj)})

        # ------------------------------------------------------------
        # B) Autosave (AJAX) – bulk rows
        # ------------------------------------------------------------
        if action == "autosave":
            ids = request.POST.getlist("row_id")
            datums = request.POST.getlist("row_datum")
            afds = request.POST.getlist("row_afdeling")
            statuses = request.POST.getlist("row_status")
            arts_list = request.POST.getlist("row_arts")
            tijden = request.POST.getlist("row_tijd")
            bijz_list = request.POST.getlist("row_bijzonderheden")

            n = min(len(ids), len(datums), len(afds), len(statuses), len(arts_list), len(tijden), len(bijz_list))

            try:
                with transaction.atomic():
                    for i in range(n):
                        rid = (ids[i] or "").strip()
                        datum_s = (datums[i] or "").strip()
                        afd_s = (afds[i] or "").strip()
                        status = (statuses[i] or ReviewPlanner.STATUS_PREP).strip()
                        arts = (arts_list[i] or "").strip()
                        tijd_s = (tijden[i] or "").strip()
                        bijz = (bijz_list[i] or "").strip()

                        # “alles leeg” => delete (alleen als bestaand id)
                        all_empty = (not datum_s and not afd_s and not arts and not tijd_s and not bijz)
                        if rid and all_empty:
                            ReviewPlanner.objects.filter(id=int(rid)).delete()
                            continue
                        if (not rid) and all_empty:
                            continue

                        d = _parse_dmy(datum_s)
                        if datum_s and not d:
                            return JsonResponse({"ok": False, "error": "Ongeldige datum."}, status=400)

                        # als er datum is ingevuld: geen verleden
                        if d and d < today:
                            return JsonResponse({"ok": False, "error": "Datum mag niet in het verleden liggen."}, status=400)

                        # en niet verder dan 8 weken terug (redundant bij 'geen verleden', maar blijft expliciet)
                        if d and d < cutoff:
                            return JsonResponse({"ok": False, "error": "Datum mag niet verder dan 8 weken terug liggen."}, status=400)

                        t = _parse_hhmm(tijd_s)
                        if tijd_s and not t:
                            return JsonResponse({"ok": False, "error": "Ongeldige tijd."}, status=400)

                        afd = None
                        if afd_s:
                            try:
                                afd = MedicatieReviewAfdeling.objects.get(id=int(afd_s))
                            except Exception:
                                return JsonResponse({"ok": False, "error": "Ongeldige afdeling."}, status=400)

                        if status not in dict(ReviewPlanner.STATUS_CHOICES):
                            return JsonResponse({"ok": False, "error": "Ongeldige status."}, status=400)

                        if rid:
                            obj = ReviewPlanner.objects.select_for_update().get(id=int(rid))
                        else:
                            obj = ReviewPlanner(created_by=request.user)

                        obj.datum = d
                        obj.afdeling = afd
                        obj.status = status
                        obj.arts = arts
                        obj.tijd = t
                        obj.bijzonderheden = bijz
                        obj.updated_by = request.user
                        obj.save()

                return JsonResponse({"ok": True})
            except Exception:
                return JsonResponse({"ok": False, "error": "Opslaan mislukt."}, status=400)

        return redirect("reviewplanner")

    context = {
        "rows": rows,
        "afdelingen": afdelingen,
        "can_edit": can_edit,
        "status_choices": ReviewPlanner.STATUS_CHOICES,
        "cutoff_iso": cutoff.isoformat(),
        "today_iso": today.isoformat(),
    }
    return render(request, "reviewplanner/index.html", context)
