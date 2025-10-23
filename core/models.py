from django.db import models
from django.conf import settings

class Roster(models.Model):
    file = models.FileField(upload_to="rooster/current.pdf", null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Lijst met relatieve paden naar gerenderde PNG-pagina’s in MEDIA_ROOT
    pages = models.JSONField(default=list, blank=True)

    class Meta:
        permissions = [
            ("can_access_admin",          "Mag beheer openen"),
            ("can_manage_users",          "Mag gebruikers beheren"),
            ("can_view_roster",           "Mag rooster bekijken"),
            ("can_upload_roster",         "Mag roosters uploaden"),
            ("can_access_availability",   "Mag Beschikbaarheid openen"),
            ("can_view_av_medications",   "Mag subtab Geneesmiddelen zien"),
            ("can_upload_voorraad",       "Mag Voorraad uploaden"),   
            ("can_view_av_nazendingen",   "Mag subtab Nazendingen zien"),
            ("can_upload_nazendingen",    "Mag Nazendingen uploaden"), 
            ("can_view_news",             "Mag Nieuws bekijken"),
            ("can_upload_news",           "Mag Nieuws uploaden"),   
            ("can_view_policies",         "Mag Werkafspraken bekijken"),
            ("can_upload_werkafspraken",  "Mag Werkafspraken uploaden"),
            ("can_send_beschikbaarheid",  "Mag Beschikbaarheid doorgeven"),
            ("can_view_beschikbaarheidsdashboard", "Mag Beschikbaarheid Personeel bekijken")
        ]
    def __str__(self):
        return f"Rooster ({self.uploaded_at:%Y-%m-%d %H})"

class Availability(models.Model):
    """
    Bewaart beschikbaarheid per gebruiker per datum (ma-vr),
    met twee tijdvakken: ochtend/middag.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="availabilities")
    date = models.DateField(db_index=True)
    morning = models.BooleanField(default=False)
    afternoon = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.user} @ {self.date} (o:{self.morning} m:{self.afternoon})"

class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} – {self.endpoint[:40]}…"

class WebAuthnCredential(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webauthn_credentials')
    name = models.CharField(max_length=100, default='Mijn toestel')
    credential_id = models.CharField(max_length=255, unique=True)  # base64url string
    public_key = models.TextField()                                 # PEM/COSE as b64url (lib levert dit)
    sign_count = models.IntegerField(default=0)
    transports = models.CharField(max_length=200, blank=True)       # csv
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} – {self.name}"
    
    # Om te verwijderen voor debug:
    # python manage.py shell
    # from core.models import WebAuthnCredential
    # WebAuthnCredential.objects.filter(user__username="sem").delete()
    # exit()