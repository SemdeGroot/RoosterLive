# core/views/home.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.tiles import build_tiles

@login_required
def home(request):
    tiles = build_tiles(request.user, group="home")
    return render(request, "home.html", {"tiles": tiles})