# core/views/views_webauthn.py
import json
import base64
from typing import Optional, List

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, get_user_model

from core.models import WebAuthnCredential

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
    AuthenticatorTransport,
    AuthenticatorAttachment,          # <-- toevoegen
)

# -------------------- helpers --------------------

def bytes_to_b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def _expected_rp_id(request) -> str:
    return request.get_host().split(":")[0]

def _expected_origin(request) -> str:
    host = request.get_host()
    secure = request.is_secure() or host.endswith(".ngrok-free.dev")
    scheme = "https" if secure else "http"
    return f"{scheme}://{host}"

def _user_struct(user) -> dict:
    return {
        "id": str(user.pk).encode("utf-8"),
        "name": user.get_username(),
        "display_name": user.get_full_name() or user.get_username(),
    }

def _json_from_options(opts) -> dict:
    return json.loads(options_to_json(opts))

def _extract_challenge_b64u(options_json: dict) -> Optional[str]:
    pk = options_json.get("publicKey") or {}
    return pk.get("challenge") or options_json.get("challenge")

# -------------------- registration --------------------

@login_required
@require_POST
def register_begin(request):
    user = request.user

    # Exclude bestaande credentials als descriptors (structs, geen dicts)
    exclude: List[PublicKeyCredentialDescriptor] = []
    for cred in user.webauthn_credentials.all():
        transports = [t for t in (cred.transports.split(",") if cred.transports else []) if t]
        exclude.append(
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(cred.credential_id),
                type="public-key",
                transports=[AuthenticatorTransport(t) for t in transports] if transports else None,
            )
        )

    # Gebruik de struct, niet een dict → voorkomt jouw AttributeError
    selection = AuthenticatorSelectionCriteria(
        authenticator_attachment=AuthenticatorAttachment.PLATFORM,   # i.p.v. "platform"
        resident_key=ResidentKeyRequirement.REQUIRED,                # i.p.v. "required"
        user_verification=UserVerificationRequirement.REQUIRED,      # i.p.v. "required"
    )

    u = _user_struct(user)

    # Sommige versies hebben 'user='; oudere verwachten losse user_* args.
    try:
        opts = generate_registration_options(
            rp_id=_expected_rp_id(request),
            rp_name="Apotheek Jansen",
            user=u,
            authenticator_selection=selection,
            timeout=60000,
            attestation="none",
            exclude_credentials=exclude,
        )
    except TypeError:
        # Legacy signature (zonder 'user='). 'selection' blijft wel een struct.
        opts = generate_registration_options(
            rp_id=_expected_rp_id(request),
            rp_name="Apotheek Jansen",
            user_id=u["id"],
            user_name=u["name"],
            user_display_name=u["display_name"],
            authenticator_selection=selection,
            timeout=60000,
            attestation="none",
            exclude_credentials=exclude,
        )

    resp = _json_from_options(opts)
    challenge_b64u = _extract_challenge_b64u(resp)
    if not challenge_b64u:
        return HttpResponseBadRequest("Challenge ontbreekt in opties.")
    request.session["webauthn_register_challenge"] = challenge_b64u

    return JsonResponse(resp)


@login_required
@require_POST
def register_complete(request):
    user = request.user
    try:
        body = json.loads(request.body.decode())
    except Exception:
        return HttpResponseBadRequest("Ongeldige JSON.")

    expected_challenge = request.session.get("webauthn_register_challenge")
    if not expected_challenge:
        return HttpResponseBadRequest("Geen challenge in session.")

    try:
        verified = verify_registration_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=_expected_rp_id(request),
            expected_origin=_expected_origin(request),
            require_user_verification=True,
        )
    except Exception as e:
        return HttpResponseBadRequest(f"Verificatie mislukt: {e}")

    cred_id_b64u = verified.credential_id
    pubkey = verified.credential_public_key
    public_key_b64u = bytes_to_b64u(pubkey) if isinstance(pubkey, (bytes, bytearray)) else str(pubkey)
    sign_count = int(verified.sign_count)

    WebAuthnCredential.objects.get_or_create(
        user=user,
        credential_id=cred_id_b64u,
        defaults={
            "public_key": public_key_b64u,
            "sign_count": sign_count,
            "transports": ",".join(body.get("transports", []) or []),
        },
    )

    request.session.pop("webauthn_register_challenge", None)
    return JsonResponse({"status": "ok"})

# -------------------- authentication --------------------

@require_POST
def auth_begin(request):
    try:
        payload = json.loads(request.body.decode())
    except Exception:
        payload = {}

    username = (payload.get("username") or "").strip()

    allow_credentials: Optional[List[PublicKeyCredentialDescriptor]] = None
    if username:
        User = get_user_model()
        try:
            u = User.objects.get(username=username)
            descs: List[PublicKeyCredentialDescriptor] = []
            for cred in u.webauthn_credentials.all():
                descs.append(
                    PublicKeyCredentialDescriptor(
                        id=base64url_to_bytes(cred.credential_id),
                        type="public-key",
                        transports=None
                    )
                )
            allow_credentials = descs or None
        except User.DoesNotExist:
            pass  # laat discoverable toe

    opts = generate_authentication_options(
        rp_id=_expected_rp_id(request),
        timeout=60000,
        user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=allow_credentials,  # None => discoverable toegestaan
    )

    resp = _json_from_options(opts)
    challenge_b64u = _extract_challenge_b64u(resp)
    if not challenge_b64u:
        return HttpResponseBadRequest("Challenge ontbreekt in opties.")
    request.session["webauthn_auth_challenge"] = challenge_b64u

    return JsonResponse(resp)


@require_POST
def auth_complete(request):
    try:
        body = json.loads(request.body.decode())
    except Exception:
        return HttpResponseBadRequest("Ongeldige JSON.")

    expected_challenge = request.session.get("webauthn_auth_challenge")
    if not expected_challenge:
        return HttpResponseBadRequest("Geen challenge in session.")

    def _lookup_public_key(credential_id_b64u: str) -> bytes:
        cred = WebAuthnCredential.objects.get(credential_id=credential_id_b64u)
        return base64url_to_bytes(cred.public_key)

    def _lookup_sign_count(credential_id_b64u: str) -> int:
        return WebAuthnCredential.objects.get(credential_id=credential_id_b64u).sign_count

    try:
        verified = verify_authentication_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=_expected_rp_id(request),
            expected_origin=_expected_origin(request),
            require_user_verification=True,
            credential_public_key_lookup=_lookup_public_key,
            credential_current_sign_count_lookup=_lookup_sign_count,
        )
    except Exception as e:
        return HttpResponseBadRequest(f"Authenticatie mislukt: {e}")

    WebAuthnCredential.objects.filter(
        credential_id=verified.credential_id
    ).update(sign_count=int(verified.new_sign_count))

    try:
        cred = WebAuthnCredential.objects.select_related("user").get(
            credential_id=verified.credential_id
        )
    except WebAuthnCredential.DoesNotExist:
        return HttpResponseBadRequest("Credential niet gevonden.")

    auth_login(request, cred.user)
    request.session.pop("webauthn_auth_challenge", None)

    return JsonResponse({"status": "ok"})