# core/tasks.py
from celery import shared_task

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_invite_email_task(self, user_id: int):
    from django.contrib.auth import get_user_model
    from core.utils.invite import send_invite_email
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    send_invite_email(user)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_roster_updated_push_task(self, iso_year: int, iso_week: int,
                                  monday_str: str, friday_str: str):
    from core.utils.push import send_roster_updated_push
    send_roster_updated_push(iso_year, iso_week, monday_str, friday_str)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_password_reset_email_task(self, user_id: int):
    from django.contrib.auth import get_user_model
    from core.utils.reset import send_password_reset_email
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    send_password_reset_email(user)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_news_uploaded_push_task(self):
    from core.utils.push import send_news_upload_push
    send_news_upload_push()

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_agenda_uploaded_push_task(self, category):
    from core.utils.push import send_agenda_upload_push
    send_agenda_upload_push(category)