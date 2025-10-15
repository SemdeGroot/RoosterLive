from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from ._helpers import can

@login_required
def mijnbeschikbaarheid_view(request):
    if not can(request.user, "can_send_beschikbaarheid"):
        return HttpResponseForbidden("Geen toegang.")
    return render(request, "mijnbeschikbaarheid/index.html")
