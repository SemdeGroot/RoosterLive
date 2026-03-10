# Nazendingen (Technisch)

De Nazendingen-module in de Apotheek Jansen App is ontworpen om een actueel overzicht van niet-leverbare geneesmiddelen te beheren en te distribueren naar externe zorgverleners en andere organisaties.

## Technische Architectuur

De feature is opgebouwd uit de volgende componenten:

### Datamodel
-   **Nazending (`core/models.py`)**: Slaat de gegevens van een nazending op.
    -   `voorraad_item`: `ForeignKey` naar `VoorraadItem`. Dit koppelt de nazending aan een uniek ZI-nummer en een officiële naam.
    -   `datum`: De datum waarop de nazending is geregistreerd.
    -   `nazending_tot`: Een vrij tekstveld voor de verwachte duur of leverdatum.
    -   `alternatief`: Een vrij tekstveld voor vervangende medicatie.

### Toegangsmodel
-   **Beheer**: Alleen medewerkers van de apotheek met de juiste permissies kunnen de module benaderen via de webinterface.
-   **Externe Distributie**: Externe organisaties (zoals zorginstellingen of andere apotheken) hebben **geen toegang** tot de applicatie. Zij ontvangen de informatie uitsluitend als PDF-bijlage via een automatische e-mail.

### Rechtenbeheer
De toegang voor interne medewerkers wordt geregeld via de volgende permissies (gedefinieerd in `core/views/_helpers.py`):

-   `can_view_av_nazendingen`: Recht om het overzicht te bekijken.
-   `can_upload_nazendingen`: Recht om nazendingen toe te voegen, te wijzigen, te verwijderen en te e-mailen.

### Backend Logica (`core/views/nazendingen.py`)
-   `nazendingen_view`: Beheert de CRUD-acties voor nazendingen en rendert de hoofdpagina.
-   `medications_search_api`: Een AJAX-endpoint die door Select2 wordt gebruikt om in de `VoorraadItem` tabel te zoeken op naam of ZI-nummer.
-   `export_nazendingen_pdf`: Genereert direct een PDF van de huidige lijst voor de ingelogde gebruiker.
-   `email_nazendingen_pdf`: Verwerkt de geselecteerde ontvangers en start de Celery task voor verzending.

## Implementatie Details

### PDF Generatie
De PDF wordt gegenereerd met **WeasyPrint** via de helperfunctie `_render_pdf` in `core/views/_helpers.py`. 

-   **Template**: `core/templates/nazendingen/pdf/nazendingen_lijst.html`.
-   **Styling**: Gebruikt inline CSS in de helperfunctie voor een consistente visuele identiteit (Apotheek Jansen blauw).
-   **Assets**: Afbeeldingen zoals het logo en de handtekening worden via absolute paden geladen met `_static_abs_path`.

### E-mail Workflow (Asynchroon)
Het versturen van e-mails gebeurt op de achtergrond via Celery om de gebruikerservaring niet te vertragen:

1.  **Task Start**: `send_nazendingen_pdf_task` wordt aangeroepen met een lijst van `organization_ids`.
2.  **PDF Creatie**: De task genereert één PDF-bestand met de actuele lijst.
3.  **Opslag**: De PDF wordt tijdelijk opgeslagen in de `tmp/nazendingen/` directory op de `default_storage`.
4.  **Dispatch**: Voor elke organisatie wordt een sub-task (`email_dispatcher_task`) aangemaakt om de e-mail met de PDF-bijlage te versturen.
5.  **Chord**: Er wordt gebruik gemaakt van een Celery `chord`. Zodra alle e-mail tasks zijn voltooid, wordt de `cleanup_storage_file_task` uitgevoerd om het tijdelijke PDF-bestand te verwijderen.

### Frontend Componenten
-   **Select2**: Wordt gebruikt voor zowel het zoeken naar medicijnen (met AJAX-ondersteuning) als het selecteren van meerdere ontvangers in de e-mail modal.
-   **CRUD Interface**: Een tabel met inline bewerkingsmogelijkheden en live zoekfunctionaliteit via JavaScript (`core/static/js/nazendingen/nazendingen.js`).
-   **Responsive Design**: Specifieke CSS (`core/static/css/nazendingen/nazendingen.css`) zorgt voor een bruikbare interface op zowel desktop als mobiele apparaten.

## Belangrijke Bestanden
-   Model: `core/models.py` -> `Nazending`
-   Views: `core/views/nazendingen.py`
-   Forms: `core/forms.py` -> `NazendingForm`
-   Tasks: `core/tasks/emails.py` -> `send_nazendingen_pdf_task`
-   Emails: `core/utils/emails/nazending_mail.py`
-   Template: `core/templates/nazendingen/index.html`
-   PDF Template: `core/templates/nazendingen/pdf/nazendingen_lijst.html`
