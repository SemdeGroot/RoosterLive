import uuid
from django.db import migrations

BATCH_SIZE = 1000

def forwards(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")

    qs = UserProfile.objects.filter(calendar_token__isnull=True).only("id")
    total = qs.count()
    if total == 0:
        return

    # batch-wise updaten (efficiënt voor prod)
    buf = []
    seen = set()  # voorkomt duplicates binnen deze migratie-run (extra safety)

    for prof in qs.iterator(chunk_size=BATCH_SIZE):
        token = uuid.uuid4()
        while token in seen:
            token = uuid.uuid4()
        seen.add(token)

        prof.calendar_token = token
        buf.append(prof)

        if len(buf) >= BATCH_SIZE:
            UserProfile.objects.bulk_update(buf, ["calendar_token"], batch_size=BATCH_SIZE)
            buf = []

    if buf:
        UserProfile.objects.bulk_update(buf, ["calendar_token"], batch_size=BATCH_SIZE)

def backwards(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")
    UserProfile.objects.update(calendar_token=None)

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0060_userprofile_calendar_token"),  # laat Django dit invullen, niet zelf gokken
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]