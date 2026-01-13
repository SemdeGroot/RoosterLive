# core/tasks_email.py
from celery import shared_task
from django.core.files.storage import default_storage

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3,
    rate_limit="10/s",
    acks_late=False,  # voorkomt dubbele mails door worker-crash na verzenden
)
def email_dispatcher_task(self, job: dict):
    """
    job = {"type": "...", "payload": {...}}
    1 task-call = 1 email (max 1 succesvolle verzending).
    """
    job_type = job["type"]
    p = job.get("payload", {})

    if job_type == "invite":
        from django.contrib.auth import get_user_model
        from core.utils.emails.invite import send_invite_email

        User = get_user_model()
        user = User.objects.get(pk=p["user_id"])
        send_invite_email(user)
        return

    if job_type == "password_reset":
        from django.contrib.auth import get_user_model
        from core.utils.emails.reset import send_password_reset_email

        User = get_user_model()
        user = User.objects.get(pk=p["user_id"])
        send_password_reset_email(user)
        return

    if job_type == "laatste_pot":
        from core.utils.emails.laatstepotten_mail import send_laatste_pot_email

        send_laatste_pot_email(
            to_email=p["to_email"],
            first_name=p.get("first_name", "Collega"),
            item_naam=p["item_naam"],
        )
        return

    if job_type == "nazending_single":
        from core.utils.emails.nazending_mail import send_single_nazending_email

        # PDF uit storage lezen (lokaal of S3)
        with default_storage.open(p["pdf_path"], "rb") as f:
            pdf_content = f.read()

        # fallback e-mailadres: probeer primary, anders email2
        try:
            send_single_nazending_email(
                to_email=p["to_email"],
                name=p["name"],
                pdf_content=pdf_content,
                filename=p["filename"],
                logo_path=p["logo_path"],
                contact_email=p["contact_email"],
            )
        except Exception:
            fallback = p.get("fallback_email")
            if fallback and fallback != p["to_email"]:
                send_single_nazending_email(
                    to_email=fallback,
                    name=p["name"],
                    pdf_content=pdf_content,
                    filename=p["filename"],
                    logo_path=p["logo_path"],
                    contact_email=p["contact_email"],
                )
            else:
                raise
        return
    
    if job_type == "uren_overzicht":
        from datetime import date
        from core.utils.emails.uren_overzicht import send_uren_overzicht_email

        # XLSX uit storage lezen (lokaal of S3)
        with default_storage.open(p["xlsx_path"], "rb") as f:
            xlsx_content = f.read()

        month_first = date.fromisoformat(p["month_first"])

        send_uren_overzicht_email(
            to_email=p["to_email"],
            month_first=month_first,
            xlsx_content=xlsx_content,
            filename=p["filename"],
            contact_email=p["contact_email"],
            logo_path=p.get("logo_path"),
        )
        return
    
    if job_type == "birthday":
        from core.utils.emails.birthday_email import send_birthday_email

        send_birthday_email(
            to_email=p["to_email"],
            first_name=p.get("first_name", "Collega"),
        )
        return
    
    if job_type == "stshalfjes_single":
        from core.utils.emails.stshalfjes_email import send_single_stshalfjes_email

        with default_storage.open(p["pdf_path"], "rb") as f:
            pdf_content = f.read()

        try:
            send_single_stshalfjes_email(
                to_email=p["to_email"],
                name=p["name"],
                pdf_content=pdf_content,
                filename=p["filename"],
                logo_path=p["logo_path"],
                contact_email=p["contact_email"],
            )
        except Exception:
            fallback = p.get("fallback_email")
            if fallback and fallback != p["to_email"]:
                send_single_stshalfjes_email(
                    to_email=fallback,
                    name=p["name"],
                    pdf_content=pdf_content,
                    filename=p["filename"],
                    logo_path=p["logo_path"],
                    contact_email=p["contact_email"],
                )
            else:
                raise
        return 

    raise ValueError(f"Unknown job type: {job_type}")

@shared_task(bind=True)
def cleanup_storage_file_task(self, results, path: str):
    """
    Celery chord geeft altijd eerst 'results' mee (list van header results).
    """
    try:
        if default_storage.exists(path):
            default_storage.delete(path)
    except Exception:
        pass