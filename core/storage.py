# core/storage.py
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

class PartialManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """
    ManifestStaticFilesStorage, maar zonder hashing voor bepaalde paden.
    Bijvoorbeeld voor PWA icons en screenshots in 'pwa/' en 'img/'.
    """

    EXCLUDED_PREFIXES = ("pwa/", "img/")

    def hashed_name(self, name, content=None, filename=None):
        # name is een pad relatief aan STATIC_ROOT, bv 'img/logo.png'
        if name.startswith(self.EXCLUDED_PREFIXES):
            # Geen hash toepassen, gewoon de originele naam gebruiken
            return name
        return super().hashed_name(name, content=content, filename=filename)
