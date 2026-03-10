# ApoGPT (Technisch)

## Technisch ontwerp
De ApoGPT module is een AI-gestuurd zoeksysteem dat gebruik maakt van Large Language Models (LLM) in combinatie met een gespecialiseerde dataset. Het systeem past Retrieval-Augmented Generation (RAG) toe om antwoorden te genereren die uitsluitend gebaseerd zijn op geautoriseerde bronnen van de Apotheek Jansen App.

## Datamodel
De belangrijkste componenten van de module zijn:

- **Google Gemini API**: Voor het genereren van antwoorden via het model `gemini-2.5-flash`.
- **Gemini File Search (Grounding)**: Een vectorstore waarin gescrapte pagina's van FK en NHG zijn opgeslagen.
- **`ScrapedPage` model**: In de database van de Apotheek Jansen App worden metadata van de gescrapte bronnen (titel, URL, categorie) bijgehouden om de correcte bronvermeldingen te tonen.

## Implementatiedetails
- **API integratie**: De module communiceert met de Google GenAI SDK.
- **Prompt engineering**: De systeeminstellingen dwingen de assistent om alleen informatie uit de meegeleverde bronnen te gebruiken en in Markdown te antwoorden.
- **Sessiebeheer**: De chatgeschiedenis wordt bijgehouden in de Django-sessie van de gebruiker (`kompasgpt_history`), beperkt tot de laatste 8 berichten om context-overflow te voorkomen.
- **Bronvermelding**: De module extraheert titels uit de grounding metadata van de Gemini-respons en matcht deze met het `ScrapedPage` model om de oorspronkelijke URL van de bron te presenteren.
- **Foutafhandeling**: Een retry-mechanisme (`_generate_with_retry`) vangt tijdelijke API-fouten (zoals HTTP 429 of 503) op.

## Autorisatie en beveiliging
- **Permissies**: Toegang wordt gereguleerd via de permissie `can_view_kompasgpt`.
- **API Keys**: Gevoelige gegevens zoals `GOOGLE_API_KEY` en `GEMINI_STORE_ID` worden via omgevingsvariabelen geconfigureerd.

## Relevante bestanden
- `core/views/kompasgpt.py`: Bevat de logica voor de integratie met de Gemini API en de view-functies.
- `core/models.py`: Bevat het `ScrapedPage` model.
- `core/static/js/kompasgpt/kompasgpt.js`: Client-side logica voor de chatinterface.
- `core/templates/kompasgpt/index.html`: Sjabloon voor de chatinterface.
