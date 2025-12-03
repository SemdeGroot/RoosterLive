from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.views._helpers import can

@login_required
def portavita_check(request):
    if not can(request.user, "can_view_portavita"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "portavita/index.html", {
        "page_title": "Portavita Check",
    })
