from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.views._helpers import can

@login_required
def sts_halfjes(request):
    if not can(request.user, "can_view_baxter_sts_halfjes"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "sts_halfjes/index.html", {
        "page_title": "STS halfjes",
    })