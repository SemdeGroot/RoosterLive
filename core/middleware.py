# core/middleware_enforce_2fa.py
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.deprecation import MiddlewareMixin
from two_factor.utils import default_device

# View-namen uit je eigen app die zonder 2FA bereikbaar moeten zijn
SAFE_URLNAMES = {
    "login",        # jouw redirect-view naar two_factor:login
    "logout",       # jouw logout POST
    "set_password", # eenmalige wachtwoord-zet pagina
    "passkey_setup",
}

SAFE_PATH_PREFIXES = (
    "/static/", "/media/", "/favicon.ico",
    "/service-worker.js", "/__reload__/",
)

class Enforce2FAMiddleware(MiddlewareMixin):
    """
    Dwingt 2FA-setup af voor ingelogde users zónder bevestigde OTP-device.
    - Laat alle two_factor views door (herkend via namespace/app_name).
    - Laat login/logout/set_password en statische assets door.
    - Redirect alleen op GET (niet op POST om data-verlies te voorkomen).
    """
    def process_request(self, request):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return  # niet ingelogd -> niets afdwingen

        # Heeft gebruiker al een (bevestigd) device? Dan niets afdwingen
        if default_device(user):
            return

        # Bepaal huidige view
        match = getattr(request, "resolver_match", None) or resolve(request.path_info)

        # Two-factor eigen views altijd toelaten (setup, qr, login wizard, etc.)
        if match and (match.app_name == "two_factor" or match.namespace == "two_factor"):
            return

        # Eigen whitelisted views (login/logout/set_password) toelaten
        if match and match.view_name in SAFE_URLNAMES:
            return

        # Statische assets en dev-tools toelaten
        if request.path_info.startswith(SAFE_PATH_PREFIXES):
            return

        # Anders: dwing naar 2FA-setup (alleen op GET om POST-data te bewaren)
        if request.method == "GET":
            setup_url = reverse("two_factor:setup")
            return redirect(f"{setup_url}?next={request.get_full_path()}")

        # Voor POST/PUT/etc niets doen; laat de target-view zelf beslissen
        return