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
            ("can_view_agenda",           "Mag agenda bekijken"),
            ("can_upload_agenda",         "Mag agenda uploaden"),
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
            ("can_view_beschikbaarheidsdashboard", "Mag Beschikbaarheid Personeel bekijken"),
            ("can_view_medicatiebeoordeling",           "Mag Medicatiebeoordeling bekijken"),
            ("can_perform_medicatiebeoordeling",         "Mag Medicatiebeoordeling uitvoeren"),
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
    device_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} – {self.endpoint[:40]}…"

class WebAuthnPasskey(models.Model):
    """
    Eén WebAuthn/passkey credential per gebruiker per device.
    credential_id en public_key komen direct uit webauthn.verify_*_response().
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkeys",
    )
    # Base64url string van credential_id (zoals webauthn teruggeeft)
    credential_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Ruwe public key bytes zoals webauthn ze teruggeeft
    public_key = models.BinaryField()

    # Sign count (wordt bij elke succesvolle auth geüpdatet en gecontroleerd)
    sign_count = models.BigIntegerField(default=0)

    # Optioneel: user handle (zoals door client teruggestuurd)
    user_handle = models.CharField(max_length=255, blank=True)

    # Optioneel: transports / backup info, enkel voor debugging/UX
    transports = models.JSONField(default=list, blank=True)
    backed_up = models.BooleanField(default=False)

    # Per-device koppeling: zelfde concept als je WebPush device_hash
    device_hash = models.CharField(max_length=64, blank=True, db_index=True)

    nickname = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bijvoorbeeld 'iPhone van Sem' of 'Werktelefoon'.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Passkey"
        verbose_name_plural = "Passkeys"

    def __str__(self):
        base = self.nickname or f"Passkey {self.pk}"
        return f"{base} – {self.user}"

# 2FA subscriptions verwijderen uit db om te testen:
# python manage.py shell
# from django.contrib.auth.models import User
# from django_otp.plugins.otp_totp.models import TOTPDevice
# user = User.objects.get(username="sem")
# TOTPDevice.objects.filter(user=user).delete()