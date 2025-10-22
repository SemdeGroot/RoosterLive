# maak bestand: jouwapp/context_processors.py
import json

def security_flags(request):
    """
    Geeft flags door aan templates:
    - authenticated      (bool)
    - has_webauthn       (bool)
    - just_logged_in     (bool; 1x true direct na login)
    """
    authenticated = request.user.is_authenticated
    has_webauthn = False
    if authenticated:
        # werkt zo als je model/relatie zoals eerder is opgezet:
        has_webauthn = request.user.webauthn_credentials.exists()

    # pop = éénmalig na login
    just_logged_in = bool(request.session.pop("just_logged_in", False))

    data = {
        "authenticated": authenticated,
        "has_webauthn": has_webauthn,
        "just_logged_in": just_logged_in,
        "username": request.user.get_username() if request.user.is_authenticated else None
    }
    # Geef JSON-string mee zodat je dit safe in JS kunt zetten
    return {"SECURITY_JSON": json.dumps(data)}
