from celery import shared_task

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_roster_updated_push_task(self, iso_year: int, iso_week: int, monday_str: str, friday_str: str):
    from core.utils.push.push import send_roster_updated_push
    send_roster_updated_push(iso_year, iso_week, monday_str, friday_str)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_news_uploaded_push_task(self, uploader_first_name):
    from core.utils.push.push import send_news_upload_push
    send_news_upload_push(uploader_first_name)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_agenda_uploaded_push_task(self, category):
    from core.utils.push.push import send_agenda_upload_push
    send_agenda_upload_push(category)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_laatste_pot_push_task(self, item_naam):
    from core.utils.push.push import send_laatste_pot_push
    send_laatste_pot_push(item_naam)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_user_shifts_changed_push_task(
    self,
    user_id: int,
    iso_year: int,
    iso_week: int,
    monday_str: str,
    added_count: int,
    changed_count: int,
    removed_count: int,
):
    from core.utils.push.push import send_user_shifts_changed_push
    send_user_shifts_changed_push(
        user_id=user_id,
        iso_year=iso_year,
        iso_week=iso_week,
        monday_str=monday_str,
        added_count=added_count,
        changed_count=changed_count,
        removed_count=removed_count,
    )