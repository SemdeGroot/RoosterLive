# Afdelingenbeheer (Technisch)

## Technisch ontwerp
De afdelingenmodule is een uitbreiding op de organisatiestructuur en is specifiek ontworpen ter ondersteuning van de module **Medicatiebeoordeling**. Elke afdeling is verplicht gekoppeld aan een organisatie van het type `Zorginstelling`.

## Datamodel
- `core.models.MedicatieReviewAfdeling`: Het centrale model voor afdelingen.
    - `organisatie`: ForeignKey naar `Organization`.
    - `afdeling`: `CharField` voor de naam van de afdeling.
    - `code`: `CharField` (optioneel) voor een externe referentiecode.
    - `created_by` / `updated_by`: Registratie van de gebruiker die de wijziging heeft doorgevoerd.

## Implementatiedetails

- **Views**: De logica bevindt zich in `core.views.admin.admin_afdelingen`, `afdeling_update` en `delete_afdeling`.
- **Forms**: `core.forms.AfdelingEditForm` wordt gebruikt voor zowel creatie als updates.
- **Validatie**: Bij het aanmaken of wijzigen wordt gecontroleerd of de geselecteerde organisatie daadwerkelijk een zorginstelling is via een filter op `Organization.ORG_TYPE_ZORGINSTELLING`.

## Autorisatie en beveiliging

- Om de afdelingenlijst te mogen inzien, is de permissie `can_perform_medicatiebeoordeling` vereist.
- Voor alle mutaties (creëren, updaten, verwijderen) is de specifieke permissie `can_manage_afdelingen` vereist.
- Bij elke mutatie worden de `updated_by` en `updated_at` velden automatisch bijgewerkt.

## Relevante bestanden

- `core/views/admin.py`: Bevat de view-logica.
- `core/models.py`: Definieert `MedicatieReviewAfdeling`.
- `core/forms.py`: Bevat `AfdelingEditForm`.
