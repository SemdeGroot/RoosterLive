# core/tasks.py
from celery import shared_task
from django.core.management import call_command

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_invite_email_task(self, user_id: int):
    from django.contrib.auth import get_user_model
    from core.utils.invite import send_invite_email
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    send_invite_email(user)  # jouw bestaande functie

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_roster_updated_push_task(self):
    from core.utils.push import send_roster_updated_push
    send_roster_updated_push()
