# core/views/errors.py
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.csrf import requires_csrf_token

@requires_csrf_token
def csrf_failure(request, reason=""):
    """
    Wordt aangeroepen als de CSRF-check faalt.
    In plaats van een kale 403 sturen we de gebruiker terug naar de login
    met een duidelijke melding.
    """
    messages.error(
        request,
        _("Je sessie is verlopen of ongeldig. Log opnieuw in.")
    )
    # jouw login view is two_factor:login
    return redirect("two_factor:login")