# core/utils/network.py
import ipaddress
from django.conf import settings

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_in_pharmacy_network(request):
    """
    Controleert of het IP van de gebruiker binnen het geconfigureerde 
    subnet of de lijst met specifieke IP's valt.
    """
    user_ip_str = get_client_ip(request)
    
    # Haal configuratie uit settings.py
    # Bijv: ALLOWED_PHARMACY_NETWORKS = ["127.19.125.0/24", "192.168.10.5"]
    allowed_networks = getattr(settings, 'ALLOWED_PHARMACY_NETWORKS', [])
    
    if not user_ip_str:
        return False

    try:
        user_ip = ipaddress.ip_address(user_ip_str)
        for network_str in allowed_networks:
            # ip_network kan overweg met zowel subnetten ("192.168.1.0/24") 
            # als losse IP's ("127.19.125.52")
            network = ipaddress.ip_network(network_str, strict=False)
            if user_ip in network:
                return True
    except ValueError:
        return False
    
    return False