from django.db import models
from django.db.models import Q
from django.contrib.auth.models import Group
from django.conf import settings
from django.utils import timezone
from fernet_fields import EncryptedCharField, EncryptedDateField, EncryptedTextField
from django.core.validators import MinValueValidator
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
import secrets
from core.utils.medication import get_jansen_group_choices

class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def delete(self):
        """
        Bulk soft delete, bv: Location.objects.filter(...).delete()
        """
        return super().update(is_active=False, deleted_at=timezone.now())

    def hard_delete(self):
        """
        Echte delete in de DB.
        """
        return super().delete()


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        # Default manager toont alleen actieve records
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_inactive(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def inactive(self):
        return self.all_with_inactive().inactive()


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Default: alleen actieve
    objects = SoftDeleteManager()

    # Optioneel: alles (actief + inactief)
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """
        Instance soft delete, bv: obj.delete()
        """
        if self.is_active:
            self.is_active = False
            self.deleted_at = timezone.now()
            self.save(update_fields=["is_active", "deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

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
            ("can_manage_functies",              "Mag functies beheren"),
            ("can_manage_bezorgen",              "Mag bezorgen beheren"),
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
            ("can_edit_urendoorgeven",       "Mag uren toeslag aanpassen"),
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
            ("can_send_baxter_omzettingslijst", "Mag Baxter-omzettingslijst versturen"),
            # Geen levering
            ("can_view_baxter_no_delivery",     "Mag 'Geen levering' bekijken"),
            ("can_edit_baxter_no_delivery",     "Mag 'Geen levering' aanpassen"),
            ("can_send_baxter_no_delivery",     "Mag 'Geen levering' versturen"),
            # STS halfjes
            ("can_view_baxter_sts_halfjes",     "Mag STS-halfjes bekijken"),
            ("can_edit_baxter_sts_halfjes",     "Mag STS-halfjes aanpassen"),
            ("can_send_baxter_sts_halfjes",     "Mag STS-halfjes versturen"),
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
            # Houdbaarheid check
            ("can_edit_houdbaarheidcheck", "Mag Houdbaarheid Check uitvoeren"),
            # Bezorgers
            ("can_view_bezorgers",    "Mag Bezorgers openen"),
            ("can_view_bakkenbezorgen",    "Mag bakken bezorgen"),
            ("can_view_afleverstatus",    "Mag afleverstatus bekijken"),
            # KompasGPT
            ("can_view_kompasgpt",    "Mag KompasGPT gebruiken"),

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

class Dagdeel(models.Model):
    CODE_MORNING     = "morning"      # Ochtend
    CODE_AFTERNOON   = "afternoon"    # Middag
    CODE_PRE_EVENING = "pre_evening"  # Vooravond
    CODE_EVENING     = "evening"      # Avond
    CODE_NIGHT       = "night"        # Nacht

    CODE_CHOICES = [
        (CODE_MORNING,     "Ochtend"),
        (CODE_AFTERNOON,   "Middag"),
        (CODE_PRE_EVENING, "Vooravond"),
        (CODE_EVENING,     "Avond"),
        (CODE_NIGHT,       "Nacht"),
    ]

    # Alleen deze 3 mogen als “normaal” ingepland worden in Availability/Shifts
    PLANNING_CODES = (CODE_MORNING, CODE_AFTERNOON, CODE_PRE_EVENING)

    code = models.CharField(max_length=12, choices=CODE_CHOICES, unique=True, db_index=True)

    # label in frontend (maar wij gaan die vast zetten op basis van code)
    name = models.CharField(max_length=40, default="", blank=True)

    start_time = models.TimeField()
    end_time = models.TimeField()

    # 100 = geen toeslag, 120 = 20% extra
    allowance_pct = models.PositiveSmallIntegerField(default=100, validators=[MinValueValidator(0)])

    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.CheckConstraint(
                check=Q(allowance_pct__gte=0) & Q(allowance_pct__lte=300),
                name="dagdeel_allowance_pct_range_0_300",
            ),
        ]

    @staticmethod
    def _to_minutes(t):
        return t.hour * 60 + t.minute

    def _intervals(self):
        """
        Return 1 of 2 intervals in minuten [start,end) op dag-basis.
        Als end <= start: wrap-around (over middernacht).
        """
        s = self._to_minutes(self.start_time)
        e = self._to_minutes(self.end_time)
        if e == s:
            # 0 minuten duur is nooit ok
            return []
        if e > s:
            return [(s, e)]
        # wrap-around, bv 20:00 -> 00:00
        return [(s, 1440), (0, e)]

    def clean(self):
        # basis guard
        if not self.start_time or not self.end_time:
            return

        # duur mag niet 0
        if self.start_time == self.end_time:
            raise ValidationError("Starttijd en eindtijd mogen niet gelijk zijn.")

        # Overlap check met wrap-around ondersteuning
        my_intervals = self._intervals()
        if not my_intervals:
            raise ValidationError("Ongeldige tijdsduur voor dit dagdeel.")

        others = Dagdeel.objects.exclude(pk=self.pk)
        for o in others:
            if not o.start_time or not o.end_time:
                continue
            other_intervals = o._intervals()
            for (a, b) in my_intervals:
                for (c, d) in other_intervals:
                    # overlap: [a,b) en [c,d)
                    if a < d and c < b:
                        raise ValidationError(
                            f"Overlappende tijden met '{o.get_code_display()}'."
                        )

    def save(self, *args, **kwargs):
        # name + sort_order vast op basis van code
        label_map = dict(self.CODE_CHOICES)
        self.name = label_map.get(self.code, self.code)

        order_map = {
            self.CODE_MORNING: 10,
            self.CODE_AFTERNOON: 20,
            self.CODE_PRE_EVENING: 30,
            self.CODE_EVENING: 40,
            self.CODE_NIGHT: 50,
        }
        self.sort_order = order_map.get(self.code, 99)

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def allowance_multiplier(self) -> Decimal:
        return (Decimal(self.allowance_pct) / Decimal("100.0"))

    @property
    def extra_pct(self) -> int:
        return int(self.allowance_pct) - 100

    def __str__(self):
        return f"{self.get_code_display()} ({self.start_time}-{self.end_time}, {self.allowance_pct}%)"

class Availability(models.Model):
    SOURCE_CHOICES = [
        ("auto", "Auto"),
        ("manual", "Manual"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    date = models.DateField(db_index=True)

    # dagdelen i.p.v. morning/afternoon/evening booleans
    dagdelen = models.ManyToManyField(
        "Dagdeel",
        blank=True,
        related_name="availabilities",
        limit_choices_to={"code__in": Dagdeel.PLANNING_CODES},  # alleen “normale” codes
    )

    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="manual",
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["date"]

    def __str__(self):
        codes = list(self.dagdelen.values_list("code", flat=True))
        return f"{self.user} @ {self.date} ({','.join(codes)})"
    
class Location(SoftDeleteModel):
    COLOR_CHOICES = [
        ("green", "Groen"),
        ("red", "Rood"),
        ("blue", "Blauw"),
    ]

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, default="")
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default="blue")

    # Conditional unique constraint
    class Meta:
        verbose_name_plural = "Locations"
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_active=True),
                name="uniq_active_location_name",
            )
        ]

    def __str__(self):
        return self.name

class Task(SoftDeleteModel):
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
        constraints = [
            models.UniqueConstraint(
                fields=["location", "name"],
                condition=Q(is_active=True),
                name="uniq_active_task_name_per_location",
            )
        ]

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
    
class Function(models.Model):
    title = models.CharField(max_length=120)
    ranking = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Lager nummer = hoger in de lijst."
    )

    class Meta:
        verbose_name = "Functie"
        verbose_name_plural = "Functies"
        ordering = ["ranking", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["title"],
                name="uniq_function_title",
            )
        ]

    def __str__(self):
        return self.title

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

class NativePushToken(models.Model):
    PLATFORM_CHOICES = (
        ("ios", "iOS"),
        ("android", "Android"),
        ("web", "Web"),
        ("", "Unknown"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="native_push_tokens",
    )
    token = models.CharField(max_length=512, unique=True)  # FCM/APNS token
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, blank=True, default="")
    device_id = models.CharField(max_length=128, blank=True, db_index=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} – {self.platform} – {self.token[:20]}…"

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

class NativeBiometricDevice(models.Model):
    """
    Native (Capacitor) "biometric login" koppeling voor een WebView app die Django sessions gebruikt.

    Concept:
      - App genereert een random device_secret (32 bytes) en bewaart die in Keychain/Keystore (biometrie-gated).
      - Server bewaart alleen een HASH van die secret.
      - Bij login stuurt app device_id + secret -> server verifieert hash -> login(request, user) -> session cookie.
    """

    PLATFORM_CHOICES = (
        ("ios", "iOS"),
        ("android", "Android"),
        ("other", "Other"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="native_biometric_devices",
    )

    # Stabiel per app-install (of per device), niet je JS device_hash.
    device_id = models.CharField(max_length=128, db_index=True)

    # Optioneel voor UX
    nickname = models.CharField(max_length=100, blank=True)

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default="other")

    # Hash van het device_secret (geen plain secret opslaan!)
    secret_hash = models.CharField(max_length=128)

    # Rotatie: je kunt later een nieuwe secret zetten en de oude ongeldig maken
    secret_version = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Native biometric device"
        verbose_name_plural = "Native biometric devices"
        indexes = [
            models.Index(fields=["device_id"]),
            models.Index(fields=["user", "device_id"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "device_id"], name="uniq_user_device_id")
        ]

    def __str__(self) -> str:
        base = self.nickname or self.device_id
        return f"{base} – {self.user}"

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

    @staticmethod
    def new_device_secret() -> str:
        # Base64url-achtige string zonder "="; makkelijk te transporteren
        return secrets.token_urlsafe(32)
    
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
    # Avonden ook
    work_mon_ev = models.BooleanField("Ma vooravond", default=False)
    work_tue_ev = models.BooleanField("Di vooravond", default=False)
    work_wed_ev = models.BooleanField("Wo vooravond", default=False)
    work_thu_ev = models.BooleanField("Do vooravond", default=False)
    work_fri_ev = models.BooleanField("Vr vooravond", default=False)
    # zaterdag (ochtend/middag/vooravond)
    work_sat_am = models.BooleanField("Za ochtend", default=False)
    work_sat_pm = models.BooleanField("Za middag", default=False)
    work_sat_ev = models.BooleanField("Za vooravond", default=False)

    # === Profielfoto ===
    avatar = models.ImageField("Profielfoto", upload_to="avatars/", null=True, blank=True)
    avatar_hash = models.CharField(max_length=16, blank=True, default="", db_index=True)
    avatar_updated_at = models.DateTimeField(null=True, blank=True)

    # === Functies ===
    function = models.ForeignKey(
    "core.Function",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="profiles",
    )

    phone_number = models.CharField("Telefoonnummer", max_length=15, blank=True, default="")

    def clear_workdays(self):
        for f in (
            "work_mon_am","work_mon_pm","work_tue_am","work_tue_pm","work_wed_am","work_wed_pm",
            "work_thu_am","work_thu_pm","work_fri_am","work_fri_pm", "work_mon_ev", "work_tue_ev", "work_wed_ev", "work_thu_ev", "work_fri_ev", "work_sat_am", "work_sat_pm", "work_sat_ev"
        ):
            setattr(self, f, False)

    def __str__(self):
        return f"Profiel van {self.user}"
    
class NotificationPreferences(models.Model):
    profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="notif_prefs",
    )

    # === Push (parent + children) ===
    push_enabled = models.BooleanField(default=True)
    push_new_roster = models.BooleanField(default=True)
    push_new_agenda = models.BooleanField(default=True)
    push_news_upload = models.BooleanField(default=True)
    push_dienst_changed = models.BooleanField(default=True)

    push_birthday_self = models.BooleanField(default=True)
    push_birthday_apojansen = models.BooleanField(default=True)
    push_uren_reminder = models.BooleanField(default=True)

    # === Email (parent + children) ===
    email_enabled = models.BooleanField(default=True)
    email_birthday_self = models.BooleanField(default=True)
    email_uren_reminder = models.BooleanField(default=True)
    email_diensten_overzicht = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notificatievoorkeuren {self.profile.user}"
    
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
    start_time = models.TimeField("Starttijd", null=True, blank=True)
    end_time = models.TimeField("Eindtijd", null=True, blank=True)

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
    
class OnboardingFormulier(models.Model):
    title = models.CharField(
        "Titel",
        max_length=80,
        help_text="Naam van het formulier (max. 80 tekens).",
    )
    url = models.URLField(
        "URL",
        max_length=500,
        help_text="Volledige link naar het formulier (bijv. Google Forms).",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="formulieren",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        permissions = [
            ("can_view_forms", "Mag formulieren bekijken"),
            ("can_edit_forms", "Mag formulieren aanpassen"),
        ]

    def __str__(self):
        return self.title
    

class InschrijvingItem(models.Model):
    title = models.CharField("Titel", max_length=80, help_text="Naam van het formulier (max. 80 tekens).")
    url = models.URLField("URL", max_length=500, help_text="Volledige link naar het formulier (bijv. Google Forms).")

    verloopdatum = models.DateField(
        "Verloopdatum",
        null=True,
        blank=True,
        help_text="Optioneel: na deze datum wordt dit item automatisch verwijderd.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inschrijvingen",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["verloopdatum", "title"]

    def __str__(self):
        return self.title
    
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

class MedicatieReviewMedGroupOverride(models.Model):
    patient = models.ForeignKey(
        "core.MedicatieReviewPatient",
        on_delete=models.CASCADE,
        related_name="med_group_overrides",
    )

    # exact gm.clean (sleutel)
    med_clean = models.CharField(max_length=255)

    # display-naam override
    override_name = models.CharField(max_length=255, blank=True, default="")

    # target groep (met choices uit jouw JSON)
    target_jansen_group_id = models.IntegerField(choices=get_jansen_group_choices())

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("patient", "med_clean")

    def __str__(self) -> str:
        return f"{self.patient_id}: {self.med_clean} -> {self.target_jansen_group_id}"

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
    afhandeling = models.TextField(
        blank=True,
        default="",
        verbose_name="Afhandeling",
        help_text="Vrije tekst: hoe is dit afgehandeld?"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-datum", "-created_at"]
        verbose_name = "Laatste Pot"
        verbose_name_plural = "Laatste Potten"

    def __str__(self):
        # Gebruik self. om naar het gekoppelde item te verwijzen
        return f"{self.voorraad_item.naam} ({self.datum})"

class STSHalfje(models.Model):
    afdeling = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="Afdeling",
    )
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

    apotheek = models.ForeignKey(
        'Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sts_halfjes',
        verbose_name="Apotheek"
    )
    patient_naam_enc = EncryptedCharField(max_length=255, blank=True, default="")
    patient_geboortedatum_enc = EncryptedDateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "STS Halfje"
        verbose_name_plural = "STS Halfjes"

    def __str__(self):
        return f"{self.item_gehalveerd.naam} -> {self.item_alternatief.naam}"
    
    @property
    def patient_naam(self):
        return self.patient_naam_enc

    @property
    def patient_geboortedatum(self):
        return self.patient_geboortedatum_enc
  
class NoDeliveryList(models.Model):
    DAG_MA = "MA"
    DAG_DI = "DI"
    DAG_WO = "WO"
    DAG_DO = "DO"
    DAG_VR = "VR"
    DAG_ZA = "ZA"

    DAG_CHOICES = (
        (DAG_MA, "Maandag"),
        (DAG_DI, "Dinsdag"),
        (DAG_WO, "Woensdag"),
        (DAG_DO, "Donderdag"),
        (DAG_VR, "Vrijdag"),
        (DAG_ZA, "Zaterdag"),
    )

    apotheek = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="no_delivery_lists",
        verbose_name="Apotheek",
    )

    jaar = models.IntegerField(verbose_name="Jaar")
    week = models.IntegerField(verbose_name="Week")

    dag = models.CharField(
        max_length=2,
        choices=DAG_CHOICES,
        default=DAG_MA,
        verbose_name="Dag",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # <-- nieuw

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        verbose_name = "Geen levering lijst"
        verbose_name_plural = "Geen levering lijsten"
        unique_together = ("apotheek", "jaar", "week", "dag")

    def __str__(self):
        apo = self.apotheek.name if self.apotheek else "-"
        return f"{apo} - {self.jaar} W{self.week} - {self.get_dag_display()}"

    @property
    def dag_label(self):
        return self.get_dag_display()


class NoDeliveryEntry(models.Model):
    no_delivery_list = models.ForeignKey(
        NoDeliveryList,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Geen levering lijst",
    )

    afdeling = models.CharField(max_length=10, blank=True, default="", verbose_name="Afdeling")

    patient_naam_enc = EncryptedCharField(max_length=255, blank=True, default="")
    patient_geboortedatum_enc = EncryptedDateField(null=True, blank=True)

    gevraagd_geneesmiddel = models.ForeignKey(
        VoorraadItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="no_delivery_entries",
        verbose_name="Gevraagd geneesmiddel",
    )

    vanaf_datum = models.DateField(null=True, blank=True, verbose_name="Vanaf datum")

    sts_paraaf = models.CharField(max_length=50, blank=True, default="", verbose_name="STS paraaf")
    roller_paraaf = models.CharField(max_length=50, blank=True, default="", verbose_name="Roller paraaf")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # <-- nieuw (optioneel maar handig)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        verbose_name = "Geen levering entry"
        verbose_name_plural = "Geen levering entries"

    def __str__(self):
        apo = self.no_delivery_list.apotheek.name if self.no_delivery_list and self.no_delivery_list.apotheek else "-"
        return f"{apo} - {self.afdeling} - {self.patient_naam or '-'}"

    @property
    def patient_naam(self):
        return self.patient_naam_enc

    @property
    def patient_geboortedatum(self):
        return self.patient_geboortedatum_enc
    

class Omzettingslijst(models.Model):
    DAG_MA = "MA"
    DAG_DI = "DI"
    DAG_WO = "WO"
    DAG_DO = "DO"
    DAG_VR = "VR"
    DAG_ZA = "ZA"

    DAG_CHOICES = (
        (DAG_MA, "Maandag"),
        (DAG_DI, "Dinsdag"),
        (DAG_WO, "Woensdag"),
        (DAG_DO, "Donderdag"),
        (DAG_VR, "Vrijdag"),
        (DAG_ZA, "Zaterdag"),
    )

    apotheek = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="omzettingslijsten",
        verbose_name="Apotheek",
    )

    jaar = models.IntegerField(verbose_name="Jaar")
    week = models.IntegerField(verbose_name="Week")

    dag = models.CharField(
        max_length=2,
        choices=DAG_CHOICES,
        default=DAG_MA,
        verbose_name="Dag",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        verbose_name = "Omzettingslijst"
        verbose_name_plural = "Omzettingslijsten"
        unique_together = ("apotheek", "jaar", "week", "dag")

    def __str__(self):
        apo = self.apotheek.name if self.apotheek else "-"
        return f"{apo} - {self.jaar} W{self.week} - {self.get_dag_display()}"

    @property
    def dag_label(self):
        return self.get_dag_display()


class OmzettingslijstEntry(models.Model):
    omzettingslijst = models.ForeignKey(
        Omzettingslijst,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Omzettingslijst",
    )

    afdeling = models.CharField(max_length=10, blank=True, default="", verbose_name="Afdeling")

    patient_naam_enc = EncryptedCharField(max_length=255, blank=True, default="")
    patient_geboortedatum_enc = EncryptedDateField(null=True, blank=True)

    gevraagd_geneesmiddel = models.ForeignKey(
        VoorraadItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="omzettingslijst_entries_gevraagd",
        verbose_name="Gevraagd geneesmiddel",
    )

    geleverd_geneesmiddel = models.ForeignKey(
        VoorraadItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="omzettingslijst_entries_geleverd",
        verbose_name="Geleverd geneesmiddel",
    )

    omschrijving_geneesmiddel = models.CharField(
        max_length=80,
        blank=True,
        default="",
        verbose_name="Omschrijving geneesmiddel",
        help_text="Bijv: tabl. rond wit 500",
    )

    vanaf_datum = models.DateField(null=True, blank=True, verbose_name="Vanaf datum")

    sts_paraaf = models.CharField(max_length=50, blank=True, default="", verbose_name="STS paraaf")
    roller_paraaf = models.CharField(max_length=50, blank=True, default="", verbose_name="Roller paraaf")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        verbose_name = "Omzettingslijst entry"
        verbose_name_plural = "Omzettingslijst entries"

    def __str__(self):
        apo = self.omzettingslijst.apotheek.name if self.omzettingslijst and self.omzettingslijst.apotheek else "-"
        return f"{apo} - {self.afdeling} - {self.patient_naam or '-'}"

    @property
    def patient_naam(self):
        return self.patient_naam_enc

    @property
    def patient_geboortedatum(self):
        return self.patient_geboortedatum_enc

class UrenMaand(models.Model):
    """
    1 record per gebruiker per 'actieve maand' (month = eerste dag van die maand).
    Bevat maand-meta zoals kilometers.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uren_maanden",
    )
    month = models.DateField("Maand", db_index=True, help_text="Eerste dag van de maand.")

    kilometers = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "month"], name="uniq_user_month_urenmaand"),
        ]
        ordering = ["-month", "user_id"]

    def __str__(self):
        return f"{self.user_id} - {self.month} (km={self.kilometers})"


class UrenRegel(models.Model):
    """
    1 regel per user per datum per dagdeel.
    Shifts worden NIET bij GET aangemaakt; alleen bij save/upsert als user uren invult.
    """
    SOURCE_CHOICES = [
        ("shift", "Shift"),
        ("manual", "Manual"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uren_regels",
    )

    # Denormalized voor snelle maandfiltering + uniekheid in admin/debug
    month = models.DateField(db_index=True, help_text="Eerste dag van de actieve maand.")

    date = models.DateField(db_index=True)

    dagdeel = models.ForeignKey(
        "Dagdeel",
        on_delete=models.PROTECT,
        related_name="uren_regels",
    )

    # Optioneel: link naar de shift die als suggestie is gebruikt
    shift = models.ForeignKey(
        "Shift",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uren_regels",
    )

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual", db_index=True)

    actual_hours = models.DecimalField(
        "Gewerkte uren",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        default=None,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "date", "dagdeel"], name="uniq_user_date_dagdeel_urenregel"),
        ]
        ordering = ["date", "dagdeel__sort_order", "id"]

    def __str__(self):
        return f"{self.user_id} {self.date} {self.dagdeel.code} ({self.actual_hours})"

class UrenDag(models.Model):
    """
    1 record per user per datum met start/eind/pauze (de nieuwe UX input).
    We blijven UrenRegel vullen als afgeleide tabel.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uren_dagen",
    )

    month = models.DateField(db_index=True, help_text="Eerste dag van de actieve maand.")
    date = models.DateField(db_index=True)

    start_time = models.TimeField()
    end_time = models.TimeField()

    # pauze in uren met 1 decimaal (bijv. 0,5)
    break_hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal("0.0"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="uniq_user_date_urendag"),
        ]
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.user_id} {self.date} {self.start_time}-{self.end_time} (break={self.break_hours})"
    
# KompasGPT
class ScrapedPage(models.Model):
    CATEGORY_CHOICES = [
        ('preparaat', 'Preparaat'),
        ('groep', 'Groep'),
        ('indicatie', 'Indicatie'),
    ]
    
    url = models.URLField(unique=True)
    title = models.CharField(max_length=512)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    content_hash = models.CharField(max_length=64)  # SHA-256
    last_scraped = models.DateTimeField(auto_now=True)
    gcs_path = models.CharField(max_length=1024, blank=True)

    def __str__(self):
        return f"{self.title} ({self.category})"