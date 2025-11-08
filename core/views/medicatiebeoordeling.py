# core/views/medicatiebeoordeling.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from ._helpers import can


@login_required
def medicatiebeoordeling(request):
    """
    Placeholder view voor medicatiebeoordeling.
    Later kun je hier logica toevoegen (upload, tabellen, etc.).
    """
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen toegang tot medicatiebeoordeling.")

    context = {
        "title": "Medicatiebeoordeling",
    }
    return render(request, "medicatiebeoordeling/index.html", context)
