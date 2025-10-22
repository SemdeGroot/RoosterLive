# core/views/views_webauthn.py
import json
import base64
import logging
from typing import Optional, List, Dict, Any

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, get_user_model
from django.utils.text import capfirst

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
    # Optie-enums/structs
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    # Payload-structs die verify_* verwachten
    RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorAttestationResponse,
    AuthenticatorAssertionResponse,
)

logger = logging.getLogger(__name__)

# -------------------- helpers --------------------

def bytes_to_b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def _expected_rp_id(request) -> str:
    # host zonder poort
    return request.get_host().split(":")[0]

def _expected_origin(request) -> str:
    host = request.get_host()
    secure = request.is_secure() or host.endswith(".ngrok-free.dev")
    scheme = "https" if secure else "http"
    return f"{scheme}://{host}"

def _safe(s: Optional[str], n: int = 32) -> str:
    if not s:
        return ""
    return s if len(s) <= n else (s[:n] + "…")

def _parse_client_data_json(cdj_b64u: str) -> Dict[str, Any]:
    """Decode clientDataJSON (b64url) om type/origin/challenge te loggen."""
    try:
        pad = "=" * ((4 - (len(cdj_b64u) % 4)) % 4)
        raw = base64.urlsafe_b64decode(cdj_b64u + pad)
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        logger.exception("clientDataJSON parse error: %s", e)
        return {}

def _user_struct(user) -> dict:
    """
    WebAuthn user entity:
      - id: bytes
      - name: wat iOS vaak toont → gebruikersnaam met hoofdletter
      - display_name: secundair label → ook gebruikersnaam met hoofdletter
    """
    username = user.get_username()
    label = capfirst(username)
    return {
        "id": str(user.pk).encode("utf-8"),
        "name": label,
        "display_name": label,
    }

def _options_to_json_dict(opts) -> dict:
    """Serialiseer via library → bewaart b64url strings zoals de browser verwacht."""
    return json.loads(options_to_json(opts))

def _extract_challenge_b64u(options_json: dict) -> Optional[str]:
    pk = options_json.get("publicKey") or {}
    return pk.get("challenge") or options_json.get("challenge")

# -------------------- REGISTRATION --------------------

@login_required
@require_POST
def register_begin(request):
    user = request.user

    # exclude_credentials als structs + transport enums
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

    selection = AuthenticatorSelectionCriteria(
        authenticator_attachment=AuthenticatorAttachment.PLATFORM,
        resident_key=ResidentKeyRequirement.REQUIRED,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    u = _user_struct(user)

    # Nieuwe en legacy signature ondersteunen
    try:
        opts = generate_registration_options(
            rp_id=_expected_rp_id(request),
            rp_name="Jansen App",
            user=u,
            authenticator_selection=selection,
            timeout=60000,
            attestation=AttestationConveyancePreference.NONE,
            exclude_credentials=exclude,
        )
    except TypeError:
        opts = generate_registration_options(
            rp_id=_expected_rp_id(request),
            rp_name="Jansen App",
            user_id=u["id"],
            user_name=u["name"],
            user_display_name=u["display_name"],
            authenticator_selection=selection,
            timeout=60000,
            attestation=AttestationConveyancePreference.NONE,
            exclude_credentials=exclude,
        )

    resp = _options_to_json_dict(opts)
    challenge_b64u = _extract_challenge_b64u(resp)
    if not challenge_b64u:
        return HttpResponseBadRequest("Challenge ontbreekt in opties.")
    request.session["webauthn_register_challenge"] = challenge_b64u

    logger.debug("[register_begin] rp_id=%s origin=%s challenge=%s",
                 _expected_rp_id(request), _expected_origin(request), _safe(challenge_b64u))
    return JsonResponse(resp)


@login_required
@require_POST
def register_complete(request):
    """
    Maak officiële structs met bytesvelden en verifieer met expected_challenge als BYTES.
    """
    expected_challenge = request.session.get("webauthn_register_challenge")
    if not expected_challenge:
        return HttpResponseBadRequest("Geen challenge in session.")

    try:
        body = json.loads(request.body.decode())
    except Exception:
        return HttpResponseBadRequest("Ongeldige JSON.")

    # Debug/early sanity
    cdj = (body.get("response") or {}).get("clientDataJSON")
    cd = _parse_client_data_json(cdj) if cdj else {}
    cd_type = cd.get("type"); cd_origin = cd.get("origin"); cd_chal = cd.get("challenge")
    logger.debug(
        "[register_complete] expected_rp_id=%s expected_origin=%s expected_chal=%s "
        "client.type=%s client.origin=%s client.chal=%s",
        _expected_rp_id(request), _expected_origin(request), _safe(expected_challenge),
        cd_type, cd_origin, _safe(cd_chal)
    )
    if cd_type and cd_type != "webauthn.create":
        return HttpResponseBadRequest(f"clientDataJSON.type mismatch: {cd_type}")
    if cd_origin and cd_origin != _expected_origin(request):
        return HttpResponseBadRequest(f"origin mismatch: client={cd_origin} server={_expected_origin(request)}")
    if cd_chal and cd_chal != expected_challenge:
        return HttpResponseBadRequest("challenge mismatch (client vs server).")

    # Structs (LET OP: response velden naar BYTES)
    try:
        cred_struct = RegistrationCredential(
            id=body["id"],  # string
            raw_id=base64url_to_bytes(body.get("rawId") or body["id"]),  # bytes
            type=body.get("type", "public-key"),
            response=AuthenticatorAttestationResponse(
                client_data_json=base64url_to_bytes(body["response"]["clientDataJSON"]),
                attestation_object=base64url_to_bytes(body["response"]["attestationObject"]),
            ),
        )
    except KeyError:
        return HttpResponseBadRequest("Onvolledige credential payload.")

    # Verify met challenge als BYTES (fix voor mismatch in sommige lib-versies)
    try:
        verified = verify_registration_response(
            credential=cred_struct,
            expected_challenge=base64url_to_bytes(expected_challenge),  # BYTES!
            expected_rp_id=_expected_rp_id(request),
            expected_origin=_expected_origin(request),
            require_user_verification=True,
        )
    except Exception as e:
        logger.exception("verify_registration_response failed: %s", e)
        return HttpResponseBadRequest(f"Verificatie mislukt: {e}")

    # Opslaan
    cred_id_b64u = verified.credential_id
    pubkey = verified.credential_public_key
    public_key_b64u = bytes_to_b64u(pubkey) if isinstance(pubkey, (bytes, bytearray)) else str(pubkey)
    sign_count = int(verified.sign_count)

    WebAuthnCredential.objects.get_or_create(
        user=request.user,
        credential_id=cred_id_b64u,
        defaults={
            "public_key": public_key_b64u,
            "sign_count": sign_count,
            "transports": ",".join(body.get("transports", []) or []),
        },
    )

    request.session.pop("webauthn_register_challenge", None)
    logger.debug("[register_complete] OK cred_id=%s sign_count=%s", _safe(cred_id_b64u), sign_count)
    return JsonResponse({"status": "ok"})

# -------------------- AUTHENTICATION --------------------

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
                        transports=None,
                    )
                )
            allow_credentials = descs or None
        except User.DoesNotExist:
            pass  # discoverable toestaan

    opts = generate_authentication_options(
        rp_id=_expected_rp_id(request),
        timeout=60000,
        user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=allow_credentials,  # None => discoverable toegestaan
    )

    resp = _options_to_json_dict(opts)
    challenge_b64u = _extract_challenge_b64u(resp)
    if not challenge_b64u:
        return HttpResponseBadRequest("Challenge ontbreekt in opties.")
    request.session["webauthn_auth_challenge"] = challenge_b64u

    logger.debug("[auth_begin] rp_id=%s origin=%s challenge=%s",
                 _expected_rp_id(request), _expected_origin(request), _safe(challenge_b64u))
    return JsonResponse(resp)


@require_POST
def auth_complete(request):
    expected_challenge = request.session.get("webauthn_auth_challenge")
    if not expected_challenge:
        return HttpResponseBadRequest("Geen challenge in session.")

    try:
        body = json.loads(request.body.decode())
    except Exception:
        return HttpResponseBadRequest("Ongeldige JSON.")

    # Debug/early sanity
    cdj = (body.get("response") or {}).get("clientDataJSON")
    cd = _parse_client_data_json(cdj) if cdj else {}
    cd_type = cd.get("type"); cd_origin = cd.get("origin"); cd_chal = cd.get("challenge")
    logger.debug(
        "[auth_complete] expected_rp_id=%s expected_origin=%s expected_chal=%s "
        "client.type=%s client.origin=%s client.chal=%s",
        _expected_rp_id(request), _expected_origin(request), _safe(expected_challenge),
        cd_type, cd_origin, _safe(cd_chal)
    )
    if cd_type and cd_type != "webauthn.get":
        return HttpResponseBadRequest(f"clientDataJSON.type mismatch: {cd_type}")
    if cd_origin and cd_origin != _expected_origin(request):
        return HttpResponseBadRequest(f"origin mismatch: client={cd_origin} server={_expected_origin(request)}")
    if cd_chal and cd_chal != expected_challenge:
        return HttpResponseBadRequest("challenge mismatch (client vs server).")

    # Structs (LET OP: response velden naar BYTES)
    try:
        cred_struct = AuthenticationCredential(
            id=body["id"],  # string
            raw_id=base64url_to_bytes(body.get("rawId") or body["id"]),  # bytes
            type=body.get("type", "public-key"),
            response=AuthenticatorAssertionResponse(
                client_data_json=base64url_to_bytes(body["response"]["clientDataJSON"]),
                authenticator_data=base64url_to_bytes(body["response"]["authenticatorData"]),
                signature=base64url_to_bytes(body["response"]["signature"]),
                user_handle=(
                    base64url_to_bytes(body["response"]["userHandle"])
                    if (body["response"].get("userHandle")) else None
                ),
            ),
        )
    except KeyError:
        return HttpResponseBadRequest("Onvolledige credential payload.")

    # Lookups voor verify
    def _lookup_public_key(credential_id_b64u: str) -> bytes:
        cred = WebAuthnCredential.objects.get(credential_id=credential_id_b64u)
        return base64url_to_bytes(cred.public_key)

    def _lookup_sign_count(credential_id_b64u: str) -> int:
        return WebAuthnCredential.objects.get(credential_id=credential_id_b64u).sign_count

    # Verify met challenge als BYTES (consistent met registration)
    try:
        verified = verify_authentication_response(
            credential=cred_struct,
            expected_challenge=base64url_to_bytes(expected_challenge),  # BYTES!
            expected_rp_id=_expected_rp_id(request),
            expected_origin=_expected_origin(request),
            require_user_verification=True,
            credential_public_key_lookup=_lookup_public_key,
            credential_current_sign_count_lookup=_lookup_sign_count,
        )
    except Exception as e:
        logger.exception("verify_authentication_response failed: %s", e)
        return HttpResponseBadRequest(f"Authenticatie mislukt: {e}")

    # Update counter
    WebAuthnCredential.objects.filter(
        credential_id=verified.credential_id
    ).update(sign_count=int(verified.new_sign_count))

    # Vind user en log in
    try:
        cred = WebAuthnCredential.objects.select_related("user").get(
            credential_id=verified.credential_id
        )
    except WebAuthnCredential.DoesNotExist:
        return HttpResponseBadRequest("Credential niet gevonden.")

    auth_login(request, cred.user)
    request.session.pop("webauthn_auth_challenge", None)
    logger.debug("[auth_complete] OK cred_id=%s", _safe(verified.credential_id))
    return JsonResponse({"status": "ok"})