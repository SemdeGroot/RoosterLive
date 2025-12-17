# core/tasks.py
from celery import shared_task

# === EMAILS ===
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3, rate_limit='10/s')
def send_invite_email_task(self, user_id: int):
    from django.contrib.auth import get_user_model
    from core.utils.invite import send_invite_email
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    send_invite_email(user)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3, rate_limit='10/s')
def send_password_reset_email_task(self, user_id: int):
    from django.contrib.auth import get_user_model
    from core.utils.reset import send_password_reset_email
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    send_password_reset_email(user)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3, rate_limit='10/s')
def send_nazendingen_pdf_task(self, organization_ids):
    # --- IMPORTS ---
    import os
    from django.conf import settings
    from django.utils import timezone
    from django.template.loader import render_to_string
    
    from core.models import Nazending, Organization
    from core.views._helpers import _static_abs_path, _render_pdf
    from core.utils.nazending_mail import send_single_nazending_email

    # 1. Instellingen & Data
    contact_email = "baxter@apotheekjansen.com"
    nazendingen = Nazending.objects.select_related('voorraad_item').order_by('-datum')
    
    # 2. Context
    context = {
        "nazendingen": nazendingen,
        "generated_at": timezone.localtime(timezone.now()),
        "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
        "signature_path": _static_abs_path("img/handtekening_apotheker.png"),
        "contact_email": contact_email,
    }

    # 3. HTML & PDF Generatie
    html = render_to_string("nazendingen/pdf/nazendingen_lijst.html", context)

    # Bepaal base_url voor plaatjes in PDF
    base_url = getattr(settings, "SITE_DOMAIN", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    
    pdf_content = _render_pdf(html, base_url=base_url)
    
    filename = f"Nazendingen_ApoJansen_{timezone.now().strftime('%d-%m-%Y')}.pdf"
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    # 4. Ontvangers
    orgs = Organization.objects.filter(id__in=organization_ids)

    # 5. Versturen met Fallback (zonder logging)
    for org in orgs:
        # Bepaal het hoofdadres (email1, of als die leeg is, email2)
        primary_email = org.email if org.email else org.email2
        
        # Als er helemaal geen adres is, sla over
        if not primary_email:
            continue

        try:
            # POGING 1: Stuur naar hoofdadres
            send_single_nazending_email(
                to_email=primary_email,
                name=org.name,
                pdf_content=pdf_content,
                filename=filename,
                logo_path=logo_path,
                contact_email=contact_email
            )
            
        except Exception:
            # POGING 2: Als Poging 1 technisch faalt (SMTP error), probeer email2
            # Alleen als email2 bestaat EN anders is dan email1
            if org.email2 and org.email2 != primary_email:
                try:
                    send_single_nazending_email(
                        to_email=org.email2,
                        name=org.name,
                        pdf_content=pdf_content,
                        filename=filename,
                        logo_path=logo_path,
                        contact_email=contact_email
                    )
                except Exception:
                    # Als ook email 2 faalt, doen we niets (pass) en gaan we door
                    pass

# === PUSH MELDINGEN ===

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_roster_updated_push_task(self, iso_year: int, iso_week: int,
                                  monday_str: str, friday_str: str):
    from core.utils.push import send_roster_updated_push
    send_roster_updated_push(iso_year, iso_week, monday_str, friday_str)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_news_uploaded_push_task(self, uploader_first_name):
    from core.utils.push import send_news_upload_push
    send_news_upload_push(uploader_first_name)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_agenda_uploaded_push_task(self, category):
    from core.utils.push import send_agenda_upload_push
    send_agenda_upload_push(category)