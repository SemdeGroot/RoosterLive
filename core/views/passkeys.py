# core/views/passkeys.py
import json
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from core.forms import IdentifierAuthenticationForm 
from ._helpers import is_mobile_request
from django.shortcuts import redirect

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    AuthenticatorAttachment,  
)
from webauthn.helpers.exceptions import (
    InvalidRegistrationResponse,
    InvalidAuthenticationResponse,
)

from core.models import WebAuthnPasskey


# =========================
# interne helpers
# =========================
def resolve_user_from_identifier(identifier: str):
    """
    Resolve op basis van:
    - email (met @)
    - unieke first_name
    Raises ValueError bij niet-unieke voornaam.
    """
    User = get_user_model()
    ident = (identifier or "").strip()
    if not ident:
        return None

    if "@" in ident:
        return User.objects.filter(email__iexact=ident).only("id").first()

    qs = User.objects.filter(first_name__iexact=ident).only("id")
    cnt = qs.count()
    if cnt == 1:
        return qs.first()
    if cnt > 1:
        raise ValueError("Deze voornaam komt vaker voor. Log in met je e-mailadres.")
    return None

def _get_rp_id(request: HttpRequest) -> str:
    """
    rp_id moet een domein zijn, ZONDER schema.
    """
    host = request.get_host()  # "example.com" of "example.com:8000"
    host = host.split(":")[0]  # poort weg
    return host


def _get_origin(request: HttpRequest) -> str:
    """
    expected_origin moet juist WEL schema + host hebben.
    """
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}"


def _store_reg_state(request: HttpRequest, challenge_b64u: str, device_hash: str) -> None:
    request.session["webauthn_reg_challenge"] = challenge_b64u
    request.session["webauthn_reg_device_hash"] = device_hash


def _pop_reg_state(request: HttpRequest):
    challenge = request.session.pop("webauthn_reg_challenge", None)
    device_hash = request.session.pop("webauthn_reg_device_hash", "") or ""
    return challenge, device_hash


def _store_auth_state(request: HttpRequest, challenge_b64u: str, user_id: int, next_url: str):
    request.session["webauthn_auth_challenge"] = challenge_b64u
    request.session["webauthn_auth_user_id"] = user_id
    request.session["webauthn_auth_next"] = next_url


def _pop_auth_state(request: HttpRequest):
    challenge = request.session.pop("webauthn_auth_challenge", None)
    user_id = request.session.pop("webauthn_auth_user_id", None)
    next_url = request.session.pop("webauthn_auth_next", "/")
    return challenge, user_id, next_url


def _mark_passkey_skip_for_device(request: HttpRequest, device_hash: str):
    """
    Onthoud in de session dat we voor dit device_hash niet meer moeten
    redirecten naar de passkey-setup.
    """
    if not device_hash:
        return
    skipped = request.session.get("webauthn_skip_devices", {})
    skipped[device_hash] = True
    request.session["webauthn_skip_devices"] = skipped


def _is_passkey_skip_for_device(request: HttpRequest, device_hash: str) -> bool:
    skipped = request.session.get("webauthn_skip_devices", {})
    return bool(device_hash and skipped.get(device_hash))


# =========================
# Passkey setup pagina
# =========================

class PasskeySetupView(TemplateView):
    template_name = "accounts/quick_login_setup.html"

    def dispatch(self, request, *args, **kwargs):
        # Je oude "geen setup op desktop" mag blijven
        if not is_mobile_request(request):
            next_url = request.GET.get("next") or reverse("home")
            return redirect(next_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next_url"] = self.request.GET.get("next") or "/"
        return ctx

# =========================
# REGISTRATIE: opties leveren
# POST /api/passkeys/options/register/
# =========================

@require_POST
@login_required
def passkey_registration_options(request: HttpRequest):
    body = json.loads(request.body.decode("utf-8"))

    user = request.user
    rp_id = _get_rp_id(request)

    # Bestaande passkeys van deze gebruiker → excludeCredentials
    existing_ids = list(
        WebAuthnPasskey.objects.filter(user=user).values_list("credential_id", flat=True)
    )

    exclude_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(cred_id),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )
        for cred_id in existing_ids
    ]

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=getattr(settings, "WEBAUTHN_RP_NAME", "Mijn App"),
        user_id=str(user.pk).encode("utf-8"),
        user_name=user.get_username(),
        user_display_name=user.get_full_name() or user.get_username(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude_credentials,
    )

    # options_to_json() encodeert bytes (challenge, user.id, etc.) naar base64url strings
    opts = json.loads(options_to_json(options))

    # challenge als base64url-string opslaan; we decoderen straks weer naar bytes
    challenge_b64u = opts["challenge"]
    _store_reg_state(request, challenge_b64u, "")

    return JsonResponse(opts)


# =========================
# REGISTRATIE: credential verifiëren & opslaan
# POST /api/passkeys/register/
# =========================

@require_POST
@login_required
def passkey_register(request: HttpRequest):
    user = request.user
    body = json.loads(request.body.decode("utf-8"))

    challenge_b64u, device_hash = _pop_reg_state(request)
    if not challenge_b64u:
        return JsonResponse({"ok": False, "error": "Geen challenge gevonden"}, status=400)

    try:
        verification = verify_registration_response(
            credential=body,  # raw dict met base64url strings → OK voor py-webauthn 2.x
            expected_challenge=base64url_to_bytes(challenge_b64u),
            expected_rp_id=_get_rp_id(request),
            expected_origin=_get_origin(request),
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        # Hier kreeg je eerder "The string did not match the expected pattern"
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    # In py-webauthn 2.7 is verification een dataclass (VerifiedRegistration), geen .json()
    # credential_id: we nemen gewoon de id die de browser stuurde (base64url-string),
    # zodat login-allowCredentials precies matcht.
    credential_id_b64u = body.get("id")
    if not credential_id_b64u:
        # fallback: encode verification.credential_id (bytes) zelf naar base64url
        # maar normaal gesproken is body["id"] er altijd
        cred_id_bytes = verification.credential_id
        from base64 import urlsafe_b64encode
        credential_id_b64u = urlsafe_b64encode(cred_id_bytes).decode("ascii").rstrip("=")

    public_key_bytes = verification.credential_public_key
    sign_count = verification.sign_count
    backed_up = getattr(verification, "credential_backed_up", False)

    ua = (request.META.get("HTTP_USER_AGENT") or "").strip()
    if len(ua) > 255:
        ua = ua[:255]

    WebAuthnPasskey.objects.update_or_create(
        credential_id=credential_id_b64u,
        defaults={
            "user": user,
            "public_key": public_key_bytes,
            "sign_count": sign_count,
            "backed_up": bool(backed_up),
            "last_used_at": timezone.now(),
            "device_hash": "",
            "user_agent": ua,
        },
    )

    return JsonResponse({"ok": True})


# =========================
# LOGIN STAP 1: password + check of passkey beschikbaar is
# POST /api/passkeys/login/password/
# =========================

@require_POST
def passkey_password_login(request: HttpRequest):
    body = json.loads(request.body.decode("utf-8"))
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    # device_hash halen we wel op, maar gebruiken we niet meer voor filtering
    # device_hash = body.get("device_hash") or "" 
    next_url = body.get("next") or "/"

    form = IdentifierAuthenticationForm(
        request=request,
        data={
            "username": username,
            "password": password,
        },
    )

    if not form.is_valid():
        return JsonResponse(
            {"ok": False, "error": "Onjuiste gebruikersnaam of wachtwoord"},
            status=400,
        )

    user = form.get_user()
    if user is None:
        return JsonResponse(
            {"ok": False, "error": "Onjuiste gebruikersnaam of wachtwoord"},
            status=400,
        )

    # === WIJZIGING START ===
    # OUD: We zochten specifiek op device_hash. Als die op Android veranderd was, faalde dit.
    # try:
    #     passkey = WebAuthnPasskey.objects.get(user=user, device_hash=device_hash)
    # except WebAuthnPasskey.DoesNotExist:
    #     return JsonResponse({"ok": True, "has_passkey": False})

    # NIEUW: We halen ALLE passkeys van deze gebruiker op.
    # De browser bepaalt zelf wel of hij de private key heeft voor één van deze credentials.
    passkeys = WebAuthnPasskey.objects.filter(user=user)
    
    if not passkeys.exists():
         return JsonResponse({"ok": True, "has_passkey": False})

    # Maak een lijst van ALLE credential ID's van deze gebruiker
    allowed_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(pk.credential_id),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )
        for pk in passkeys
    ]
    # === WIJZIGING EIND ===

    options = generate_authentication_options(
        rp_id=_get_rp_id(request),
        allow_credentials=allowed_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    opts = json.loads(options_to_json(options))
    challenge_b64u = opts["challenge"]

    _store_auth_state(request, challenge_b64u, user.id, next_url)

    # has_passkey is True zolang de user ERGENS een passkey heeft.
    return JsonResponse({"ok": True, "has_passkey": True, "options": opts})

# =========================
# LOGIN STAP 2: WebAuthn assertion verifiëren
# POST /api/passkeys/login/authenticate/
# =========================

@require_POST
def passkey_authenticate(request: HttpRequest):
    body = json.loads(request.body.decode("utf-8"))

    challenge_b64u, user_id, next_url = _pop_auth_state(request)
    if not challenge_b64u or not user_id:
        return JsonResponse({"ok": False, "error": "Geen login challenge actief"}, status=400)

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Onbekende gebruiker"}, status=400)

    # Zoek alle passkeys van deze user; in theorie kun je meerdere hebben
    passkeys = list(WebAuthnPasskey.objects.filter(user=user))
    if not passkeys:
        return JsonResponse({"ok": False, "error": "Geen passkeys gevonden"}, status=400)

    # credentialId in de response gebruiken om juiste key te pakken
    credential_id_b64u = body.get("id")
    if not credential_id_b64u:
        return JsonResponse({"ok": False, "error": "Geen credential ID"}, status=400)

    try:
        passkey = next(pk for pk in passkeys if pk.credential_id == credential_id_b64u)
    except StopIteration:
        return JsonResponse({"ok": False, "error": "Credential onbekend"}, status=400)

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=base64url_to_bytes(challenge_b64u),
            expected_rp_id=_get_rp_id(request),
            expected_origin=_get_origin(request),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    # VerifiedAuthentication dataclass → direct attribuut gebruiken
    new_sign_count = verification.new_sign_count

    ua = (request.META.get("HTTP_USER_AGENT") or "").strip()
    if len(ua) > 255:
        ua = ua[:255]

    passkey.sign_count = new_sign_count
    passkey.last_used_at = timezone.now()
    passkey.user_agent = ua
    passkey.save(update_fields=["sign_count", "last_used_at", "user_agent"])

    # HIER: user volledig inloggen en 2FA overslaan
    login(request, user)

    return JsonResponse({"ok": True, "redirect_url": next_url})


# =========================
# EERSTE LOGIN → PASSKEY OFFER (per device)
# POST /api/passkeys/should-offer/
# =========================
@require_POST
@login_required
def passkey_should_offer(request: HttpRequest):
    body = json.loads(request.body.decode("utf-8"))
    next_url = body.get("next") or (request.path + request.META.get("QUERY_STRING", ""))

    user = request.user

    # user heeft al minstens één passkey -> nooit offeren
    if WebAuthnPasskey.objects.filter(user=user).exists():
        return JsonResponse({"offer": False})

    # in deze sessie geskipt?
    if bool(request.session.get("webauthn_skip_offer", False)):
        return JsonResponse({"offer": False})

    setup_url = reverse("passkey_setup")
    setup_url = f"{setup_url}?{urlencode({'next': next_url})}"
    return JsonResponse({"offer": True, "setup_url": setup_url})


# =========================
# SKIP-API zodat je niet oneindig prompt
# POST /api/passkeys/skip/
# =========================

@require_POST
@login_required
def passkey_skip(request: HttpRequest):
    request.session["webauthn_skip_offer"] = True
    return JsonResponse({"ok": True})

@require_POST
def passkey_login_options(request: HttpRequest):
    body = json.loads(request.body.decode("utf-8"))
    identifier = (body.get("identifier") or "").strip()
    next_url = body.get("next") or "/"

    if not identifier:
        return JsonResponse({"ok": True, "has_passkey": False})

    try:
        user = resolve_user_from_identifier(identifier)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    if user is None:
        # anti user-enumeration: doe alsof er geen passkey is
        return JsonResponse({"ok": True, "has_passkey": False})

    passkeys = WebAuthnPasskey.objects.filter(user=user)
    if not passkeys.exists():
        return JsonResponse({"ok": True, "has_passkey": False})

    allowed_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(pk.credential_id),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )
        for pk in passkeys
    ]

    options = generate_authentication_options(
        rp_id=_get_rp_id(request),
        allow_credentials=allowed_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    opts = json.loads(options_to_json(options))
    _store_auth_state(request, opts["challenge"], user.id, next_url)

    return JsonResponse({"ok": True, "has_passkey": True, "options": opts})
