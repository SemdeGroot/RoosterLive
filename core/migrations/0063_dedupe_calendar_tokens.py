import uuid
from django.db import migrations
from django.db.models import Count


BATCH_SIZE = 1000


def forwards(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")

    # Safety: als er toch nog NULL's zijn, vul ze ook
    for prof in UserProfile.objects.filter(calendar_token__isnull=True).only("id").iterator(chunk_size=BATCH_SIZE):
        prof.calendar_token = uuid.uuid4()
        prof.save(update_fields=["calendar_token"])

    # Zoek tokens die meerdere keren voorkomen
    dup_tokens = (
        UserProfile.objects
        .values("calendar_token")
        .annotate(c=Count("id"))
        .filter(c__gt=1, calendar_token__isnull=False)
    )

    for row in dup_tokens.iterator(chunk_size=BATCH_SIZE):
        token = row["calendar_token"]

        # Pak alle profielen met dit token (op id volgorde)
        ids = list(
            UserProfile.objects
            .filter(calendar_token=token)
            .order_by("id")
            .values_list("id", flat=True)
        )

        # Eerste houden, rest nieuw token geven
        for prof_id in ids[1:]:
            new_token = uuid.uuid4()
            # extra safety: zorg dat het echt uniek is in DB
            while UserProfile.objects.filter(calendar_token=new_token).exists():
                new_token = uuid.uuid4()

            UserProfile.objects.filter(id=prof_id).update(calendar_token=new_token)


def backwards(apps, schema_editor):
    # Niet nodig om terug te draaien
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_fill_calendar_tokens"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]