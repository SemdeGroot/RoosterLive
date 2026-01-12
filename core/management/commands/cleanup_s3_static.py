import json
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3

class Command(BaseCommand):
    help = 'Schoont S3 op op basis van het staticfiles manifest'

    def handle(self, *args, **options):
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(bucket_name)

        # 1. Haal het manifest op van S3
        manifest_key = 'static/staticfiles.json'
        try:
            obj = s3.Object(bucket_name, manifest_key)
            manifest_data = json.loads(obj.get()['Body'].read().decode('utf-8'))
        except Exception as e:
            self.stderr.write(f"Kon manifest niet laden: {e}")
            return

        # Haal de gehashte namen op uit het manifest
        active_files = set(manifest_data.get('paths', {}).values())
        
        # Voeg de originele namen ook toe (voor de zekerheid) en het manifest zelf
        active_files.update(manifest_data.get('paths', {}).keys())
        active_files.add('staticfiles.json')

        # 2. Definieer de prefixes die we NOOIT mogen verwijderen (uit jouw storage.py)
        # Alles in deze mappen wordt gespaard omdat ze niet in het manifest staan.
        excluded_prefixes = ("pwa/", "img/")

        self.stdout.write(f"Opschonen van bucket {bucket_name}...")

        delete_count = 0
        for obj in bucket.objects.filter(Prefix='static/'):
            # Maak het pad relatief aan de 'static/' map op S3
            relative_path = obj.key.replace('static/', '', 1)

            if not relative_path:
                continue

            # Check 1: Staat het in het manifest?
            if relative_path in active_files:
                continue

            # Check 2: Valt het onder de uitgesloten mappen (pwa/img)?
            if relative_path.startswith(excluded_prefixes):
                continue
            
            # Check 3: Is het geen 'map' (S3 keys die eindigen op /)
            if obj.key.endswith('/'):
                continue

            # Als we hier komen, is het een oud gehasht bestand of troep
            self.stdout.write(f"Verwijderen: {obj.key}")
            obj.delete()
            delete_count += 1

        self.stdout.write(self.style.SUCCESS(f"Succesvol {delete_count} oude bestanden verwijderd."))