# core/storage.py
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
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
    default_acl = "public-read"
    file_overwrite = True


class MediaRootS3Boto3Storage(S3Boto3Storage):
    """S3 storage onder de 'media/' prefix in de bucket."""
    location = "media"
    default_acl = "public-read"
    file_overwrite = False


class PartialManifestStaticFilesS3Storage(PartialManifestStaticFilesStorage, StaticRootS3Boto3Storage):
    """
    Combineert partial-manifest hashing met S3 storage.
    In DEBUG de lokale PartialManifestStaticFilesStorage,
    in PROD deze S3-variant.
    """
    pass
