# core/views/news.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from ._helpers import can, logo_url

@login_required
def news(request):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")
    return render(request, "news/index.html", {"logo_url": logo_url()})
