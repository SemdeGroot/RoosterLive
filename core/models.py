from django.db import models

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
        ]
    def __str__(self):
        return f"Rooster ({self.uploaded_at:%Y-%m-%d %H})"
