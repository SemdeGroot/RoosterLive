# core/decorators.py
from functools import wraps
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse

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