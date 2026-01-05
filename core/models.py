from django.db import models
from django.contrib.auth.models import Group
from django.conf import settings
from django.utils import timezone
from fernet_fields import EncryptedCharField, EncryptedDateField, EncryptedTextField
import json
from django.core.validators import MinValueValidator
import uuid

class Roster(models.Model):
    file = models.FileField(upload_to="rooster/current.pdf", null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Lijst met relatieve paden naar gerenderde PNG-pagina’s in MEDIA_ROOT
    pages = models.JSONField(default=list, blank=True)

    class Meta:
        permissions = [
            ("can_access_admin",          "Mag beheer openen"),
            ("can_access_profiel",          "Mag profiel aanpassen"),("can_manage_users",          "Mag gebruikers beheren"),
            ("can_manage_groups",              "Mag groepen beheren"),
            ("can_manage_afdelingen",              "Mag afdelingen beheren"),
            ("can_manage_orgs",              "Mag organisaties beheren"),
            ("can_manage_tasks",              "Mag taken beheren"),
            ("can_view_agenda",           "Mag agenda bekijken"),
            ("can_upload_agenda",         "Mag agenda uploaden"),
            ("can_view_roster",           "Mag rooster bekijken"),
            ("can_upload_roster",         "Mag roosters uploaden"),
            ("can_access_availability",   "Mag Beschikbaarheid openen"),
            ("can_view_av_medications",   "Mag subtab Geneesmiddelen zien"),
            ("can_upload_voorraad",       "Mag Voorraad uploaden"),   
            ("can_view_av_nazendingen",   "Mag subtab Nazendingen zien"),
            ("can_upload_nazendingen",    "Mag Nazendingen uploaden"), 
            ("can_view_news",             "Mag Nieuws bekijken"),
            ("can_upload_news",           "Mag Nieuws uploaden"),   
            ("can_view_policies",         "Mag Werkafspraken bekijken"),
            ("can_upload_werkafspraken",  "Mag Werkafspraken uploaden"),
            ("can_send_beschikbaarheid",  "Mag Beschikbaarheid doorgeven"),
            ("can_view_beschikbaarheidsdashboard", "Mag Beschikbaarheid Personeel bekijken"),
            ("can_edit_beschikbaarheidsdashboard", "Mag diensten toewijzen"),
            ("can_view_medicatiebeoordeling",           "Mag Medicatiebeoordeling bekijken"),
            ("can_perform_medicatiebeoordeling",         "Mag Medicatiebeoordeling uitvoeren"),
            # Onboarding
            ("can_view_onboarding",     "Mag Onboarding openen"),
            # Personeel
            ("can_view_personeel",      "Mag Personeel openen"),
            # Diensten
            ("can_view_diensten",       "Mag Diensten bekijken"),
            # Uren doorgeven
            ("can_view_urendoorgeven",       "Mag uren doorgeven bekijken"),
            # Ziek melden
            ("can_view_ziekmelden",       "Mag Ziek Melden bekijken"),
            ("can_edit_ziekmelden",       "Mag personeel ziek melden"),
            # Inschrijven
            ("can_view_inschrijven",       "Mag zich inschrijven"),
            ("can_edit_inschrijven",       "Mag inschrijving formulieren aanpassen"),
            # Wie is wie?
            ("can_view_whoiswho",       "Mag Wie is wie? bekijken"),
            ("can_edit_whoiswho",       "Mag Wie is wie? aanpassen"),
            # Onboarding formulieren
            ("can_view_forms",            "Mag formulieren bekijken"),
            ("can_edit_forms",            "Mag formulieren aanpassen"),
            # Checklist
            ("can_view_checklist",        "Mag checklist bekijken"),
            ("can_edit_checklist",        "Mag checklist aanpassen"),
                        # Baxter hoofdpagina
            ("can_view_baxter",                 "Mag Baxter openen"),
            # Baxter subpagina’s – Omzettingslijst
            ("can_view_baxter_omzettingslijst", "Mag Baxter-omzettingslijst bekijken"),
            ("can_edit_baxter_omzettingslijst", "Mag Baxter-omzettingslijst aanpassen"),
            # Geen levering
            ("can_view_baxter_no_delivery",     "Mag 'Geen levering' bekijken"),
            ("can_edit_baxter_no_delivery",     "Mag 'Geen levering' aanpassen"),
            # STS halfjes
            ("can_view_baxter_sts_halfjes",     "Mag STS-halfjes bekijken"),
            ("can_edit_baxter_sts_halfjes",     "Mag STS-halfjes aanpassen"),
            # Laatste potten
            ("can_view_baxter_laatste_potten",  "Mag laatste potten bekijken"),
            ("can_edit_baxter_laatste_potten",  "Mag laatste potten aanpassen"),
            ("can_perform_bestellingen",  "Krijgt een melding bij aanpassing laatste potten"),
            # Apotheek tiles
            ("can_view_openbare_apo",    "Mag Openbare apotheek-tegel zien"),
            ("can_view_instellings_apo", "Mag Instellingsapotheek-tegel zien"),
            # Reviewplanner
            ("can_view_reviewplanner", "Mag Review Planner bekijken"),
            ("can_edit_reviewplanner", "Mag Review Planner bewerken"),
            # Portavita Check
            ("can_view_portavita", "Mag Portavita Check bekijken"),
            ("can_edit_portavita", "Mag Portavita Check bewerken"),

        ]
    def __str__(self):
        return f"Rooster ({self.uploaded_at:%Y-%m-%d %H})"
    
class StandaardInlog(models.Model):
    """
    Singleton model om te bepalen welke rol (Group) wordt gebruikt 
    voor de algemene kiosk/baxter inlog.
    """
    standaard_rol = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="standaard_inlog_config",
        verbose_name="Standaard Rol"
    )

    def save(self, *args, **kwargs):
        self.pk = 1  # Zorgt dat er altijd maar 1 configuratie is
        super(StandaardInlog, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Haalt de instellingen op, of maakt ze aan als ze nog niet bestaan."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configuratie Standaard Inlog"

class Availability(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="availabilities")
    date = models.DateField(db_index=True)
    morning = models.BooleanField(default=False)
    afternoon = models.BooleanField(default=False)
    evening = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.user} @ {self.date} (o:{self.morning} m:{self.afternoon} a:{self.evening})"
    
class Location(models.Model):
    COLOR_CHOICES = [
        ("green", "Groen"),
        ("red", "Rood"),
        ("blue", "Blauw"),
    ]

    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255, blank=True, default="")
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default="blue")

    class Meta:
        verbose_name_plural = "Locations"

    def __str__(self):
        return self.name


class Task(models.Model):
    name = models.CharField(max_length=100)
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="tasks"
    )
    description = models.TextField(blank=True, null=True)

    # ===== Minimale bezetting (ma t/m za) =====
    min_mon_morning = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_mon_afternoon = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_mon_evening = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    min_tue_morning = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_tue_afternoon = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_tue_evening = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    min_wed_morning = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_wed_afternoon = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_wed_evening = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    min_thu_morning = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_thu_afternoon = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_thu_evening = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    min_fri_morning = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_fri_afternoon = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_fri_evening = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    min_sat_morning = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_sat_afternoon = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    min_sat_evening = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name_plural = "Tasks"

    def __str__(self):
        return f"{self.name} ({self.location.name})"


class Shift(models.Model):
    PERIOD_CHOICES = [
        ('morning', 'Ochtend'),
        ('afternoon', 'Middag'),
        ('evening', 'Avond'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shifts"
    )
    task = models.ForeignKey(
        "Task",
        on_delete=models.PROTECT,
        related_name="shifts"
    )
    date = models.DateField(db_index=True)
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date", "period")
        ordering = ["date", "period"]

    def __str__(self):
        return f"{self.date} - {self.user} - {self.get_period_display()} ({self.task})"
    
class ShiftDraft(models.Model):
    ACTION_CHOICES = [
        ("upsert", "Upsert"),
        ("delete", "Delete"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shift_drafts")
    date = models.DateField(db_index=True)
    period = models.CharField(max_length=10, choices=Shift.PERIOD_CHOICES, db_index=True)

    # bij action="delete" is task leeg
    task = models.ForeignKey("Task", on_delete=models.PROTECT, null=True, blank=True, related_name="shift_drafts")

    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date", "period")
        ordering = ["date", "period"]

    def __str__(self):
        return f"[DRAFT {self.action}] {self.date} {self.user} {self.period}"

class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    device_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} – {self.endpoint[:40]}…"

class WebAuthnPasskey(models.Model):
    """
    Eén WebAuthn/passkey credential per gebruiker per device.
    credential_id en public_key komen direct uit webauthn.verify_*_response().
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkeys",
    )
    # Base64url string van credential_id (zoals webauthn teruggeeft)
    credential_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Ruwe public key bytes zoals webauthn ze teruggeeft
    public_key = models.BinaryField()

    # Sign count (wordt bij elke succesvolle auth geüpdatet en gecontroleerd)
    sign_count = models.BigIntegerField(default=0)

    # Optioneel: user handle (zoals door client teruggestuurd)
    user_handle = models.CharField(max_length=255, blank=True)

    # Optioneel: transports / backup info, enkel voor debugging/UX
    transports = models.JSONField(default=list, blank=True)
    backed_up = models.BooleanField(default=False)

    # Per-device koppeling: zelfde concept als je WebPush device_hash
    device_hash = models.CharField(max_length=64, blank=True, db_index=True)

    nickname = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bijvoorbeeld 'iPhone van Sem' of 'Werktelefoon'.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Passkey"
        verbose_name_plural = "Passkeys"

    def __str__(self):
        base = self.nickname or f"Passkey {self.pk}"
        return f"{base} – {self.user}"
    
class Organization(models.Model):
    ORG_TYPE_APOTHEEK = "apotheek"
    ORG_TYPE_ZORGINSTELLING = "zorginstelling"

    ORG_TYPE_CHOICES = [
        (ORG_TYPE_APOTHEEK, "Apotheek"),
        (ORG_TYPE_ZORGINSTELLING, "Zorginstelling"),
    ]
    name = models.CharField(
        "Organisatienaam",
        max_length=255,
        unique=True,
        db_index=True,
    )
    email = models.EmailField(
        "E-mailadres",
        max_length=254,
        blank=True,
    )
    email2 = models.EmailField(
        "E-mailadres 2",
        max_length=254,
        blank=True,
    )
    phone = models.CharField(
        "Telefoonnummer",
        max_length=50,
        blank=True,
    )

    org_type = models.CharField(
    "Type organisatie",
    max_length=20,
    choices=ORG_TYPE_CHOICES,
    default=ORG_TYPE_APOTHEEK,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    class Dienstverband(models.TextChoices):
        VAST = "vast", "Vast contract"
        OPROEP = "oproep", "Oproeper"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    birth_date = models.DateField("Geboortedatum", null=True, blank=True, db_index=True)

    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        verbose_name="Organisatie",
    )

    dienstverband = models.CharField(
        "Dienstverband",
        max_length=10,
        choices=Dienstverband.choices,
        default=Dienstverband.OPROEP,
        db_index=True,
    )
    calendar_token = models.UUIDField(default=uuid.uuid4, unique=True,editable=False)

    # vaste werkdagen (ma-vr, ochtend/middag)
    work_mon_am = models.BooleanField("Ma ochtend", default=False)
    work_mon_pm = models.BooleanField("Ma middag", default=False)
    work_tue_am = models.BooleanField("Di ochtend", default=False)
    work_tue_pm = models.BooleanField("Di middag", default=False)
    work_wed_am = models.BooleanField("Wo ochtend", default=False)
    work_wed_pm = models.BooleanField("Wo middag", default=False)
    work_thu_am = models.BooleanField("Do ochtend", default=False)
    work_thu_pm = models.BooleanField("Do middag", default=False)
    work_fri_am = models.BooleanField("Vr ochtend", default=False)
    work_fri_pm = models.BooleanField("Vr middag", default=False)

    def clear_workdays(self):
        for f in (
            "work_mon_am","work_mon_pm","work_tue_am","work_tue_pm","work_wed_am","work_wed_pm",
            "work_thu_am","work_thu_pm","work_fri_am","work_fri_pm",
        ):
            setattr(self, f, False)

    def __str__(self):
        return f"Profiel van {self.user}"
    
class AgendaItem(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "Algemeen"
        OUTING = "outing", "Uitje"

    title = models.CharField(
        "Titel",
        max_length=50,
        help_text="Korte titel van het agendapunt (max. 50 tekens).",
    )
    description = models.CharField(
        "Beschrijving",
        max_length=100,
        help_text="Korte beschrijving (max. 100 tekens).",
    )
    date = models.DateField("Datum", db_index=True)

    category = models.CharField(
        "Categorie",
        max_length=10,
        choices=Category.choices,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agenda_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "category", "title"]

    def __str__(self):
        return f"{self.get_category_display()}: {self.title} op {self.date}"
    
class NewsItem(models.Model):
    title = models.CharField(max_length=50)
    short_description = models.CharField(
        max_length=100,
        blank=True,
        help_text="Korte beschrijving voor in de lijst (max 100 tekens).",
    )
    description = models.TextField(blank=True)
    date = models.DateField(auto_now_add=True)

    # Pad relatief t.o.v. MEDIA_ROOT, bv. "news/news.<hash>.pdf"
    file_path = models.CharField(max_length=255, blank=True, default="")
    file_hash = models.CharField(max_length=32, db_index=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-uploaded_at"]

    def __str__(self):
        return self.title

    @property
    def has_file(self) -> bool:
        return bool(self.file_path)

    @property
    def is_pdf(self) -> bool:
        """
        True als er een bestand is én het eindigt op .pdf
        """
        return bool(self.file_path) and self.file_path.lower().endswith(".pdf")

    @property
    def media_url(self) -> str:
        """
        Geeft de MEDIA URL terug, of een lege string als er geen bestand is.
        """
        if not self.file_path:
            return ""
        return f"{settings.MEDIA_URL}{self.file_path}"

class Werkafspraak(models.Model):
    class Category(models.TextChoices):
        BAXTER = "baxter", "Baxterproductie"
        INSTELLING = "instelling", "Instellingenapotheek"
        OPENBARE = "openbare", "Openbare Apotheek"

    title = models.CharField(
        "Titel",
        max_length=50,
        help_text="Korte titel van de werkafspraak (max. 50 tekens).",
    )
    short_description = models.CharField(
        "Beschrijving",
        max_length=100,
        help_text="Korte beschrijving van de werkafspraak (max. 100 tekens).",
    )
    
    # Pad relatief t.o.v. MEDIA_ROOT, bv. "werkafspraken/werkafspraak.<hash>.pdf"
    file_path = models.CharField(max_length=255, blank=True, default="")
    file_hash = models.CharField(max_length=32, db_index=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    
    category = models.CharField(
        "Categorie",
        max_length=10,
        choices=Category.choices,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="werkafspraken",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_category_display()}: {self.title}"

    class Meta:
        ordering = ["category", "title"]
    
    @property
    def has_file(self) -> bool:
        return bool(self.file_path)

    @property
    def is_pdf(self) -> bool:
        """
        True als er een bestand is én het eindigt op .pdf
        """
        return bool(self.file_path) and self.file_path.lower().endswith(".pdf")

    @property
    def media_url(self) -> str:
        """
        Geeft de MEDIA URL terug, of een lege string als er geen bestand is.
        """
        if not self.file_path:
            return ""
        return f"{settings.MEDIA_URL}{self.file_path}"
    
class RosterWeek(models.Model):
    monday = models.DateField(unique=True, db_index=True)
    week_slug = models.CharField(max_length=16, db_index=True)  # "week01"
    file_path = models.CharField(max_length=255, blank=True, default="")  # opgeslagen PDF pad (optioneel maar handig)
    file_hash = models.CharField(max_length=32, db_index=True, blank=True)  # sha[:16] past ook
    n_pages = models.PositiveIntegerField(default=0)
    preview_ext = models.CharField(max_length=8, default="webp")  # "webp" of "png" (legacy)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-monday"]

    def __str__(self):
        return f"{self.week_slug} ({self.monday})"
    
class MedicatieReviewAfdeling(models.Model):
    """
    Stamdata: Een afdeling binnen een organisatie en locatie.
    """
    organisatie = models.ForeignKey(
        "Organization", 
        on_delete=models.CASCADE, 
        related_name="medicatie_afdelingen",
        verbose_name="Organisatie"
    )
    
    afdeling = models.CharField("Naam afdeling", max_length=255)
    code = models.CharField("Code", max_length=10, blank=True)
    locatie = models.CharField("Locatie", max_length=255)
    
    # Optionele contactgegevens
    email = models.EmailField("E-mailadres", blank=True)
    email2 = models.EmailField("E-mailadres 2", blank=True)
    telefoon = models.CharField("Telefoonnummer", max_length=50, blank=True)

    # Tracking (Wanneer voor het laatst gewijzigd/gebruikt)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="afdelingen_created"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="afdelingen_updated"
    )

    def __str__(self):
        return f"{self.afdeling} - {self.locatie} - {self.organisatie.name}"

    class Meta:
        ordering = ["organisatie__name", "afdeling"]
        verbose_name = "Medicatiereview Afdeling"
        verbose_name_plural = "Medicatiereview Afdelingen"
        # Voorkom dubbele afdelingsnamen binnen dezelfde organisatie
        unique_together = ("organisatie", "locatie", "afdeling")


class MedicatieReviewPatient(models.Model):
    """Eén patiënt binnen een afdeling."""
    
    # AANGEPAST: on_delete=models.CASCADE
    # Als de Afdeling verwijderd wordt, worden alle gekoppelde patiënten ook verwijderd.
    afdeling = models.ForeignKey(
        MedicatieReviewAfdeling, 
        on_delete=models.CASCADE, 
        related_name="patienten"
        # null=True en blank=True zijn verwijderd omdat de koppeling nu strikt is.
    )
    
    # ENCRYPTIE: Wel versleuteld (Persoonsgegevens)
    naam = EncryptedCharField(max_length=255)
    geboortedatum = EncryptedDateField(null=True, blank=True)
    
    # GEEN ENCRYPTIE: Medische data zonder persoonsgegevens mag als standaard JSON
    analysis_data = models.JSONField()

    # Tracking historie
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name="patienten_created"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="patienten_updated"
    ) 

    def __str__(self):
        return self.naam

    class Meta:
        verbose_name = "Medicatiereview Patiënt"
        verbose_name_plural = "Medicatiereview Patiënten"


class MedicatieReviewComment(models.Model):
    """Opmerkingen van de apotheker, gekoppeld aan ID."""
    
    # DIT STOND AL GOED: on_delete=models.CASCADE
    # Als de Patiënt verwijderd wordt (handmatig of via cascade van de afdeling),
    # worden de comments ook verwijderd.
    patient = models.ForeignKey(MedicatieReviewPatient, on_delete=models.CASCADE, related_name="comments")
    
    jansen_group_id = models.IntegerField() 
    
    # ENCRYPTIE: Wel versleuteld (Vrije tekst kan namen bevatten)
    tekst = EncryptedTextField(blank=True)

    # Historische data (alleen-lezen in de frontend)
    historie = EncryptedTextField(blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ("patient", "jansen_group_id")

class VoorraadItem(models.Model):
    # Kolom 1: ZI-nummer (Verplicht 8 cijfers)
    zi_nummer = models.CharField(max_length=8, primary_key=True)
    
    # Kolom 2: Medicijnnaam
    naam = models.CharField(max_length=255)
    
    # Rest van de kolommen: Dynamische metadata
    metadata = models.JSONField(default=dict, blank=True)
    # Upload datum
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["naam"]
        verbose_name = "Voorraaditem"
        verbose_name_plural = "Voorraad"

    def __str__(self):
        return f"{self.zi_nummer} - {self.naam}"

class Nazending(models.Model):
    # Koppeling met VoorraadItem (bevat ZI en Naam)
    voorraad_item = models.ForeignKey(
        'VoorraadItem', 
        on_delete=models.CASCADE, 
        related_name='nazendingen',
        verbose_name="Geneesmiddel"
    )
    
    datum = models.DateField(verbose_name="Datum nazending")
    
    # Vrije tekst velden
    nazending_tot = models.CharField(
        max_length=255, 
        verbose_name="Nazending tot",
        help_text="Bijv. week 45 of 'onbekend'"
    )
    alternatief = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Alternatief",
        help_text="Vrij tekstveld"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["datum", "created_at"] # Oudste datum bovenaan
        verbose_name = "Nazending"
        verbose_name_plural = "Nazendingen"

    def __str__(self):
        return f"{self.datum} - {self.voorraad_item.naam}"
    
class LaatstePot(models.Model):
    voorraad_item = models.ForeignKey(
        'VoorraadItem', 
        on_delete=models.CASCADE, 
        related_name='laatste_potten',
        verbose_name="Geneesmiddel"
    )
    datum = models.DateField(default=timezone.now, verbose_name="Datum melding")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-datum", "-created_at"]
        verbose_name = "Laatste Pot"
        verbose_name_plural = "Laatste Potten"

    def __str__(self):
        # Gebruik self. om naar het gekoppelde item te verwijzen
        return f"{self.voorraad_item.naam} ({self.datum})"

class STSHalfje(models.Model):
    item_gehalveerd = models.ForeignKey(
        'VoorraadItem', 
        on_delete=models.CASCADE, 
        related_name='sts_gehalveerd',
        verbose_name="Geneesmiddel dat gehalveerd wordt"
    )
    item_alternatief = models.ForeignKey(
        'VoorraadItem', 
        on_delete=models.CASCADE, 
        related_name='sts_alternatieven',
        verbose_name="Alternatieve sterkte"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "STS Halfje"
        verbose_name_plural = "STS Halfjes"

    def __str__(self):
        return f"{self.item_gehalveerd.naam} -> {self.item_alternatief.naam}"