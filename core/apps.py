from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # registreer signals uit de permissions-package
        from .permissions import signals  # noqa: F401