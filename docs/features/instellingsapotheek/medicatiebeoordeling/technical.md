# Medicatiebeoordeling (Technisch)

De module voor medicatiebeoordelingen in de Apotheek Jansen App is opgedeeld in twee hoofdonderdelen: een Django-gebaseerde beheerlaag op AWS EC2 en een analyse-engine op AWS Lambda. Dit document beschrijft de technische architectuur, de dataflow en de implementatiedetails van beide componenten.

## Technisch ontwerp

De architectuur volgt een microservices-patroon waarbij de zware reken- en parsingtaken zijn uitbesteed aan een serverless AWS Lambda functie.

- **Frontend & Beheer (Django/EC2)**: Verwerkt de gebruikersinterface, slaat patiëntgegevens op en beheert de handmatige overrides en comments.
- **Analyse-engine (FastAPI/Lambda)**: Een stateless microservice die ruwe AIS-tekst (Medimo of Pharmacom) transformeert naar gestructureerde klinische inzichten.
- **Communicatie**: De Django-applicatie roept de Lambda aan via een POST-request en ontvangt de resultaten als een NDJSON-stream (Newline Delimited JSON) voor real-time voortgangsweergave.

### Workflow
1.  **Invoer**: De gebruiker kopieert tekst uit het AIS naar de Django-app.
2.  **Request**: Django stuurt de tekst naar de Lambda microservice.
3.  **Parsing & Matching**: De Lambda identificeert patiënten en koppelt medicatie aan de G-Standaard via een lokale SQLite-database (`lookup.db`).
4.  **Klinische Analyse**: De engine voert parallelle controles uit (STOPP, ACB, dubbelmedicatie, standaardvragen).
5.  **Response**: De resultaten worden als JSON teruggestuurd naar Django.
6.  **Opslag & Verrijking**: Django slaat de resultaten op in `MedicatieReviewPatient` en synchroniseert gevonden vragen naar `MedicatieReviewComment`.

## Datamodel

### Django (Hoofdapplicatie)
- **`MedicatieReviewAfdeling`**: Beheert de koppeling tussen organisaties, locaties en afdelingsnamen.
- **`MedicatieReviewPatient`**: Slaat per patiënt de ruwe analyse-data op in een `JSONField` (`analysis_data`). Persoonsgegevens zoals naam en geboortedatum zijn versleuteld (`EncryptedCharField`).
- **`MedicatieReviewComment`**: Bevat de farmaceutische anamnese en actiepunten per Jansen-groep. De tekst is versleuteld en ondersteunt automatische synchronisatie van standaardvragen.
- **`MedicatieReviewMedGroupOverride`**: Slaat handmatige wijzigingen op in de groepering of naamgeving van specifieke geneesmiddelen voor een patiënt.

### Lambda (Analyse-engine)
De Lambda maakt gebruik van een SQLite database (`lookup.db`) die wordt opgebouwd uit G-Standaard bestanden:

- **`bst020_namen`**: Voor het matchen van productnamen naar Naamnummers (NMNR).
- **`bst711_generiek`**: Voor het koppelen van NMNR aan ATC-codes en SPKodes.
- **`atc_jansen_mapping`**: Voor het indelen van ATC-codes in de specifieke Jansen-groepen.
- **`bst801_atc_teksten`**: Voor de tekstuele omschrijvingen van ATC-codes op verschillende niveaus (ATC3 t/m ATC7).

## Implementatiedetails

### Tekst-parsing (Medimo)
De parser identificeert patiënten door te zoeken naar headers als `Dhr.` of `Mevr.`. Medicatieregels worden herkend aan de prefixen `C` (Continu), `Z` (Zo nodig) of `T` (Tijdelijk).

- **Schoonmaken**: AIS-specifieke codes zoals `ARBO`, `KK` of `OW` worden gestript om de matching-kans in de G-Standaard te vergroten.
- **Doseringsextractie**: Met regex-patronen worden doseringsschema's (bijv. `1 - 1 - 1 - 1`) gescheiden van de eenheid en eventuele opmerkingen.

### G-Standaard Matching
De engine gebruikt vier 'routes' om een medicijnnaam te koppelen aan een ATC-code:

1.  **Direct**: Match op basis van Generiek Product Stamnummer (GPSTNR).
2.  **Recept**: Koppeling via Receptnaamnummer (PRNMNR).
3.  **Artikel**: Koppeling via Artikelnaamnummer (ATNMNR) en Handelsproduct (HPKODE).
4.  **Voorschrijfproduct**: Koppeling via Voorschrijfproduct (HPNAMN).

### Klinische Analyse Modules
- **STOPP-NL v2**: Evalueert de medicatielijst tegen de criteria in `stop-v2.json`.
- **Anticholinerge Score (ACB)**: Berekent een cumulatieve score op basis van `acb.json`. Scores worden gerapporteerd als lichte, matige of hoge belasting.
- **Dubbelmedicatie**: Detecteert wanneer een patiënt meerdere middelen gebruikt met dezelfde ATC5-code.
- **Standaardvragen**: Een dynamisch systeem dat criteria ophaalt uit een S3-bucket (`vragen.json`). Het systeem ondersteunt complexe logica met `AND` en `AND_NOT` operatoren om relevante farmaceutische vragen te genereren.

## Autorisatie en beveiliging

- **API-beveiliging**: De communicatie tussen Django en Lambda is beveiligd met een gedeelde API-key (`X-API-Key` header).
- **Data Encryptie**: In de Django-database worden alle herleidbare patiëntgegevens en vrije tekstvelden versleuteld opgeslagen met `django-cryptography`.
- **Database Toegang**: De SQLite database in de Lambda-omgeving is read-only geopend via URI mode (`mode=ro`) voor maximale veiligheid en snelheid.

## Relevante bestanden

### Hoofdapplicatie (Django)
- `core/models.py`: Definieert de `MedicatieReview` modellen.
- `core/services/medicatiereview_api.py`: Beheert de communicatie met de Lambda en de synchronisatie van resultaten.
- `core/views/medicatiebeoordeling.py`: Bevat de logica voor het verwerken van de UI-requests.

### Microservice (Lambda)
- `app/main.py`: De FastAPI entrypoint en Mangum handler.
- `core/services.py`: De orchestrator van de analyse-engine.
- `core/parsers/parse_medimo_afdeling.py`: De Medimo tekst-parser.
- `core/analyses/standaardvragen/check_standaardvragen.py`: De logica voor de klinische standaardvragen.
- `scripts/build_db.py`: Script voor het genereren van de `lookup.db`.
