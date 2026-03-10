# Groepenbeheer (Technisch)

## Technisch ontwerp
Groepenbeheer maakt direct gebruik van het ingebouwde permissiesysteem van Django (`django.contrib.auth`). Groepen fungeren als containers voor `Permission` objecten die aan gebruikers kunnen worden gekoppeld.

## Datamodel
- `django.contrib.auth.models.Group`: Het standaard Django groepsmodel.
- `django.contrib.auth.models.Permission`: Het standaard Django permissiemodel.
- `core.models.StandaardInlog`: Een singleton model dat de configuratie opslaat voor de algemene Kiosk-account. Dit model bevat de `standaard_rol` (ForeignKey naar Group).

## Implementatiedetails

- **Views**: De logica bevindt zich in `core.views.admin.admin_groups` en de delete actie in `group_delete`.
- **Permission Sync**: Bij het laden van de groepen-beheerpagina wordt `sync_custom_permissions()` aangeroepen. Deze functie zorgt ervoor dat alle programmatisch gedefinieerde permissies (zoals die voor specifieke modules) in de database aanwezig zijn.
- **Form**: `core.forms.GroupWithPermsForm` handelt het opslaan van de groepsnaam en de Many-to-Many relatie met permissies af.
- **Kiosk Logic**: De `StandaardInlog` configuratie wordt gebruikt om te bepalen welke rechten de algemene "Apotheek Algemeen" gebruiker krijgt bij het inloggen op een kiosk-zuil.

## Autorisatie en beveiliging

- Toegang tot het dashboard vereist `can_access_admin`.
- Het beheren van groepen en inloginstellingen vereist `can_manage_users`.
- Het verwijderen van groepen is beveiligd met `can_manage_groups`.
- Er vindt een integriteitscheck plaats bij het verwijderen: als `group.user_set.count() > 0`, wordt de verwijdering geblokkeerd.

## Relevante bestanden

- `core/views/admin.py`: Bevat `admin_groups` en `group_delete`.
- `core/models.py`: Bevat de definitie van `StandaardInlog`.
- `core/forms.py`: Bevat `GroupWithPermsForm` en `StandaardInlogForm`.
- `core/permissions_cache.py`: (Indien aanwezig) Bevat vaak de definities van custom permissies die gesynchroniseerd worden.
