from django.db import models
from django.contrib.auth.models import User

class Roster(models.Model):
    title = models.CharField(max_length=200, default="Rooster")
    pdf = models.FileField(upload_to="rosters/")
    created_at = models.DateTimeField(auto_now_add=True)
    hash16 = models.CharField(max_length=16, blank=True)
    page_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.title} ({self.created_at:%Y-%m-%d %H:%M})"
    
    class Meta:
        permissions = [
            ("can_access_admin",          "Mag beheer openen"),
            ("can_upload_roster",         "Mag roosters uploaden"),
            ("can_manage_users",          "Mag gebruikers beheren"),
            ("can_view_roster",           "Mag rooster bekijken"),

            ("can_access_availability",   "Mag Beschikbaarheid openen"),        
            ("can_view_av_medications",   "Mag subtab Geneesmiddelen zien"),
            ("can_view_av_nazendingen",   "Mag subtab Nazendingen zien"),         
        ]
