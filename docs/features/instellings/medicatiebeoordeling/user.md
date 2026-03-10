# Medicatiebeoordeling (Gebruiker)

De module voor medicatiebeoordelingen in de Apotheek Jansen App controleert medicatielijsten uit externe systemen op basis van ingestelde standaardvragen en landelijke richtlijnen. De app toont direct relevante aandachtspunten voor de patiënt.

!!! info "Privacy & Beveiliging"
    Namen en geboortedatums van patiënten worden versleuteld opgeslagen. Het overzicht is IP-afgeschermd: resultaten zijn uitsluitend in te zien via het interne netwerk van de apotheek. Alleen apothekers en beheerders hebben toegang tot de medicatiebeoordelingen.

---

## 1. Een analyse starten

Volg deze stappen om een lijst te controleren:

1.  **Selecteer de instellingen**: 

    - Kies het bronsysteem (momenteel alleen Medimo). Ondersteuning voor Pharmacom-exports is in ontwikkeling.
    - Kies de scope: een afdelingslijst (meerdere patiënten) of een individuele patiënt.

2.  **Kopieer de tekst uit het AIS**:

    - Volg de aanwijzingen in de app voor het kopiëren van de gegevens.

3.  **Plakken en Analyseren**: 

    - Plak de tekst in het invoerveld.
    - Vul bij individuele patiënten de naam en geboortedatum in zoals ze in Medimo staan.
    - Klik op 'Analyseer'.

---

## 2. Resultaten en Controles

De resultaten verschijnen per patiënt op het scherm. De Apo Jansen App voert automatisch de volgende controles uit:

- **STOP-NL V2**: Signaleert medicatie die volgens de richtlijn mogelijk gestopt of gewijzigd dient te worden (zie: [NHG STOP-NL V2](https://www.nhg.org/thema/farmacotherapie/stop-nl-v2/)).
- **Anticholinerge Belasting (ACB)**: Berekent de ACB-score op basis van de [Ephor lijst](https://ephor.nl/wp-content/uploads/2018/12/anticholinergic-drugs.pdf). Bij een score van 3 of hoger wordt een waarschuwing getoond.
- **Dubbelmedicatie**: Controleert op meerdere voorschriften binnen dezelfde werkzame stof-groep.
- **Standaardvragen**: Toont apotheek-specifieke vragen als aandachtspunt of agendapunt.

---

## 3. Medicatie Aanpassen & Bevindingen Noteren

### Handmatige aanpassingen
Indien een medicijnnaam niet correct wordt herkend of in een verkeerde categorie (Jansen Groep) is geplaatst, kun je dit aanpassen:

1. Klik bij een medicijn op het bewerk-icoon.
2. Wijzig de categorie via de dropdown.
3. Klik op opslaan om de wijziging direct door te voeren in de analyse en exports.

### Bevindingen en Historie vastleggen
Gebruik de tekstvakken voor klinische opmerkingen. Deze notities worden opgeslagen. Bij een volgende beoordeling van dezelfde patiënt zie je eerdere opmerkingen terug onder het veld **Historie** van die Jansen categorie.

---

## 4. Resultaten Exporteren

Het overzicht kan worden geëxporteerd voor overleg met de arts:

- **Word-document (.docx)**: Voor handmatige aanpassingen in het definitieve document.
- **PDF-document**: Voor een onwijzigbaar verslag.

Alle aanpassingen en opmerkingen die in de app zijn ingevoerd, worden automatisch meegenomen in de export.

!!! warning "Documentatie in de app"
    Hoewel het mogelijk is om handmatige aanpassingen te doen in een geëxporteerd Word-document, worden deze wijzigingen **niet** teruggestuurd naar de Apo Jansen App. Dit betekent dat dergelijke aantekeningen niet zichtbaar zijn in de **Historie** bij een volgende beoordeling van de patiënt. 

    Het is daarom aanbevolen om alle bevindingen en opmerkingen direct in de app te documenteren. Zo hoeft u bij toekomstige controles niet in oude documenten te zoeken naar eerdere besluitvorming.


---

## 5. Zelf de Standaardvragen Aanpassen

De 'Standaardvragen' zijn te beheren via het menu (**Medicatiebeoordeling -> Instellingen**). Voor de configuratie worden altijd ATC-codes gebruikt. Je kunt in de app de naam van een geneesmiddel typen om de juiste ATC-code te vinden.

### Logica van de regels

Hieronder volgt een gedetailleerde uitleg over hoe de regels ("Triggers", "AND" en "AND_NOT") samenwerken.

**A. De Trigger (Wanneer wordt de vraag overwogen?)**
Elke vraag heeft een basisvoorwaarde (Primary Trigger) nodig.

- **Eén of meer codes (OF-voorwaarde)**: De vraag verschijnt als de patiënt minimaal één van de opgegeven codes gebruikt.
    - *Voorbeeld*: Je vult `N05A (Antipsychotica)` en `N05B (Anxiolytica)` in. Gebruikt de patiënt Haloperidol **OF** Oxazepam? Dan verschijnt de vraag.

**B. Extra Voorwaarde / "AND" (Wat moet er nog meer aanwezig zijn?)**
Met de "AND" regel voeg je een extra vereiste toe. Deze regel slaagt alleen als er een **ander, uniek medicijn** op de lijst staat dat aan de voorwaarde voldoet.

- **Meerdere codes binnen één regel (OF-voorwaarde)**: De patiënt moet naast de hoofdtrigger minimaal één van deze andere middelen gebruiken.
    - *Voorbeeld*: Trigger = `C03C (Lisdiuretica, bijv. Furosemide)`. Je voegt één AND-regel toe met `C07 (Bètablokkers)` en `C09 (RAS-remmers)`. De vraag verschijnt alleen als de patiënt Furosemide gebruikt **EN** daarnaast nog een ander medicijn heeft uit de groep bètablokkers **OF** RAS-remmers.
- **Meerdere aparte AND-regels (EN-voorwaarde)**: De patiënt moet aan alle regels tegelijk voldoen met steeds verschillende medicijnen.
    - *Voorbeeld*: Trigger = `C03C (Lisdiuretica)`. Je maakt regel 1 met `C07 (Bètablokkers)` en regel 2 met `C09 (RAS-remmers)`. De vraag verschijnt nu alleen als de patiënt middelen uit **alle drie** de groepen tegelijk op zijn lijst heeft staan.

**C. Uitsluiting / "AND_NOT" (Wanneer moet de vraag verborgen worden?)**
De "AND_NOT" regel werkt als een uitsluiting. Zodra een patiënt een medicijn gebruikt dat in deze lijst staat, wordt de vraag niet weergegeven.

- **Codes binnen de regel (OF-voorwaarde)**: Als er ook maar één middel uit deze lijst aanwezig is, verdwijnt de vraag.
    - *Voorbeeld (Maagbescherming bij NSAID)*: Trigger = `M01A (NSAID's)`. Je voegt één AND_NOT regel toe met `A02BC (Protonpompremmers)` en `A02BA (H2-antagonisten)`. Gebruikt de patiënt Omeprazol **OF** Famotidine? Dan is de maag al beschermd en wordt de vraag verborgen.
- **Meerdere aparte AND_NOT-regels**: Elke regel kan de vraag onafhankelijk blokkeren.
    - *Voorbeeld*: Trigger = `C03C (Lisdiuretica)`. Regel 1 (AND_NOT) bevat `A12BA (Kaliumsupplementen)` en Regel 2 (AND_NOT) bevat `C03D (Kaliumsparende diuretica)`. Gebruikt de patiënt kalium supplementen? Vraag verborgen. Gebruikt de patiënt Spironolacton? Vraag ook verborgen.
