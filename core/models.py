from django.db import models

class Roster(models.Model):
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Dit veld hoeft niet gebruikt te worden, maar laat 'm optioneel ivm bestaande rows:
    file = models.FileField(upload_to="rooster/", blank=True, null=True)

    class Meta:
        permissions = [
            ("can_access_admin",          "Mag beheer openen"),
            ("can_manage_users",          "Mag gebruikers beheren"),
            ("can_view_roster",           "Mag rooster bekijken"),
            ("can_upload_roster",         "Mag roosters uploaden"),
            ("can_access_availability",   "Mag Beschikbaarheid openen"),
            ("can_view_av_medications",   "Mag subtab Geneesmiddelen zien"),
            ("can_view_av_nazendingen",   "Mag subtab Nazendingen zien"),
            ("can_view_news",             "Mag Nieuws bekijken"),          # <— NIEUW
            ("can_view_policies",         "Mag Werkafspraken bekijken"),   # <— NIEUW
        ]
