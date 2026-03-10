# Profiel (Technisch)

## Technisch ontwerp
De Profiel module in de **Apo Jansen App** is gebaseerd op een One-to-One relatie tussen het Django `User` model en het `UserProfile` model. Deze module beheert niet alleen persoonlijke data, maar ook beveiligingsmechanismen (Passkeys), notificatievoorkeuren en integratie-tokens (WebCal).

## Datamodel
De belangrijkste modellen zijn:

### UserProfile
- `user`: One-to-One koppeling met `User`.
- `organization`: Koppeling met het `Organization` model.
- `function`: Koppeling met het `Function` model.
- `calendar_token`: Unieke UUID voor iCal/WebCal feeds.
- `avatar` / `avatar_hash`: Afbeelding en hash voor caching-beheer.
- `dienstverband`: Keuze tussen "vast" of "oproep".
- `work_mon_am` etc.: Booleans voor vaste werkdagen (gebruikt voor automatische beschikbaarheid).

### NotificationPreferences
- `profile`: One-to-One koppeling met `UserProfile`.
- Bevat diverse booleans voor push- en e-mailnotificaties per categorie.

### WebAuthnPasskey
- Beheert WebAuthn credentials voor biometrische login/passkeys.
- `credential_id`, `public_key`, `sign_count`.
- Koppeling met `device_hash` voor device-specifieke authenticatie.

## Implementatiedetails
De module bevat logica voor de volgende processen:

- **Avatar Hashing**: Bij het uploaden van een nieuwe avatar wordt een hash gegenereerd en opgeslagen in `avatar_hash`. Dit wordt in de frontend gebruikt om browser-caching te forceren bij wijzigingen.
- **WebCal Integratie**: Het `calendar_token` wordt gebruikt in de URL's van de ICS-feeds (`core/views/diensten_webcal.py`) om veilige, persoonlijke toegang tot agenda-data te bieden zonder in te loggen.
- **WebAuthn**: De integratie met WebAuthn maakt het mogelijk om in te loggen via biometrie (FaceID/TouchID) op ondersteunde apparaten.
- **Push Notificatie Registratie**: Apparaten kunnen zich registreren voor push-notificaties via het `NativePushToken` model, gekoppeld aan de gebruiker.

## Autorisatie en beveiliging
De toegang wordt beheerd via de volgende Django permissies:

- `can_access_profiel`: Mag de eigen profielinstellingen inzien en bewerken.
- **Token Beveiliging**: Het `calendar_token` moet geheim worden gehouden; bij verlies kan een nieuw token worden gegenereerd (unieke UUID).
- **WebAuthn**: Passkey-registratie en authenticatie verlopen via cryptografisch beveiligde uitwisselingen (`core/views/webauthn.py`).

## Relevante bestanden
De belangrijkste bestanden voor deze module zijn:

- `core/models.py`: Definities van `UserProfile`, `NotificationPreferences` en `WebAuthnPasskey`.
- `core/views/profiel.py`: Bevat de logica voor het bewerken van profielgegevens.
- `core/views/webauthn.py`: Implementatie van WebAuthn/Passkey logica.
- `core/views/diensten_webcal.py`: Gebruikt de `calendar_token` voor agenda-feeds.
