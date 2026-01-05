from celery import shared_task
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
    nazendingen = Nazending.objects.select_related('voorraad_item').order_by('-datum')

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