# STS-halfjes (Technisch)

De module STS-halfjes registreert onnodig gehalveerde geneesmiddelen in baxterrollen en ontsluit deze voor externe organisaties.

## Technisch ontwerp
De module combineert database-registratie met PDF-generatie en asynchrone distributie per organisatie. De architectuur is ontworpen om meldingen per apotheek te groeperen en deze geautomatiseerd te verzenden.

## Datamodel
- `STSHalfje`:
    - `afdeling`: Vrij tekstveld voor de bronafdeling.
    - `item_gehalveerd`: ForeignKey naar `VoorraadItem` (medicijn dat gehalveerd wordt).
    - `item_alternatief`: ForeignKey naar `VoorraadItem` (alternatieve sterkte).
    - `apotheek`: ForeignKey naar `Organization` (doelorganisatie).
    - `patient_naam_enc`: Versleutelde patiëntnaam (`EncryptedCharField`).
    - `patient_geboortedatum_enc`: Versleutelde patiëntgeboortedatum (`EncryptedDateField`).

## Implementatiedetails
- **CRUD**: De view `stshalfjes` in `core/views/stshalfjes.py` beheert de registratie en wijzigingen via `STSHalfjeForm`.
- **PDF Export**: Maakt gebruik van de helper `_render_pdf` (WeasyPrint) om de template `stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html` te converteren.
- **Email Distributie**: De task `send_stshalfjes_pdf_task` verstuurt alleen die meldingen naar een apotheek die expliciet aan die apotheek gekoppeld zijn.

## Autorisatie en beveiliging
- Toegang tot de pagina is beveiligd met `@ip_restricted` en `@login_required`.
- Rechten worden gecontroleerd via:
    - `can_view_baxter_sts_halfjes`: Bekijken.
    - `can_edit_baxter_sts_halfjes`: Wijzigen.
    - `can_send_baxter_sts_halfjes`: Export en verzending.
- Patiëntgegevens worden versleuteld in de database opgeslagen om aan privacy-eisen te voldoen.

## Relevante bestanden
- `core/models.py`: Het `STSHalfje` model.
- `core/views/stshalfjes.py`: De hoofdview en export-functionaliteit.
- `core/tasks.py`: De Celery-task voor verzending.
- `core/forms.py`: Het `STSHalfjeForm`.
- `core/templates/stshalfjes/`: Interface en PDF-layouts.
