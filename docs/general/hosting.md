# Hosting & Infrastructuur

De Apotheek Jansen App wordt gehost op Amazon Web Services (AWS) en is gebouwd als een Progressive Web App (PWA). Dit betekent dat de applicatie via de browser te installeren is op mobiele apparaten. Dit zorgt voor een app-achtige ervaring, terwijl we gebruik blijven maken van webtechnieken zoals _over the air_ updates zonder afhankelijk te zijn van app stores.

## Tech Stack

De applicatie maakt gebruik van de volgende kerntechnologieën:

**Backend**
De hoofdapplicatie is gebouwd in Python met het Django framework. De analyse-engine voor de medicatiebeoordeling draait als een losse microservice, gebouwd in Python met FastAPI.

**Frontend**
De gebruikersinterface is opgebouwd met klassieke webtechnologieën: HTML, CSS en JavaScript. Hoewel er is gekozen voor een server-rendered structuur met Django templates om de complexiteit laag te houden, is een toekomstige migratie naar moderne frontend frameworks (zoals React) mogelijk om de interactiviteit verder uit te breiden.

**Infrastructuur**
De hosting vindt plaats op AWS, waarbij gebruik wordt gemaakt van EC2, RDS, S3, Lambda en CloudFront om de verschillende onderdelen van het systeem te faciliteren.

## De Hoofdapplicatie (AWS EC2)

De kern van de Django applicatie draait op een AWS EC2-instantie. Op deze server worden de inkomende webrequests afgehandeld en gerouteerd door een Nginx webserver.

Naast de webserver draaien hier ook de Celery workers. Celery wordt gebruikt voor het asynchroon uitvoeren van tijdrovende achtergrondtaken, zodat de gebruiker hier niet op hoeft te wachten. Voorbeelden hiervan zijn het versturen van e-mails en het afleveren van push notificaties.

Tot slot draait op deze server Redis. Redis fungeert als message broker voor Celery en wordt ingezet voor snelle in-memory caching. Het beheert actieve gebruikerssessies en cachet veelgevraagde data, zoals de `.ics` kalenderbestanden in de Agenda feature, om de laadtijden aanzienlijk te verkorten.

## Gegevensopslag

Voor de opslag van data maken we gebruik van beheerde AWS services. Zowel de database als de opslag zijn via AWS beveiligingsbeleid (IAM en Security Groups) afgeschermd, zodat deze uitsluitend toegankelijk zijn voor de applicatieserver (EC2) en niet direct benaderbaar zijn vanaf het internet.

**Relationele Database (AWS RDS)**
Alle gestructureerde applicatiedata, zoals roosters, instellingen en gebruikersprofielen, wordt opgeslagen in een PostgreSQL database gehost via AWS RDS. Dit zorgt voor automatische back-ups, data-integriteit, hoge beschikbaarheid en een uiterst veilige opslag.

**Bestandsopslag (AWS S3)**
Statische mediabestanden en geüploade documenten, zoals profielfoto's, configuratiebestanden voor de medicatiebeoordeling en afbeeldingen bij nieuwsberichten, worden veilig opgeslagen in Amazon S3 buckets.

## Content Delivery

Om de laadtijd voor gebruikers te minimaliseren, is AWS CloudFront ingericht als Content Delivery Network (CDN). CloudFront distribueert de statische assets (zoals de opgeslagen afbeeldingen uit S3, stylesheets en scripts) zeer efficiënt, ongeacht waar de gebruiker zich bevindt.

## Medicatiebeoordeling (AWS Lambda)

De module voor de medicatiebeoordeling vereist kortstondig veel rekenkracht door de complexe tekst-parsing. Om te voorkomen dat de hoofdapplicatie hierdoor vertraagt, draait deze engine serverless op AWS Lambda.

Wanneer een gebruiker een analyse start, verstuurt de EC2-instantie de data naar de Lambda-functie. De functie laadt de data, voert de logica uit via een lokale SQLite lookup database en streamt de resultaten direct terug. Zodra de berekening klaar is, stopt de functie automatisch, wat zorgt voor een efficiënte en schaalbare architectuur.
