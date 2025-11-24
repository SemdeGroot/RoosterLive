import json

from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles.storage import staticfiles_storage


class Command(BaseCommand):
    help = "Verwijdert S3 static files die niet meer in het staticfiles manifest staan."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Toon alleen welke bestanden verwijderd zouden worden, zonder echt te verwijderen.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        storage = staticfiles_storage
        backend = f"{storage.__class__.__module__}.{storage.__class__.__name__}"

        # Veiligheidscheck: alleen draaien als we echt de S3 static storage gebruiken
        if "S3Boto3Storage" not in backend:
            raise CommandError(
                f"staticfiles_storage is geen S3-storage ({backend}). "
                "Draai clean_static_s3 alleen in PROD met S3 static storage."
            )

        # Manifest inladen uit S3
        try:
            with storage.open("staticfiles.json") as f:
                manifest = json.load(f)
        except Exception as e:
            raise CommandError(f"Kan 'staticfiles.json' niet lezen uit S3: {e}")

        if not isinstance(manifest, dict):
            raise CommandError("Manifest heeft geen dictionary-structuur, onverwacht formaat.")

        # Geldige namen: originele + gehashte namen + staticfiles.json zelf
        valid_names = set(manifest.keys()) | set(manifest.values())
        valid_names.add("staticfiles.json")

        bucket = storage.bucket
        location = (storage.location or "").strip("/")
        prefix = f"{location}/" if location else ""

        self.stdout.write(
            f"Gebruik backend: {backend}\n"
            f"Bucket: {bucket.name}\n"
            f"Prefix: '{prefix}'\n"
            f"Aantal geldige manifest entries: {len(valid_names)}"
        )

        deleted = 0
        kept = 0
        skipped = 0

        for obj in bucket.objects.filter(Prefix=prefix):
            key = obj.key  # bv. 'static/js/auth/login.dbd9....js'
            # Strip de 'static/' prefix zodat je 'js/auth/...' overhoudt
            rel_name = key[len(prefix):] if key.startswith(prefix) else key

            # 'mappen' in S3 zijn gewoon keys die op / eindigen; die slaan we veilig over
            if rel_name.endswith("/"):
                skipped += 1
                continue

            if rel_name in valid_names:
                kept += 1
                continue

            if dry_run:
                self.stdout.write(f"[DRY-RUN] Zou verwijderen: {bucket.name}/{key}")
            else:
                obj.delete()
                self.stdout.write(f"Verwijderd: {bucket.name}/{key}")
            deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Klaar. Bewaard: {kept}, overgeslagen: {skipped}, verwijderd: {deleted} objecten in {bucket.name}/{prefix}"
            )
        )