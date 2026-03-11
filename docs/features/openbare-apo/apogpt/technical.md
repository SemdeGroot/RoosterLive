# ApoGPT (Technisch)

## Technisch ontwerp
De ApoGPT module is een AI-gestuurd zoeksysteem dat gebruik maakt van Large Language Models (LLM) in combinatie met een specifieke dataset. Het systeem past Retrieval-Augmented Generation (RAG) toe om antwoorden te genereren die uitsluitend gebaseerd zijn op ingeladen bronnen.

De architectuur bestaat uit drie lagen:

1. **Scraper-laag**: Periodieke taken die bronnen (FK en NHG) ophalen en converteren naar Markdown.
2. **Kennis-laag**: Opslag van metadata in de database (`ScrapedPage`) en document-inhoud in de Gemini File Search Store (vectorstore).
3. **Conversatie-laag**: Een chatinterface die vragen beantwoordt op basis van de vectorstore met directe bronvermeldingen.

## Datamodel
### ScrapedPage model
Het model `ScrapedPage` in `core/models.py` houdt metadata bij van elke gescrapte bron:

- **url**: De unieke URL van de originele bron.
- **title**: De titel van de pagina (zoals gebruikt voor matching in de vectorstore).
- **category**: De classificatie van de bron (`preparaat`, `groep`, `indicatie`, `nhg_standaard` of `nhg_behandelrichtlijn`).
- **content_hash**: SHA-256 hash van de Markdown-inhoud om onnodige updates te voorkomen.
- **last_scraped**: Tijdstip van de laatste succesvolle verwerking.

### Gemini File Search
De inhoud van de bronnen wordt geüpload naar een Gemini File Search Store (`GEMINI_STORE_ID`). Dit stelt het model in staat om relevante passages te vinden (grounding) voordat een antwoord wordt gegenereerd.

## Implementatiedetails

### Scraper Logica (Farmacotherapeutisch Kompas)
De `KompasScraper` in `core/utils/kompasscraper/scraper.py` verwerkt het Farmacotherapeutisch Kompas:

- **Discovery**: Navigeert door alfabetische lijsten van preparaatteksten, groepsteksten en indicatieteksten.
- **Injected Content**: Veel FK-pagina's bevatten dynamische elementen (bijv. "Laden..."). De scraper herkent `pat-inject` links en haalt deze sub-pagina's recursief op om een compleet Markdown-bestand te vormen.
- **ATC-extractie**: Tijdens de extractie worden ATC-codes geïdentificeerd en als metadata meegegeven aan de vectorstore voor verbeterde zoekresultaten.
- **Markdown conversie**: HTML-structuren (tabellen, lijsten, headers) worden omgezet naar GitHub-flavored Markdown.

### Scraper Logica (NHG)
De `NHGScraper` in `core/utils/nhgscraper/scraper.py` verwerkt de richtlijnen van het Nederlands Huisartsen Genootschap:

- **Discovery**: Gebruikt primair de `sitemap.xml` van de NHG-richtlijnen website voor een volledige inventarisatie van standaarden en behandelrichtlijnen.
- **Metadata**: Extraheert specifieke metadata zoals KNR-codes, publicatiedatum en de betrokken NHG-werkgroep.
- **Structuur**: Verwerkt complexe collapsible secties en "Aanbevelingen" binnen de richtlijnen om de hiërarchie in Markdown te behouden.

### Verwerkingstaken (Celery)
Periodieke taken (`tasks.run_nhg_scraper` en vergelijkbare taken voor FK) regelen de synchronisatie:

1. **Discovery fase**: Identificeer alle relevante URLs.
2. **Vergelijkingsfase**: Controleer via de `content_hash` of de pagina gewijzigd is sinds de laatste run.
3. **Upload fase**: Bij wijzigingen wordt de nieuwe Markdown-inhoud naar de Gemini vectorstore geüpload en de metadata in `ScrapedPage` bijgewerkt.

### API Integratie en RAG
- **Grounding**: De view `kompasgpt` gebruikt de `google-genai` SDK met de `file_search` tool geactiveerd.
- **Bronvermelding**: Gemini retourneert grounding chunks met titels. De backend matcht deze titels met het `ScrapedPage` model om de oorspronkelijke bron-URL's aan de gebruiker te tonen.
- **Retry mechanisme**: Vanwege rate-limits en mogelijke tijdelijke onbeschikbaarheid van de API is een exponentieel backoff-mechanisme geïmplementeerd voor zowel scraping als chatsessies.

## Autorisatie en beveiliging
- **Toegang**: Gebruikers moeten beschikken over de permissie `can_view_kompasgpt`.
- **Configuratie**: Alle API-gegevens (`GOOGLE_API_KEY`, `GEMINI_STORE_ID`) zijn strikt gescheiden van de code en worden ingeladen via omgevingsvariabelen.

## Relevante bestanden
- `core/views/kompasgpt.py`: Integratielogica met Gemini.
- `core/utils/kompasscraper/scraper.py`: Logica voor het FK-scrapen.
- `core/utils/nhgscraper/scraper.py`: Logica voor het NHG-scrapen.
- `core/tasks/beat/nhg_scraper.py`: Celery taak voor NHG synchronisatie.
- `core/models.py`: Definitie van `ScrapedPage`.
