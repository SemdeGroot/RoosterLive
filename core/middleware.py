from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.deprecation import MiddlewareMixin
from django.urls.exceptions import Resolver404
from two_factor.utils import default_device

SAFE_URLNAMES = {"login", "logout", "set_password", "passkey_setup"}

SAFE_PATH_PREFIXES = (
    "/static/", "/media/", "/favicon.ico",
    "/service_worker.",          # alle versies: v19, v20, etc
    "/__reload__/",
    "/manifest.json",
    "api/baxter/machine-statistieken/ingest/",
)

class Enforce2FAMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return  # niet ingelogd -> niets afdwingen

        if user.username == "apotheek_kiosk":
            return  # bypass

        # Assets/devtools/PWA eerst, zodat resolve() nooit nodig is
        if request.path_info.startswith(SAFE_PATH_PREFIXES):
            return

        # Heeft gebruiker al een (bevestigd) device? Dan niets afdwingen
        if default_device(user):
            return

        # Resolve veilig (kan Resolver404 geven bij onbekende paths)
        try:
            match = getattr(request, "resolver_match", None) or resolve(request.path_info)
        except Resolver404:
            return  # laat Django verder gaan; geen middleware-500

        # Two-factor eigen views altijd toelaten
        if match and (match.app_name == "two_factor" or match.namespace == "two_factor"):
            return

        # Eigen whitelisted views toelaten
        if match and match.view_name in SAFE_URLNAMES:
            return

        # Alleen HTML-paginaverzoeken dwingen naar 2FA-setup
        accept = request.META.get("HTTP_ACCEPT", "")
        if "text/html" not in accept:
            return

        # Alleen op GET redirecten
        if request.method == "GET":
            setup_url = reverse("two_factor:setup")
            return redirect(f"{setup_url}?next={request.get_full_path()}")

        # Voor POST/PUT/etc niets doen; laat de view zelf beslissen
        return