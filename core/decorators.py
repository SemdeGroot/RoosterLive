# core/decorators.py
from functools import wraps
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from django_otp.plugins.otp_totp.models import TOTPDevice

def require_totp(view_func):
    """
    Vereist TOTP, maar laat herhaalde acties toe binnen een korte 'grace window'
    nadat de gebruiker 1x succesvol heeft bevestigd.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Alleen afdwingen op POST (meestal jouw delete/update actions)
        if request.method != "POST":
            return view_func(request, *args, **kwargs)

        # 1) Grace window check (30s)
        until_iso = request.session.get("totp_verified_until")
        if until_iso:
            try:
                until = timezone.datetime.fromisoformat(until_iso)
                if timezone.is_naive(until):
                    until = timezone.make_aware(until, timezone.get_current_timezone())
                if timezone.now() < until:
                    return view_func(request, *args, **kwargs)
            except Exception:
                # als session value corrupt is: negeren en opnieuw vragen
                pass

        # 2) Normale TOTP check
        token = (request.POST.get("totp_token") or "").strip().replace(" ", "")
        if not (token.isdigit() and len(token) == 6):
            return _totp_fail(request, "Voer je 6-cijferige code in.")

        devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)
        if not devices.exists():
            return _totp_fail(request, "Je hebt geen 2FA ingesteld.")

        ok = any(d.verify_token(token) for d in devices)
        if not ok:
            return _totp_fail(request, "De code klopt niet.")

        # 3) Zet grace window na succesvolle verificatie
        request.session["totp_verified_until"] = (timezone.now() + timedelta(seconds=30)).isoformat()

        return view_func(request, *args, **kwargs)

    return _wrapped_view

def _totp_fail(request, message: str):
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if is_ajax:
        return JsonResponse({"ok": False, "error": message}, status=403)

    messages.error(request, message)
    return redirect(request.META.get("HTTP_REFERER") or "/")


def get_client_ip(request):
    """
    Haalt het IP-adres van de client op.
    Houdt rekening met X-Forwarded-For (voor als je achter Nginx/Load Balancer zit).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def ip_restricted(view_func):
    """
    Decorator die checkt of het IP van de gebruiker in de ALLOWED_MEDICATIE_IPS settings staat.
    Zo niet: toont een specifieke foutpagina of JSON error.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Haal de toegestane IP's op uit settings.py
        # Gebruik een lege lijst als fallback als de setting ontbreekt
        allowed_ips = getattr(settings, 'ALLOWED_PHARMACY_NETWORKS', [])
        
        user_ip = get_client_ip(request)

        # Voor debuggen lokaal (optioneel, haal weg in productie):
        # print(f"User IP: {user_ip} - Allowed: {allowed_ips}")

        if user_ip not in allowed_ips:
            # 1. Check of het een API/AJAX call is (geef JSON terug)
            if request.path.endswith('api') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {"error": "IP restrictie: Log in op een computer in de apotheek."}, 
                    status=403
                )
            
            # 2. Render de HTML pagina (Standalone, geen base inheritance nodig voor error pages)
            return render(request, "includes/ip_restricted.html", status=403)

        return view_func(request, *args, **kwargs)
    return _wrapped_view