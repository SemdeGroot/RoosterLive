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
