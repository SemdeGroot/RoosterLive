from django.db import models

class Roster(models.Model):
    file = models.FileField(upload_to="rooster/current.pdf")
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
            ("can_view_av_nazendingen",   "Mag subtab Nazendingen zien"),
            ("can_view_news",             "Mag Nieuws bekijken"),          # <— NIEUW
            ("can_view_policies",         "Mag Werkafspraken bekijken"),   # <— NIEUW
        ]
    def __str__(self):
        return f"Rooster ({self.uploaded_at:%Y-%m-%d %H})"
