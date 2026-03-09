# Techniek & Standaardvragen Beheren

De applicatie maakt gebruik van tekst-parsing, data matching en een data-flow verdeeld over de hoofdapplicatie (Django op EC2) en de analyse-engine (FastAPI op AWS Lambda). Hier volgt een uitleg van het proces.

## De Volledige Analyse-pijplijn

Wanneer een lijst wordt ingevoerd via de Django hoofdapplicatie, stuurt deze een aanvraag naar de FastAPI analyse-engine op AWS Lambda. Dit verloopt in de volgende stappen:

1. __Parser (Rauwe tekst naar Data)__ 
   De FastAPI backend (gehost via Mangum op Lambda) ontvangt de tekst via een `POST` request met de parameters `text`, `source`, en `scope`. Met behulp van reguliere expressies wordt de tekst geparset. Regels die beginnen met `C `, `Z ` of `T ` worden herkend als medicatieregels. De `clean_name` functie verwijdert AIS-tags (zoals `ARBO` of `KK`).

2. __SQLite Matcher (G-Standaard Lookup)__ 
   Elk medicijn wordt opgezocht in de lokale SQLite database (`lookup.db`). Deze database is via een build-script gevuld met data uit de G-Standaard bestanden (zoals `bst020`, `bst711`, etc.) en Jansen Groepen. De database wordt in read-only mode (`?mode=ro`) geopend.
   - Er wordt gezocht naar een exacte match op de geneesmiddelnaam.
   - Indien dit niet lukt, stript de parser stapsgewijs woorden van het einde van de inkomende tekst af (om vervuilende toevoegingen en doseringen te negeren). Bij elke stap wordt opnieuw een exacte match geprobeerd, gevolgd door een prefix scan (via SQL `LIKE`), net zolang tot er een geldig Naamnummer (NMNR) is gevonden.
   - Vanuit het NMNR doorloopt de code 4 mogelijke SQL-routes (bijv. via recept, artikelen, of voorschrijfproduct) om de definitieve SPKode (`spkode`) te bepalen.
   - De SPKode wordt gekoppeld aan de ATC-code. Eventuele voorkeurs-ATC's worden direct toegepast via `ATC_preferent.json`. De Jansen groep (`atc_jansen_mapping`) wordt in deze stap ook direct vanuit de database gekoppeld.

3. __Analyses uitvoeren (Op AWS Lambda)__
   Met de gestructureerde lijst aan medicijnen (inclusief ATC-codes) voert de Lambda-functie vier controles uit:
   - __STOPP-NL v2__: Matcht ATC-codes tegen de configuratie in `stop-v2.json`.
   - __ACB Score__: Berekent de score op ATC7-niveau aan de hand van `acb.json`. Dubbele middelen met dezelfde ATC7-code worden maar één keer geteld (O(1) lookup).
   - __Dubbelmedicatie__: Detecteert of er meerdere, uniek benoemde middelen voorgeschreven zijn binnen exact dezelfde ATC5-code.
   - __Standaardvragen__: Evalueert de patiëntgegevens op basis van de S3-configuratie (`vragen.json`).

4. __NDJSON Streaming__
   Via een Generator (`yield`) streamt de FastAPI applicatie de voortgang en de geanalyseerde data direct in `application/x-ndjson` formaat terug naar de Django applicatie, die het vervolgens doorgeeft aan de browser.

5. __Verrijking: Overrides & Historie (Op EC2)__
   Zodra de data de browser en de Django hoofdapplicatie (RDS) bereikt, wordt dit verrijkt:
   - __Overrides (`MedicatieReviewMedGroupOverride`)__: Haalt eventuele handmatige wijzigingen op (weergavenaam of Jansen Categorie). De originele analyse vanuit Lambda blijft intact.
   - __Historie (`MedicatieReviewComment`)__: Haalt eerdere opmerkingen van de specifieke patiënt op en toont deze in het historie-veld.

6. __Exporteren (Word/PDF)__
   Vanuit de detailpagina worden documenten gegenereerd door de Django applicatie (EC2). Dit levert een Word-document (`.docx`) of PDF op, inclusief handmatige instellingen en opmerkingen.

---

## Standaardvragen Aanpassen (vragen.json)

De configuratie voor standaardvragen staat in een JSON-bestand op een __AWS S3 Bucket__ (`config/vragen.json`). De Lambda-applicatie controleert de 'ETag' van het bestand op S3. Het bestand wordt alleen opnieuw van S3 gedownload en in het werkgeheugen geplaatst indien het is gewijzigd ten opzichte van de cache.

### De opbouw van een JSON-vraag

In het JSON-bestand staat een array genaamd `"criteria"`. Elk object hierin representeert één vraag.

```json
{
  "definition": {
    "id": "VRAAG_MAAG_01",
    "title": "Maagbescherming bij NSAID",
    "category_atc_code": "A",
    "subcategory_atc_code": "A02",
    "description": "Is er gedacht aan maagbescherming bij dit NSAID gebruik?"
  },
  "activation": {
    "primary_triggers": ["M01A", "N02BA"]
  },
  "logic_rules": [
    {
      "type": "ATC",
      "boolean_operator": "AND_NOT",
      "trigger_codes": ["A02BC"]
    },
    {
      "type": "ATC",
      "boolean_operator": "AND",
      "trigger_codes": ["C09"]
    }
  ],
  "filters": {
    "age_min": 70
  }
}
```

### De Interne Boolean Logica

De `check_standaardvragen.py` logica op Lambda evalueert deze regels als volgt:

1. __Leeftijdsfilter (`filters.age_min`)__: 
   Indien de patiënt jonger is dan de opgegeven leeftijd, wordt de vraag overgeslagen.

2. __De Basis-trigger (`activation.primary_triggers`)__: 
   Deze lijst hanteert een __OR (OF)__ logica. Als er minimaal één code matcht met een code (van ATC3 t/m ATC7) uit de medicatielijst van de patiënt, is de trigger geactiveerd.

3. __De Extra Condities (`logic_rules`)__:
   Binnen de `logic_rules` array is elk object (elke regel) een aparte voorwaarde. Alle objecten in de array moeten succesvol zijn gepasseerd (__strikte AND__). Binnen een object (in de `trigger_codes` array) geldt altijd een __OR (OF)__ logica.

   - __`AND` (Extra vereiste)__: 
       - _Inhoud_: `["C09", "C08"]`
       - _Logica_: Wordt middel C09 __OF__ middel C08 gebruikt (naast de trigger)?
       - _Resultaat_: Indien ja, slaagt de conditie. Indien geen van beide middelen aanwezig is, wordt de vraag geannuleerd. _Opmerking: Als in de `AND` regel dezelfde code wordt gebruikt als de `primary_trigger`, dwingt de applicatie af dat er twee unieke (verschillende) middelen met deze ATC-code op de lijst moeten staan._
   - __`AND_NOT` (Uitsluiting)__: 
       - _Inhoud_: `["A02BC", "A02BA"]`
       - _Logica_: Wordt middel A02BC __OF__ middel A02BA gebruikt?
       - _Resultaat_: Indien ja, faalt de conditie direct en wordt de vraag geannuleerd.
