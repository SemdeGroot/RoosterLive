from django.db import models

class Roster(models.Model):
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to="rooster/", blank=True, null=True)  # we schrijven zelf naar rooster/rooster.pdf

    class Meta:
        permissions = [
            ("can_access_admin",          "Mag beheer openen"),
            ("can_manage_users",          "Mag gebruikers beheren"),
            ("can_view_roster",           "Mag rooster bekijken"),
            ("can_upload_roster",         "Mag roosters uploaden"),
            ("can_access_availability",   "Mag Beschikbaarheid openen"),
            ("can_view_av_medications",   "Mag subtab Geneesmiddelen zien"),
            ("can_view_av_nazendingen",   "Mag subtab Nazendingen zien"),
            ("can_view_news",             "Mag Nieuws bekijken"),
            ("can_view_policies",         "Mag Werkafspraken bekijken"),
        ]
