import os
from celery import Celery
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rooster_site.settings")

app = Celery("rooster_site")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # vindt tasks.py in je apps

# Minder geheugen / writes:
app.conf.task_ignore_result = True            # geen results opslaan
app.conf.result_expires = timedelta(minutes=30)
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True