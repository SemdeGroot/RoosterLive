# core/storage.py
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage, ManifestFilesMixin
from storages.backends.s3boto3 import S3Boto3Storage


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


class StaticRootS3Boto3Storage(S3Boto3Storage):
    """S3 storage onder de 'static/' prefix in de bucket."""
    location = "static"
    default_acl = None          # BELANGRIJK i.v.m. Bucket owner enforced
    file_overwrite = True


class MediaRootS3Boto3Storage(S3Boto3Storage):
    """S3 storage onder de 'media/' prefix in de bucket."""
    location = "media"
    default_acl = None          # idem
    file_overwrite = False


class PartialManifestStaticFilesS3Storage(ManifestFilesMixin, StaticRootS3Boto3Storage):
    """
    Combineert ManifestFilesMixin (hashing) met S3 storage,
    plus jouw uitzondering voor bepaalde prefixes.
    """

    EXCLUDED_PREFIXES = ("pwa/", "img/")

    def hashed_name(self, name, content=None, filename=None):
        if name.startswith(self.EXCLUDED_PREFIXES):
            return name
        return super().hashed_name(name, content=content, filename=filename)