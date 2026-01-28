# core/tasks/emails.py
from celery import shared_task, chord, group
from core.tasks.email_dispatcher import email_dispatcher_task

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_invite_email_task(self, user_id: int):
    email_dispatcher_task.apply_async(
        args=[{"type": "invite", "payload": {"user_id": user_id}}],
        queue="mail",
    )

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_password_reset_email_task(self, user_id: int):
    email_dispatcher_task.apply_async(
        args=[{"type": "password_reset", "payload": {"user_id": user_id}}],
        queue="mail",
    )

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_nazendingen_pdf_task(self, organization_ids):
    import os
    from django.conf import settings
    from django.utils import timezone
    from django.template.loader import render_to_string
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from celery import chord, group

    from core.models import Nazending, Organization
    from core.views._helpers import _static_abs_path, _render_pdf
    from core.tasks.email_dispatcher import email_dispatcher_task, cleanup_storage_file_task

    contact_email = "baxterezorg@apotheekjansen.com"
    nazendingen = (
        Nazending.objects
        .select_related("voorraad_item")
        .order_by("voorraad_item__naam", "voorraad_item__zi_nummer")
    )

    context = {
        "nazendingen": nazendingen,
        "generated_at": timezone.localtime(timezone.now()),
        "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
        "signature_path": _static_abs_path("img/handtekening_apotheker.png"),
        "contact_email": contact_email,
    }

    html = render_to_string("nazendingen/pdf/nazendingen_lijst.html", context)

    base_url = getattr(settings, "SITE_DOMAIN", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    pdf_bytes = _render_pdf(html, base_url=base_url)

    filename = f"Nazendingen_ApoJansen_{timezone.now().strftime('%d-%m-%Y')}.pdf"
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"tmp/nazendingen/{ts}_{filename}"
    pdf_path = default_storage.save(pdf_path, ContentFile(pdf_bytes))

    orgs = Organization.objects.filter(id__in=organization_ids)

    mail_sigs = []
    for org in orgs:
        primary = org.email or org.email2
        if not primary:
            continue

        sig = email_dispatcher_task.s({
            "type": "nazending_single",
            "payload": {
                "to_email": primary,
                "fallback_email": org.email2 if org.email2 and org.email2 != primary else None,
                "name": org.name,
                "pdf_path": pdf_path,
                "filename": filename,
                "logo_path": logo_path,
                "contact_email": contact_email,
            }
        }).set(queue="mail")

        mail_sigs.append(sig)

    if not mail_sigs:
        cleanup_storage_file_task.apply_async(args=[[], pdf_path], queue="default")
        return

    chord(group(mail_sigs))(cleanup_storage_file_task.s(pdf_path).set(queue="default"))

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_laatste_pot_email_task(self, item_naam: str):
    from django.contrib.auth import get_user_model
    from core.views._helpers import can

    User = get_user_model()
    users = User.objects.filter(is_active=True)
    recipients = [u for u in users if can(u, "can_perform_bestellingen")]

    for user in recipients:
        if not user.email:
            continue

        email_dispatcher_task.apply_async(
            args=[{
                "type": "laatste_pot",
                "payload": {
                    "to_email": user.email,
                    "first_name": user.first_name or "Collega",
                    "item_naam": item_naam,
                }
            }],
            queue="mail",
        )
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def cleanup_storage_files_task(self, results, paths):
    """
    Cleanup voor meerdere files (chord callback).
    Celery chord geeft altijd eerst 'results' mee.
    """
    from django.core.files.storage import default_storage

    for p in paths or []:
        try:
            if default_storage.exists(p):
                default_storage.delete(p)
        except Exception:
            pass


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_stshalfjes_pdf_task(self, organization_ids):
    import os
    from django.conf import settings
    from django.utils import timezone
    from django.template.loader import render_to_string
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from core.models import STSHalfje, Organization
    from core.views._helpers import _static_abs_path, _render_pdf

    from core.tasks.email_dispatcher import email_dispatcher_task

    contact_email = "baxterezorg@apotheekjansen.com"

    orgs = Organization.objects.filter(id__in=organization_ids)

    base_url = getattr(settings, "SITE_DOMAIN", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    today_str = timezone.now().strftime("%d-%m-%Y")

    # Inline logo voor mail (filesystem pad)
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    mail_sigs = []
    tmp_paths = []

    for org in orgs:
        primary = org.email or org.email2
        if not primary:
            continue

        qs = (
            STSHalfje.objects
            .select_related("item_gehalveerd", "item_alternatief", "apotheek")
            .filter(apotheek=org)
            .order_by("-created_at")
        )

        # Voorkom extra .exists() query: maak 1x list
        items = list(qs)
        if not items:
            continue
        item_ids = [i.id for i in items]

        context = {
            "items": items,
            "apotheek": org,
            "generated_at": timezone.localtime(timezone.now()),
            "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
            "signature_path": _static_abs_path("img/handtekening_apotheker.png"),
            "contact_email": contact_email,
        }

        html = render_to_string(
            "stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html",
            context,
        )

        pdf_bytes = _render_pdf(html, base_url=base_url)

        # Veilige filename (org.name kan rare chars bevatten)
        safe_name = "".join(c if c.isalnum() or c in " _-" else "-" for c in (org.name or "apotheek"))
        filename = f"Onnodig_gehalveerde_geneesmiddelen_{safe_name}_{today_str}.pdf"

        pdf_path = f"tmp/stshalfjes/{ts}_{org.id}_{filename}"
        pdf_path = default_storage.save(pdf_path, ContentFile(pdf_bytes))
        tmp_paths.append(pdf_path)

        sig = email_dispatcher_task.s({
            "type": "stshalfjes_single",
            "payload": {
                "to_email": primary,
                "fallback_email": org.email2 if org.email2 and org.email2 != primary else None,
                "name": org.name,
                "pdf_path": pdf_path,
                "filename": filename,
                "logo_path": logo_path,
                "contact_email": contact_email,
                "item_ids": item_ids,
            }
        }).set(queue="mail")

        mail_sigs.append(sig)

    # Niks te mailen? cleanup meteen
    if not mail_sigs:
        cleanup_storage_files_task.apply_async(args=[[], tmp_paths], queue="default")
        return

    # Na alle mails -> cleanup alle pdf files
    chord(group(mail_sigs))(
        cleanup_storage_files_task.s(paths=tmp_paths).set(queue="default")
    )

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_no_delivery_pdf_task(self, no_delivery_list_ids):
    import os
    from django.conf import settings
    from django.utils import timezone
    from django.template.loader import render_to_string
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from core.models import NoDeliveryList
    from core.views._helpers import _static_abs_path, _render_pdf
    from core.tasks.email_dispatcher import email_dispatcher_task

    contact_email = "baxterezorg@apotheekjansen.com"

    base_url = getattr(settings, "SITE_DOMAIN", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    today_str = timezone.now().strftime("%d-%m-%Y")

    # Inline logo voor mail (filesystem pad)
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    lists = (
        NoDeliveryList.objects
        .select_related("apotheek")
        .prefetch_related("entries", "entries__gevraagd_geneesmiddel")
        .filter(id__in=no_delivery_list_ids)
        .order_by("-updated_at", "-created_at")
    )

    mail_sigs = []
    tmp_paths = []

    for lst in lists:
        org = lst.apotheek
        if not org:
            continue

        primary = org.email or org.email2
        if not primary:
            continue

        entries = list(lst.entries.all())
        if not entries:
                continue

        # Bepaal datum van deze lijst (op basis van jaar/week/dag)
        from datetime import date

        def _iso_weekday_from_dag(dag_code: str) -> int:
            mapping = {"MA": 1, "DI": 2, "WO": 3, "DO": 4, "VR": 5, "ZA": 6}
            return mapping.get((dag_code or "").upper(), 1)

        def _date_from_year_week_dag(jaar: int, week: int, dag_code: str) -> date:
            return date.fromisocalendar(int(jaar), int(week), _iso_weekday_from_dag(dag_code))

        try:
            dag_datum = _date_from_year_week_dag(lst.jaar, lst.week, lst.dag)
        except Exception:
            dag_datum = None

        context = {
            "selected_list": lst,
            "entries": entries,
            "generated_at": timezone.localtime(timezone.now()),
            "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
            "signature_path": _static_abs_path("img/handtekening_apotheker.png"),
            "contact_email": contact_email,
            "dag_datum": dag_datum,
        }

        html = render_to_string("no_delivery/pdf/no_delivery_export.html", context)


        pdf_bytes = _render_pdf(html, base_url=base_url)

        safe_name = "".join(c if c.isalnum() or c in " _-" else "-" for c in (org.name or "apotheek"))
        dag_label = lst.get_dag_display()
        filename = f"Niet-leverlijst_{safe_name}_Week{lst.week}_{dag_label}_{today_str}.pdf"

        pdf_path = f"tmp/no_delivery/{ts}_{lst.id}_{filename}"
        pdf_path = default_storage.save(pdf_path, ContentFile(pdf_bytes))
        tmp_paths.append(pdf_path)

        sig = email_dispatcher_task.s({
            "type": "no_delivery_single",
            "payload": {
                "to_email": primary,
                "fallback_email": org.email2 if org.email2 and org.email2 != primary else None,
                "name": org.name,
                "pdf_path": pdf_path,
                "filename": filename,
                "logo_path": logo_path,
                "contact_email": contact_email,
                "week": int(lst.week),
                "dag_label": dag_label,
            }
        }).set(queue="mail")

        mail_sigs.append(sig)

    if not mail_sigs:
        cleanup_storage_files_task.apply_async(args=[[], tmp_paths], queue="default")
        return

    chord(group(mail_sigs))(
        cleanup_storage_files_task.s(paths=tmp_paths).set(queue="default")
    )

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_omzettingslijst_pdf_task(self, omzettingslijst_ids):
    import os
    from django.conf import settings
    from django.utils import timezone
    from django.template.loader import render_to_string
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from core.models import Omzettingslijst
    from core.views._helpers import _static_abs_path, _render_pdf
    from core.tasks.email_dispatcher import email_dispatcher_task
    from core.tasks import cleanup_storage_files_task  # als die in dezelfde module staat

    contact_email = "baxterezorg@apotheekjansen.com"

    base_url = getattr(settings, "SITE_DOMAIN", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    today_str = timezone.now().strftime("%d-%m-%Y")

    # Inline logo voor mail (filesystem pad)
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    lists = (
        Omzettingslijst.objects
        .select_related("apotheek")
        .prefetch_related(
            "entries",
            "entries__gevraagd_geneesmiddel",
            "entries__geleverd_geneesmiddel",
        )
        .filter(id__in=omzettingslijst_ids)
        .order_by("-updated_at", "-created_at")
    )

    mail_sigs = []
    tmp_paths = []

    from datetime import date

    def _iso_weekday_from_dag(dag_code: str) -> int:
        mapping = {"MA": 1, "DI": 2, "WO": 3, "DO": 4, "VR": 5, "ZA": 6}
        return mapping.get((dag_code or "").upper(), 1)

    def _date_from_year_week_dag(jaar: int, week: int, dag_code: str) -> date:
        return date.fromisocalendar(int(jaar), int(week), _iso_weekday_from_dag(dag_code))

    for lst in lists:
        org = lst.apotheek
        if not org:
            continue

        primary = org.email or org.email2
        if not primary:
            continue

        entries = list(lst.entries.all())
        if not entries:
            continue

        try:
            dag_datum = _date_from_year_week_dag(lst.jaar, lst.week, lst.dag)
        except Exception:
            dag_datum = None

        context = {
            "selected_list": lst,
            "entries": entries,
            "generated_at": timezone.localtime(timezone.now()),
            "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
            "signature_path": _static_abs_path("img/handtekening_apotheker.png"),
            "contact_email": contact_email,
            "dag_datum": dag_datum,
        }

        html = render_to_string("omzettingslijst/pdf/omzettingslijst_export.html", context)
        pdf_bytes = _render_pdf(html, base_url=base_url)

        safe_name = "".join(c if c.isalnum() or c in " _-" else "-" for c in (org.name or "apotheek"))
        dag_label = lst.get_dag_display()
        filename = f"Omzettingslijst_{safe_name}_Week{lst.week}_{dag_label}_{today_str}.pdf"

        pdf_path = f"tmp/omzettingslijst/{ts}_{lst.id}_{filename}"
        pdf_path = default_storage.save(pdf_path, ContentFile(pdf_bytes))
        tmp_paths.append(pdf_path)

        sig = email_dispatcher_task.s({
            "type": "omzettingslijst_single",
            "payload": {
                "to_email": primary,
                "fallback_email": org.email2 if org.email2 and org.email2 != primary else None,
                "name": org.name,
                "pdf_path": pdf_path,
                "filename": filename,
                "logo_path": logo_path,
                "contact_email": contact_email,
                "week": int(lst.week),
                "dag_label": dag_label,
            }
        }).set(queue="mail")

        mail_sigs.append(sig)

    if not mail_sigs:
        cleanup_storage_files_task.apply_async(args=[[], tmp_paths], queue="default")
        return

    chord(group(mail_sigs))(
        cleanup_storage_files_task.s(paths=tmp_paths).set(queue="default")
    )
