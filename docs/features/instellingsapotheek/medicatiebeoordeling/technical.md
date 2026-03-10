# Medicatiebeoordeling (Technisch)

De module voor medicatiebeoordelingen in de Apotheek Jansen App is opgebouwd als een losse microservice (FastAPI op AWS Lambda) die samenwerkt met de hoofdapplicatie (Django op AWS EC2). Dit document beschrijft de dataflow en technische opzet van deze analyse-engine.

!!! warning "In ontwikkeling"
    De documentatie van de techbische medicatiebeoordeling is nog in ontwikkeling en is dus nog niet volledig
## Architectuur en Dataflow

Wanneer een gebruiker een analyse start, doorloopt het systeem de volgende stappen:

### 1. Tekst-parsing
De hoofdapplicatie verstuurt de ruwe invoertekst naar de analyse-engine. 
- **Parser**: Met reguliere expressies worden medicatieregels herkend (regels die beginnen met `C`, `Z` of `T`).
- **Cleaning**: AIS-specifieke codes zoals `ARBO` of `KK` worden uit de namen verwijderd voor een zuivere match.

### 2. G-Standaard Matching (SQLite)
De analyse-engine maakt gebruik van een lokale SQLite database (`lookup.db`) gevuld met G-Standaard gegevens. 
- Het systeem zoekt via een exacte match of via een prefix-scan door de productnaam stapsgewijs in te korten. 
- Na identificatie van een Naamnummer (NMNR) wordt de bijbehorende ATC-code opgehaald en worden direct de juiste Jansen Groepen gekoppeld.

### 3. Klinische Analyses
Met de gevonden ATC-codes voert de engine vier parallelle controles uit:
- **STOPP-NL v2**: Matching op basis van `stop-v2.json`.
- **ACB Score**: Berekening op ATC7-niveau via `acb.json`.
- **Dubbelmedicatie**: Detectie van meerdere middelen binnen dezelfde ATC5-code.
- **Standaardvragen**: Evaluatie van lokale criteria die zijn vastgelegd in `vragen.json`.

### 4. Resultaten en Verrijking
De resultaten worden via een NDJSON-stream teruggestuurd naar de Django-applicatie. Daar vindt de laatste verrijking plaats:
- **Overrides**: Handmatige aanpassingen uit de database worden toegepast op de resultaten.
- **Historie**: Eerdere klinische notities van de specifieke patiënt worden opgehaald uit de database.

## Configuratie Standaardvragen (`vragen.json`)

De criteria voor de standaardvragen staan in een JSON-bestand op een AWS S3 bucket. De engine controleert bij elke aanvraag de ETag van het bestand en cachet de data in het geheugen.

### Logica-evaluatie (check_standaardvragen.py)

De evaluatie van een criterium volgt een strikte boolean-logica:

1.  **Primary Triggers**: Minimaal één code uit de `primary_triggers` lijst moet aanwezig zijn in de medicatielijst van de patiënt.
2.  **Logic Rules**: Elke regel in de `logic_rules` array wordt geëvalueerd. Alle regels moeten slagen (strikt EN-verband tussen de regels).
    -   **Operator AND**: Vereist dat de patiënt minimaal één middel uit de `trigger_codes` lijst gebruikt. Dit moet een **ander** product zijn dan het product dat de `primary_trigger` heeft geactiveerd (`rule_meds - primary_meds`). Dit voorkomt dat één enkel medicijn aan beide voorwaarden voldoet.
    -   **Operator AND_NOT**: Werkt als een veto. Indien de patiënt een middel gebruikt dat matcht met een code uit de `trigger_codes` lijst, wordt de gehele vraag direct geblokkeerd.
3.  **Filters**: Aanvullende voorwaarden zoals een minimale leeftijd (`age_min`) worden gecontroleerd voordat de triggers worden geëvalueerd.
