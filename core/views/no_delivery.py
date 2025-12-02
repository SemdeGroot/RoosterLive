from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.views._helpers import can

@login_required
def no_delivery(request):
    if not can(request.user, "can_view_baxter_no_delivery"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "no_delivery/index.html", {
        "page_title": "Geen levering",
    })
