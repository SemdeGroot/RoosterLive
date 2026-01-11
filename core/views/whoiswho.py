# core/views/whoiswho.py
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from core.models import UserProfile
from core.views._helpers import can

@login_required
def whoiswho(request):
    if not can(request.user, "can_view_whoiswho"):
        return HttpResponseForbidden("Geen toegang.")

    # Filter op actieve gebruikers van Apotheek Jansen (ID 1)
    profiles = UserProfile.objects.filter(
        user__is_active=True,
        organization_id=1
    ).select_related('user', 'function').order_by(
        'function__ranking',     # 1. Eerst op ranking
        'function__title',       # 2. Dan alfabetisch op functie titel
        'user__first_name',      # 3. voornaam
        'user__last_name'        # 4. Achternaam
    )

    return render(request, "whoiswho/index.html", {
        "profiles": profiles,
        "can_edit": can(request.user, "can_edit_whoiswho"),
    })