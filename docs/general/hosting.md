# Hosting & Infrastructuur

De Apotheek Jansen App wordt gehost op Amazon Web Services (AWS) en is ontworpen om medische en bedrijfsgegevens veilig en betrouwbaar te verwerken.

## Technologie

De app is opgebouwd als een **Progressive Web App (PWA)**. Gebruikers kunnen de app direct via de browser op hun telefoon of computer installeren voor een app-achtige ervaring.

- **Backend**: Python (Django framework) voor de hoofdapplicatie en FastAPI voor de microservices.
- **Frontend**: HTML, CSS en JavaScript met een server-rendered opzet voor eenvoud, snelheid en role-based access control.

## Infrastructuur

### Applicatieserver (AWS EC2)
De kern van de Django-applicatie draait op een AWS EC2-instantie. Hierop worden webrequests afgehandeld door een Nginx webserver. Op deze server draaien ook:

- **Celery Workers**: Voor asynchrone taken, zoals het versturen van e-mails en pushnotificaties.
- **Redis**: Voor in-memory caching van veelgevraagde gegevens (bijvoorbeeld agenda-bestanden).

### Gegevensopslag (AWS RDS & S3)
De data in de Apotheek Jansen App is strikt afgeschermd. De enige entiteit die toegang heeft tot de databases en opslagbuckets is de EC2-applicatieserver. Dit betekent dat de data uitsluitend toegankelijk is via de app zelf of door personen die direct kunnen inloggen op de EC2-server via een beveiligde verbinding.

- **Relationele Database (AWS RDS)**: Alle applicatiegegevens, zoals roosters en gebruikersprofielen, worden bewaard in een PostgreSQL database met automatische back-ups.
- **Bestandsopslag (AWS S3)**: Statische bestanden, zoals profielfoto's en de configuratie voor de medicatiebeoordeling, worden veilig in S3 buckets opgeslagen.

### Content Delivery (AWS CloudFront)
CloudFront fungeert als CDN om statische assets (stylesheets, scripts, afbeeldingen) efficiënt aan gebruikers te leveren, waardoor de app sneller laadt.

### Medicatieanalyse (AWS Lambda)
De analyse-engine voor de medicatiebeoordeling draait op AWS Lambda. Door deze engine als losse microservice op Lambda te draaien, beïnvloedt de rekenkracht van analyses de snelheid van de rest van de app niet.