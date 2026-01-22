from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model, authenticate
from django.core.validators import FileExtensionValidator, MaxLengthValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from .views._helpers import PERM_LABELS, PERM_SECTIONS

from two_factor.forms import AuthenticationTokenForm, TOTPDeviceForm 

from core.models import UserProfile, Organization, AgendaItem, NewsItem, Werkafspraak, MedicatieReviewAfdeling, Nazending, VoorraadItem, StandaardInlog, LaatstePot, STSHalfje, Location, Task, OnboardingFormulier, InschrijvingItem, UrenMaand, UrenRegel, NotificationPreferences, Function, Dagdeel, NoDeliveryEntry, NoDeliveryList

UserModel = get_user_model()


class GroupWithPermsForm(forms.ModelForm):
    """
    Bouwt permissie-checkboxen dynamisch vanuit PERM_LABELS.
    - Maakt BooleanFields tijdens __init__
    - Vult initial op basis van group.permissions
    - Slaat gekozen permissies op
    """
    class Meta:
        model = Group
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1) Alle permissies voor ons 'synthetische' content type
        ct, _ = ContentType.objects.get_or_create(app_label="core", model="custompermission")

        # Haal alle Permission objects op die we in PERM_LABELS gebruiken
        perms_qs = Permission.objects.filter(content_type=ct, codename__in=PERM_LABELS.keys())
        # Map: codename -> Permission object
        self.perm_map = {p.codename: p for p in perms_qs}

        # 2) Dynamisch BooleanFields aanmaken volgens PERM_LABELS
        for code, label in PERM_LABELS.items():
            self.fields[code] = forms.BooleanField(required=False, label=label)

        # 3) Initial waarden zetten als er een bestaande groep is
        if self.instance and self.instance.pk:
            current_codes = set(self.instance.permissions.values_list("codename", flat=True))
            for code in PERM_LABELS.keys():
                self.fields[code].initial = (code in current_codes)

        # 4) Secties doorgeven aan de form zelf, gefilterd op bestaande velden
        self.sections = [(title, [c for c in codes if c in self.fields]) for title, codes in PERM_SECTIONS]

    def save(self, commit=True):
        g = super().save(commit)
        # Verzamel alle gekozen codenames
        chosen_codes = [code for code in PERM_LABELS.keys() if self.cleaned_data.get(code)]
        # Converteer naar Permission objects
        chosen_perms = [self.perm_map[code] for code in chosen_codes if code in self.perm_map]
        g.permissions.set(chosen_perms)
        return g

class StandaardInlogForm(forms.ModelForm):
    class Meta:
        model = StandaardInlog
        fields = ['standaard_rol']
        widgets = {
            'standaard_rol': forms.Select(attrs={'class': 'admin-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['standaard_rol'].label = "Kies de rol waarmee elke computer in de apotheek met één druk op de knop kan inloggen."
        # Sorteer de lijst netjes op naam
        self.fields['standaard_rol'].queryset = Group.objects.all().order_by('name')

class SimpleUserCreateForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150, required=True)
    last_name = forms.CharField(label="Achternaam", max_length=150, required=True)
    email = forms.EmailField(label="E-mail", required=True)
    phone_number = forms.CharField(
        label="Telefoonnummer", 
        required=False, 
        widget=forms.TextInput(attrs={"class": "admin-input", "placeholder": "0612345678"})
    )
    birth_date = forms.DateField(
        label="Geboortedatum",
        required=False,
        input_formats=["%d-%m-%Y"],  # we verwachten d-m-Y van de datepicker
        widget=forms.DateInput(
            attrs={
                # GEEN type="date" meer → anders krijg je de native picker erbij
                "placeholder": "dd-mm-jjjj",
                "class": "admin-input js-date",  # class waarop we flatpickr hangen
                "autocomplete": "off",
            }
        ),
    )
    group = forms.ModelChoiceField(
        label="Groep",
        queryset=Group.objects.all(),
        required=True,
        empty_label="----------",
    )
    organization = forms.ModelChoiceField(
        label="Organisatie",
        queryset=Organization.objects.all(),
        required=True,
        empty_label="----------",
    )

    function = forms.ModelChoiceField(
        label="Functie",
        queryset=Function.objects.all().order_by("ranking", "title"),
        required=False,
        empty_label="----------",
        widget=forms.Select(attrs={"class": "admin-select"}),
    )

    def clean_first_name(self):
        first = (self.cleaned_data.get("first_name") or "").strip().lower()
        if not first:
            raise forms.ValidationError("Voornaam is verplicht.")
        return first
    
    def clean_last_name(self):
        last = (self.cleaned_data.get("last_name") or "").strip().lower()
        if not last:
            raise forms.ValidationError("Achternaam is verplicht.")
        return last

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("E-mail is verplicht.")
        if UserModel.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Er bestaat al een gebruiker met dit e-mailadres.")
        return email

WORK_FIELDS = (
    "work_mon_am","work_mon_pm","work_mon_ev",
    "work_tue_am","work_tue_pm","work_tue_ev",
    "work_wed_am","work_wed_pm","work_wed_ev",
    "work_thu_am","work_thu_pm","work_thu_ev",
    "work_fri_am","work_fri_pm","work_fri_ev",
    "work_sat_am","work_sat_pm","work_sat_ev",
)

class SimpleUserEditForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150, required=True)
    last_name = forms.CharField(label="Achternaam", max_length=150, required=True)
    email = forms.EmailField(label="E-mail", required=True)
    phone_number = forms.CharField(label="Telefoonnummer", required=False, widget=forms.TextInput(attrs={"class": "admin-input"}))


    birth_date = forms.DateField(
        label="Geboortedatum",
        required=False,
        input_formats=["%d-%m-%Y"],
        widget=forms.DateInput(
            attrs={
                "placeholder": "dd-mm-jjjj",
                "class": "admin-input js-date",
                "autocomplete": "off",
            }
        ),
    )

    group = forms.ModelChoiceField(
        label="Groep",
        queryset=Group.objects.all(),
        required=True,
        empty_label="----------",
    )

    organization = forms.ModelChoiceField(
        label="Organisatie",
        queryset=Organization.objects.all(),
        required=True,
        empty_label="----------",
    )

    dienstverband = forms.ChoiceField(
        label="Dienstverband",
        choices=UserProfile.Dienstverband.choices,
        required=True,
        widget=forms.Select(attrs={"class": "admin-select js-dienstverband"}),
    )

    function = forms.ModelChoiceField(
        label="Functie",
        queryset=Function.objects.all().order_by("ranking", "title"),
        required=False,
        empty_label="----------",
        widget=forms.Select(attrs={"class": "admin-select"}),
    )

    # werkblokken (ma-vr, ochtend/middag)
    work_mon_am = forms.BooleanField(required=False)
    work_mon_pm = forms.BooleanField(required=False)
    work_tue_am = forms.BooleanField(required=False)
    work_tue_pm = forms.BooleanField(required=False)
    work_wed_am = forms.BooleanField(required=False)
    work_wed_pm = forms.BooleanField(required=False)
    work_thu_am = forms.BooleanField(required=False)
    work_thu_pm = forms.BooleanField(required=False)
    work_fri_am = forms.BooleanField(required=False)
    work_fri_pm = forms.BooleanField(required=False)
    work_mon_ev = forms.BooleanField(required=False)
    work_tue_ev = forms.BooleanField(required=False)
    work_wed_ev = forms.BooleanField(required=False)
    work_thu_ev = forms.BooleanField(required=False)
    work_fri_ev = forms.BooleanField(required=False)

    work_sat_am = forms.BooleanField(required=False)
    work_sat_pm = forms.BooleanField(required=False)
    work_sat_ev = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        # instance is optioneel: bij create = None, bij edit = User instance
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        # defaults bij create
        self.fields["dienstverband"].initial = UserProfile.Dienstverband.OPROEP

        if not self.instance:
            return

        # initials bij edit (als je later ooit het form zou renderen)
        self.fields["first_name"].initial = self.instance.first_name or self.instance.username
        self.fields["last_name"].initial = self.instance.last_name
        self.fields["email"].initial = self.instance.email

        g = self.instance.groups.first()
        if g:
            self.fields["group"].initial = g.id

        profile = getattr(self.instance, "profile", None)
        if profile:
            self.fields["dienstverband"].initial = profile.dienstverband
            self.fields["phone_number"].initial = profile.phone_number

            if profile.birth_date:
                self.fields["birth_date"].initial = profile.birth_date.strftime("%d-%m-%Y")
            if profile.organization:
                self.fields["organization"].initial = profile.organization.id

            if profile.function_id:
                self.fields["function"].initial = profile.function_id

            for f in WORK_FIELDS:
                self.fields[f].initial = getattr(profile, f, False)

    def clean_first_name(self):
        first = (self.cleaned_data.get("first_name") or "").strip().lower()
        if not first:
            raise forms.ValidationError("Voornaam is verplicht.")
        return first

    def clean_last_name(self):
        last = (self.cleaned_data.get("last_name") or "").strip().lower()
        if not last:
            raise forms.ValidationError("Achternaam is verplicht.")
        return last

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("E-mail is verplicht.")

        qs = UserModel.objects.filter(email__iexact=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Er bestaat al een gebruiker met dit e-mailadres.")

        return email

    def save(self):
        """
        Werkt voor BOTH:
        - create: self.instance is None → maakt User + Profile
        - edit: self.instance is User → update User + Profile
        """
        first = self.cleaned_data["first_name"]
        last = self.cleaned_data["last_name"]
        email = self.cleaned_data["email"]
        phone_number = self.cleaned_data.get("phone_number")

        group = self.cleaned_data.get("group")
        birth_date = self.cleaned_data.get("birth_date")
        organization = self.cleaned_data.get("organization")

        dienstverband = self.cleaned_data.get("dienstverband")
        function = self.cleaned_data.get("function")

        if self.instance:
            u = self.instance
            u.username = email
            u.first_name = first
            u.last_name = last
            u.email = email
            u.save(update_fields=["username", "first_name", "last_name", "email"])
        else:
            u = UserModel.objects.create(
                username=email,
                first_name=first,
                last_name=last,
                email=email,
                is_active=True,
            )
            u.set_unusable_password()
            u.save(update_fields=["password"])

        profile, _ = UserProfile.objects.get_or_create(user=u)
        profile.birth_date = birth_date
        profile.organization = organization
        profile.dienstverband = dienstverband
        profile.function = function
        profile.phone_number = phone_number

        if dienstverband == UserProfile.Dienstverband.OPROEP:
            profile.clear_workdays()
        else:
            for f in WORK_FIELDS:
                setattr(profile, f, bool(self.cleaned_data.get(f)))

        profile.save()

        # group opslaan
        u.groups.clear()
        if group:
            u.groups.add(group)

        return u
    
class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = NotificationPreferences
        fields = [
            "push_enabled",
            "push_new_roster",
            "push_new_agenda",
            "push_news_upload",
            "push_dienst_changed",
            "push_birthday_self",
            "push_birthday_apojansen",
            "push_uren_reminder",
            "email_enabled",
            "email_birthday_self",
            "email_uren_reminder",
            "email_diensten_overzicht",
        ]
    
class OrganizationEditForm(forms.Form):
    ORG_TYPE_CHOICES = [
        ("apotheek", "Apotheek"),
        ("zorginstelling", "Zorginstelling"),
    ]

    name = forms.CharField(label="Naam organisatie", max_length=255)
    email = forms.EmailField(label="E-mailadres", required=True)
    email2 = forms.EmailField(label="E-mailadres 2", required=False)
    phone = forms.CharField(label="Telefoonnummer", max_length=50, required=False)
    org_type = forms.ChoiceField(
        label="Type organisatie",
        choices=ORG_TYPE_CHOICES,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)

        self.fields["name"].initial = self.instance.name
        self.fields["email"].initial = self.instance.email
        self.fields["email2"].initial = self.instance.email2
        self.fields["phone"].initial = self.instance.phone
        self.fields["org_type"].initial = self.instance.org_type or "zorginstelling"

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Organisatienaam is verplicht.")

        qs = Organization.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Er bestaat al een organisatie met deze naam.")
        return name

    def save(self):
        org = self.instance
        org.name = self.cleaned_data["name"].strip()
        org.email = (self.cleaned_data.get("email") or "").strip() or ""
        org.email2 = (self.cleaned_data.get("email2") or "").strip() or ""
        org.phone = (self.cleaned_data.get("phone") or "").strip() or ""
        org.org_type = self.cleaned_data["org_type"]
        org.save()
        return org

class AvailabilityUploadForm(forms.Form):
    file = forms.FileField(label="Bestand (CSV of XLSX)", help_text="Upload een CSV of Excel-bestand.")


class EmailOrUsernameLoginForm(forms.Form):
    identifier = forms.CharField(label="Gebruikersnaam of e-mail")
    password = forms.CharField(label="Wachtwoord", widget=forms.PasswordInput)


class RosterUploadForm(forms.Form):
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        allow_empty_file=False,
        label="Rooster (PDF)",
    )

class IdentifierAuthenticationForm(AuthenticationForm):
    """
    Login met gebruikersnaam, e-mailadres of unieke voornaam.
    Form zelf pusht GEEN messages; dat doet de view. Dit voorkomt dubbele meldingen.
    """

    username = forms.CharField(
        label=_("Gebruikersnaam, e-mailadres of voornaam"),
        widget=forms.TextInput(attrs={"autofocus": True}),
    )

    error_messages = {
        "invalid_login": _(
            "Combinatie niet gevonden. Controleer je gegevens en probeer het opnieuw."
        ),
        "inactive": _(
            "Dit account is (nog) niet actief. Neem contact op met een beheerder."
        ),
        "multiple_firstname": _(
            "Er zijn meerdere gebruikers met deze voornaam. Log in met je e-mailadres."
        ),
        "password_required": _("Voer je wachtwoord in."),
    }

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(self.error_messages["inactive"], code="inactive")

    def clean(self):
        identifier = (self.cleaned_data.get("username") or "").strip().lower()
        password   = self.cleaned_data.get("password")

        if not password:
            raise forms.ValidationError(self.error_messages["password_required"], code="password_required")

        resolved_username = None
        if "@" in identifier:
            u = UserModel.objects.filter(email__iexact=identifier).only("username").first()
            if u:
                resolved_username = u.username
        else:
            u = UserModel.objects.filter(username__iexact=identifier).only("username").first()
            if u:
                resolved_username = u.username
            else:
                qs = UserModel.objects.filter(first_name__iexact=identifier).only("username")
                cnt = qs.count()
                if cnt == 1:
                    resolved_username = qs.first().username
                elif cnt > 1:
                    raise forms.ValidationError(self.error_messages["multiple_firstname"], code="multiple_firstname")

        user = authenticate(
            self.request,
            username=resolved_username or identifier,
            password=password,
        )
        if user is None:
            # Laat Django/two_factor flow lopen, maar met jouw NL tekst
            raise self.get_invalid_login_error()

        self.confirm_login_allowed(user)
        self.user_cache = user
        return self.cleaned_data

    def get_invalid_login_error(self):
        return forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")

class MyAuthenticationTokenForm(AuthenticationTokenForm):
    """
    Toon slechts 2 meldingen:
    - 'Voer 6 cijfers in.' (als niet exact 6 cijfers)
    - 'De code klopt niet. Probeer het nog een keer.' (als 6 cijfers maar onjuist)
    We gebruiken géén veldvalidatie; alles in clean() als non-field error.
    """

    # Gebruik een "platte" CharField zonder validators, zodat het veld zelf géén meldingen maakt.
    otp_token = forms.CharField(
        label=_("Token"),
        required=True,
        widget=forms.TextInput(attrs={
            'autofocus': 'autofocus',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autocomplete': 'one-time-code',
        }),
    )

    # Alleen voor consistentie; we gebruiken de dict zelf niet meer, omdat we eigen clean() doen.
    error_messages = {
        "invalid_token": _("De code klopt niet. Probeer het nog een keer."),
        "invalid_length": _("Voer 6 cijfers in."),
    }

    def clean(self):
        """
        1) Zelf checken op exact 6 cijfers → zo niet: één non-field error.
        2) Als wel 6 cijfers: OTP valideren via mixin → bij fout: één non-field error.
        """

        cleaned_data = super(forms.Form, self).clean()  # sla ouders over die velderrors toevoegen
        token = (self.data.get(self.add_prefix('otp_token')) or "").strip()

        # 1) Lengte + numeriek (samengevoegd tot één simpele melding)
        if not (token and token.isdigit() and len(token) == 6):
            raise ValidationError(self.error_messages["invalid_length"], code="invalid_length")

        # Zet het veld in cleaned_data (anders kan mixin klagen)
        cleaned_data['otp_token'] = token
        self.cleaned_data = cleaned_data

        # 2) OTP-check: als onjuist, vervang elke onderliggende boodschap door onze NL-melding
        try:
            # Dit komt uit OTPAuthenticationFormMixin
            self.clean_otp(self.user)
        except ValidationError:
            # Altijd dezelfde simpele boodschap teruggeven
            raise ValidationError(self.error_messages["invalid_token"], code="invalid_token")

        return self.cleaned_data

class MyTOTPDeviceForm(TOTPDeviceForm):
    # Alleen de boodschap aanpassen; verder 100% package-gedrag
    error_messages = {
        **TOTPDeviceForm.error_messages,
        "invalid_token": _("De code klopt niet. Probeer het nog een keer."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Je mag labels/attrs tweaken zonder de type/validatie te wijzigen
        self.fields["token"].label = _("Token")
        self.fields["token"].widget.attrs.update({
            "autofocus": "autofocus",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
        })

class AgendaItemForm(forms.ModelForm):
    date = forms.DateField(
        input_formats=["%d-%m-%Y"],
        widget=forms.TextInput(
            attrs={
                "class": "js-date",
                "placeholder": "dd-mm-jjjj",
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
    )

    # TimeFields met inputformat HH:MM
    start_time = forms.TimeField(
        required=False,
        input_formats=["%H:%M"],
        widget=forms.TextInput(
            attrs={
                "class": "js-time",
                "placeholder": "uu:mm",
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
        help_text="Optioneel: vul start- én eindtijd in. Laat leeg voor 'hele dag'.",
        label="Starttijd",
    )

    end_time = forms.TimeField(
        required=False,
        input_formats=["%H:%M"],
        widget=forms.TextInput(
            attrs={
                "class": "js-time",
                "placeholder": "uu:mm",
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
        help_text="Optioneel: vul start- én eindtijd in. Laat leeg voor 'hele dag'.",
        label="Eindtijd",
    )

    class Meta:
        model = AgendaItem
        fields = ["title", "description", "date", "start_time", "end_time"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.setdefault("placeholder", "Titel (max 50 karakters)")
        self.fields["description"].widget.attrs.setdefault("placeholder", "Korte beschrijving (max 100 karakters)")
        self.fields["description"].widget.attrs.setdefault("rows", 2)

        self.fields["title"].widget.attrs["maxlength"] = 50
        self.fields["description"].widget.attrs["maxlength"] = 100

        self.fields["title"].validators.append(MaxLengthValidator(50))
        self.fields["description"].validators.append(MaxLengthValidator(100))

    def clean_date(self):
        d = self.cleaned_data.get("date")
        if not d:
            return d

        today = timezone.localdate()
        if d < today:
            raise ValidationError("Datum mag niet in het verleden liggen.")
        return d

    # cross-field validatie
    def clean(self):
        cleaned = super().clean()
        st = cleaned.get("start_time")
        et = cleaned.get("end_time")

        if (st and not et) or (et and not st):
            raise ValidationError("Vul zowel een starttijd als eindtijd in (of laat beide leeg voor hele dag).")

        if st and et and st >= et:
            raise ValidationError("Eindtijd moet later zijn dan starttijd.")

        return cleaned

class NewsItemForm(forms.ModelForm):
    MAX_FILE_SIZE_MB = 25  # limiet gelijk aan nginx

    file = forms.FileField(
        label="Bestand (PDF of afbeelding)",
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png"])],
        required=False,
    )

    class Meta:
        model = NewsItem
        fields = ["title", "short_description", "description", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # === TITLE ===
        self.fields["title"].widget.attrs.update({
            "placeholder": "Titel (max 50 tekens)",
            "class": "form-input",
            "maxlength": "50",
        })
        self.fields["title"].validators.append(MaxLengthValidator(50))

        # === SHORT DESCRIPTION ===
        self.fields["short_description"].widget.attrs.update({
            "placeholder": "Korte beschrijving (max 100 tekens)",
            "class": "form-input",
            "maxlength": "100",
        })
        self.fields["short_description"].validators.append(MaxLengthValidator(100))

        # === DESCRIPTION (geen max nodig hier tenzij je dat wilt) ===
        self.fields["description"].widget.attrs.update({
            "placeholder": "Beschrijving",
            "class": "form-input",
            "rows": 2,
        })

        # === FILE ===
        self.fields["file"].widget.attrs.update({
            "accept": ".pdf,.jpg,.jpeg,.png",
        })

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if not f:
            return f

        max_bytes = self.MAX_FILE_SIZE_MB * 1024 * 1024
        if f.size > max_bytes:
            raise forms.ValidationError(
                f"Het bestand is te groot. Maximaal {self.MAX_FILE_SIZE_MB} MB toegestaan."
            )
        return f
    
class WerkafspraakForm(forms.ModelForm):
    MAX_FILE_SIZE_MB = 25  # limiet gelijk aan nginx

    file = forms.FileField(
        label="Bestand (PDF)",
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        required=False,
    )

    class Meta:
        model = Werkafspraak
        fields = ["title", "short_description", "category", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # === TITLE ===
        self.fields["title"].widget.attrs.update({
            "placeholder": "Titel (max 50 tekens)",
            "class": "form-input",
            "maxlength": "50",
        })
        self.fields["title"].validators.append(MaxLengthValidator(50))

        # === SHORT DESCRIPTION ===
        self.fields["short_description"].widget.attrs.update({
            "placeholder": "Korte beschrijving (max 100 tekens)",
            "class": "form-input",
            "maxlength": "100",
        })
        self.fields["short_description"].validators.append(MaxLengthValidator(100))

        # === CATEGORY ===
        self.fields["category"].widget.attrs.update({
            "class": "form-input",
        })

        # === FILE ===
        self.fields["file"].widget.attrs.update({
            "accept": ".pdf",
        })

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if not f:
            return f

        max_bytes = self.MAX_FILE_SIZE_MB * 1024 * 1024
        if f.size > max_bytes:
            raise forms.ValidationError(
                f"Het bestand is te groot. Maximaal {self.MAX_FILE_SIZE_MB} MB toegestaan."
            )
        return f

class OnboardingFormulierForm(forms.ModelForm):
    class Meta:
        model = OnboardingFormulier
        fields = ["title", "url"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.setdefault("placeholder", "Titel (max 80 karakters)")
        self.fields["url"].widget.attrs.setdefault("placeholder", "https://... (bij voorkeur verkorte link)")

        self.fields["title"].widget.attrs["maxlength"] = 80
        self.fields["url"].widget.attrs["maxlength"] = 500

        self.fields["title"].validators.append(MaxLengthValidator(80))

    def clean_url(self):
        url = (self.cleaned_data.get("url") or "").strip()
        if not url:
            return url

        # Maak het gebruiksvriendelijk: als iemand 'forms.gle/...' plakt, prepend https://
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Laat URLField de rest valideren, maar met nette foutmelding
        if " " in url:
            raise ValidationError("URL mag geen spaties bevatten.")
        return url

class InschrijvingItemForm(forms.ModelForm):
    verloopdatum = forms.DateField(
        required=False,
        input_formats=["%d-%m-%Y"],
        error_messages={"invalid": "Voer een geldige datum in (dd-mm-jjjj)."},
        help_text="Optioneel: na deze datum wordt dit item automatisch verwijderd.",
    )

    class Meta:
        model = InschrijvingItem
        fields = ["title", "url", "verloopdatum"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.setdefault("placeholder", "Titel (max 80 karakters)")
        self.fields["url"].widget.attrs.setdefault("placeholder", "https://... (bij voorkeur verkorte link)")
        self.fields["verloopdatum"].widget.attrs.setdefault("placeholder", "dd-mm-jjjj")

        self.fields["title"].widget.attrs["maxlength"] = 80
        self.fields["url"].widget.attrs["maxlength"] = 500

        self.fields["title"].validators.append(MaxLengthValidator(80))

    def clean_url(self):
        url = (self.cleaned_data.get("url") or "").strip()
        if not url:
            return url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if " " in url:
            raise ValidationError("URL mag geen spaties bevatten.")
        return url

class MedicatieReviewForm(forms.Form):
    
    afdeling_id = forms.ModelChoiceField(
        queryset=MedicatieReviewAfdeling.objects.none(), # Wordt in view gevuld
        required=True,
        widget=forms.Select(attrs={'class': 'form-control django-select2'})
    )
    
    BRON_CHOICES = [("medimo", "Medimo")]
    SCOPE_CHOICES = [("afdeling", "Volledige Afdeling")]#, ("patient", "Individuele Patiënt")

    source = forms.ChoiceField(
        choices=BRON_CHOICES, 
        initial="medimo",
        label="Bron (AIS)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    scope = forms.ChoiceField(
        choices=SCOPE_CHOICES, 
        initial="afdeling",
        label="Type Review",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    medimo_text = forms.CharField(
        label="Plak hier de tekst uit het geselecteerde AIS",
        widget=forms.Textarea(attrs={
            'class': 'form-input', 
            'rows': 12, 
            'placeholder': 'Kopieer de tekst van de afdeling en plak deze hier... Bijvoorbeeld:\n\nOverzicht medicatie Argusvlinder\nEen overzicht van alle actieve medicatie in afdeling Argusvlinder. Per patient wordt weergegeven of en zo ja welke geneesmiddelen deze mensen gebruiken.\n\n10 records in selectie\n________________________________________\nDhr. A Einstein (14-03-1879)\nC   Clozapine tablet 6,25mg	0-0-4 stuks, dagelijks, Continu\nEtc...'
        }),
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Vul de queryset zodat validatie werkt
        self.fields['afdeling_id'].queryset = MedicatieReviewAfdeling.objects.all()


class AfdelingEditForm(forms.ModelForm):
    class Meta:
        model = MedicatieReviewAfdeling
        fields = ['organisatie', 'afdeling', 'code', 'locatie', 'email', 'email2', 'telefoon']
        widgets = {
            'organisatie': forms.Select(attrs={'class': 'admin-input'}),
            'afdeling': forms.TextInput(attrs={'class': 'admin-input'}),
            'code': forms.TextInput(attrs={'class': 'admin-input'}),
            'locatie': forms.TextInput(attrs={'class': 'admin-input'}),
            'email': forms.EmailInput(attrs={'class': 'admin-input'}),
            'email2': forms.EmailInput(attrs={'class': 'admin-input'}),
            'telefoon': forms.TextInput(attrs={'class': 'admin-input'}),
        }
        labels = {
            'organisatie': 'Zorginstelling',
            'afdeling': 'Afdeling',
            'locatie': 'Locatie',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Basis: alleen zorginstellingen
        qs = Organization.objects.filter(
            org_type=Organization.ORG_TYPE_ZORGINSTELLING
        ).order_by('name')

        # Extra safety: als deze afdeling al gekoppeld is aan een andere org,
        # zorg dat die ook zichtbaar blijft in de dropdown, zodat je geen validation error krijgt.
        if self.instance and self.instance.pk and self.instance.organisatie_id:
            qs = Organization.objects.filter(pk=self.instance.organisatie_id) | qs
            qs = qs.distinct()

        self.fields['organisatie'].queryset = qs

        # Verplichte velden
        self.fields['organisatie'].required = True
        self.fields['afdeling'].required = True
        self.fields['locatie'].required = True

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "address", "color"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Bijv. Openbare Apotheek",
            }),
            "address": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "bijv. Liendertseweg 32, Amersfoort",
            }),
            "color": forms.Select(attrs={"class": "admin-select"}),
        }

STAFFING_FIELDS = [
    "min_mon_morning","min_mon_afternoon","min_mon_evening",
    "min_tue_morning","min_tue_afternoon","min_tue_evening",
    "min_wed_morning","min_wed_afternoon","min_wed_evening",
    "min_thu_morning","min_thu_afternoon","min_thu_evening",
    "min_fri_morning","min_fri_afternoon","min_fri_evening",
    "min_sat_morning","min_sat_afternoon","min_sat_evening",
]

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["name", "location", "description", *STAFFING_FIELDS]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Bijv. Ontstrippen",
            }),
            "location": forms.Select(attrs={
                "class": "admin-select",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 3,
                "placeholder": "Beschrijf hier kort wat de taak inhoudt...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # alle bezettingsvelden als integer inputs met jouw styling
        for f in STAFFING_FIELDS:
            self.fields[f].widget = forms.NumberInput(attrs={
                "class": "admin-input",
                "min": "0",
                "step": "1",
            })
            
class DagdeelForm(forms.ModelForm):
    # Forceer parsing van "HH:MM" (past perfect bij IMask)
    start_time = forms.TimeField(
        input_formats=["%H:%M"],
        widget=forms.TextInput(
            attrs={
                "class": "admin-input js-time",
                "type": "text",
                "inputmode": "numeric",
                "placeholder": "uu:mm",
                "autocomplete": "off",
            }
        ),
    )

    end_time = forms.TimeField(
        input_formats=["%H:%M"],
        widget=forms.TextInput(
            attrs={
                "class": "admin-input js-time",
                "type": "text",
                "inputmode": "numeric",
                "placeholder": "uu:mm",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = Dagdeel
        fields = ["start_time", "end_time", "allowance_pct"]
        widgets = {
            "allowance_pct": forms.NumberInput(
                attrs={
                    "class": "admin-input",
                    "min": "0",
                    "max": "300",
                    "step": "1",
                }
            ),
        }

class FunctionForm(forms.ModelForm):
    class Meta:
        model = Function
        fields = ["title", "ranking"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Bijv. Teamleider",
            }),
            "ranking": forms.NumberInput(attrs={
                "class": "admin-input",
                "min": "0",
                "step": "1",
                "placeholder": "0",
            }),
        }

class NazendingForm(forms.ModelForm):
    class Meta:
        model = Nazending
        fields = ['voorraad_item', 'datum', 'nazending_tot', 'alternatief']
        widgets = {
            'voorraad_item': forms.Select(attrs={
                'class': 'select2-single', 
                'style': 'width: 100%'
            }),
            'datum': forms.TextInput(attrs={
                'class': 'admin-input js-date', 
                'placeholder': 'dd-mm-jjjj'
            }),
            'nazending_tot': forms.TextInput(attrs={
                'class': 'admin-input',
                'placeholder': 'Bijvoorbeeld: "week 42", "UDH" of "onbekend"'
            }),
            'alternatief': forms.TextInput(attrs={
                'class': 'admin-input',
                'placeholder': 'Alternatief middel...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Zorg dat datum input dd-mm-yyyy accepteert
        self.fields['datum'].input_formats = ['%d-%m-%Y']
        # Queryset optimalisatie voor de dropdown
        self.fields['voorraad_item'].queryset = VoorraadItem.objects.all()

class LaatstePotForm(forms.ModelForm):
    class Meta:
        model = LaatstePot
        fields = ['voorraad_item', 'datum', 'afhandeling']  # <-- afhandeling toegevoegd
        widgets = {
            'voorraad_item': forms.Select(attrs={'class': 'select2-single', 'style': 'width: 100%'}),
            'datum': forms.TextInput(attrs={
                'class': 'admin-input js-date',
                'placeholder': 'dd-mm-jjjj'
            }),
            'afhandeling': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Hoe is dit afgehandeld?'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['datum'].input_formats = ['%d-%m-%Y']
        self.fields['voorraad_item'].queryset = VoorraadItem.objects.all()

        if not self.instance.pk:
            # Add-form: datum initialiseren + afhandeling niet tonen / niet invulbaar
            self.initial['datum'] = timezone.now().strftime('%d-%m-%Y')
            self.fields.pop('afhandeling', None)
        else:
            # Edit-form: afhandeling wél tonen
            self.fields['afhandeling'].label = "Afhandeling"

class STSHalfjeForm(forms.ModelForm):
    patient_geboortedatum_enc = forms.DateField(
        required=False,
        input_formats=["%d-%m-%Y"],
        widget=forms.DateInput(attrs={
            "placeholder": "dd-mm-jjjj",
            "class": "admin-input js-date",
            "autocomplete": "off",
        }),
        label="Geboortedatum",
    )

    class Meta:
        model = STSHalfje
        fields = [
            "apotheek",
            "patient_naam_enc",
            "patient_geboortedatum_enc",
            "item_gehalveerd",
            "item_alternatief",
        ]
        labels = {
            "patient_naam_enc": "Patiënt",
            "apotheek": "Apotheek",
        }
        widgets = {
            "patient_naam_enc": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Naam patiënt...",
                "autocomplete": "off",
            }),
            "item_gehalveerd": forms.Select(attrs={
                "class": "select2-single",
                "style": "width: 100%",
            }),
            "item_alternatief": forms.Select(attrs={
                "class": "select2-single",
                "style": "width: 100%",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item_gehalveerd"].queryset = VoorraadItem.objects.all()
        self.fields["item_alternatief"].queryset = VoorraadItem.objects.all()
        self.fields["apotheek"].queryset = Organization.objects.filter(
            org_type=Organization.ORG_TYPE_APOTHEEK
        ).order_by("name")
        
class NoDeliveryListForm(forms.ModelForm):
    class Meta:
        model = NoDeliveryList
        fields = ["apotheek", "jaar", "week", "dag"]
        labels = {
            "apotheek": "Apotheek",
            "jaar": "Jaar",
            "week": "Week",
            "dag": "Dag",
        }
        widgets = {
            "jaar": forms.NumberInput(attrs={
                "class": "admin-input",
                "placeholder": "2026",
                "min": 2000,
                "max": 2100,
            }),
            "week": forms.NumberInput(attrs={
                "class": "admin-input",
                "placeholder": "1-53",
                "min": 1,
                "max": 53,
            }),
            # dropdown
            "dag": forms.Select(attrs={
                "class": "admin-input",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["apotheek"].queryset = Organization.objects.filter(
            org_type=Organization.ORG_TYPE_APOTHEEK
        ).order_by("name")


class NoDeliveryEntryForm(forms.ModelForm):
    patient_geboortedatum_enc = forms.DateField(
        required=False,
        input_formats=["%d-%m-%Y"],
        widget=forms.DateInput(attrs={
            "placeholder": "dd-mm-jjjj",
            "class": "admin-input js-date",
            "autocomplete": "off",
        }),
        label="Geboortedatum",
    )

    vanaf_datum = forms.DateField(
        required=False,
        input_formats=["%d-%m-%Y"],
        widget=forms.DateInput(attrs={
            "placeholder": "dd-mm-jjjj",
            "class": "admin-input js-date",
            "autocomplete": "off",
        }),
        label="Vanaf datum",
    )

    class Meta:
        model = NoDeliveryEntry
        fields = [
            "afdeling",
            "patient_naam_enc",
            "patient_geboortedatum_enc",
            "gevraagd_geneesmiddel",
            "vanaf_datum",
            "sts_paraaf",
            "roller_paraaf",
        ]
        labels = {
            "patient_naam_enc": "Patiënt",
            "gevraagd_geneesmiddel": "Gevraagd geneesmiddel",
        }
        widgets = {
            "afdeling": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Afdeling...",
                "autocomplete": "off",
            }),
            "patient_naam_enc": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Naam patiënt...",
                "autocomplete": "off",
            }),
            "gevraagd_geneesmiddel": forms.Select(attrs={
                "class": "select2-single",
                "style": "width: 100%",
            }),
            "sts_paraaf": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Paraaf...",
                "autocomplete": "off",
            }),
            "roller_paraaf": forms.TextInput(attrs={
                "class": "admin-input",
                "placeholder": "Paraaf...",
                "autocomplete": "off",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # select2 ajax endpoint gebruikt /api/voorraad-zoeken/
        self.fields["gevraagd_geneesmiddel"].queryset = VoorraadItem.objects.all()

def _clean_1_decimal_decimal(v, label):
    if v in (None, ""):
        return None

    if isinstance(v, str):
        v = v.strip().replace(",", ".")
    try:
        d = Decimal(str(v))
    except Exception:
        raise ValidationError(f"{label} is ongeldig.")

    return d.quantize(Decimal("0.1"))


class UrenMaandForm(forms.ModelForm):
    class Meta:
        model = UrenMaand
        fields = ["kilometers"]
        widgets = {
            "kilometers": forms.NumberInput(attrs={
                "class": "admin-input",
                "inputmode": "numeric",
                "min": "0",
                "step": "1",
                "autocomplete": "off",
                "placeholder": "0",
            })
        }

    def clean_kilometers(self):
        v = self.cleaned_data.get("kilometers")
        if v is None:
            return 0
        if v < 0:
            raise ValidationError("Kilometers mogen niet negatief zijn.")
        return v


class Hours1DecimalField(forms.Form):
    hours = forms.CharField(required=False)

    def clean_hours(self):
        return _clean_1_decimal_decimal(self.cleaned_data.get("hours"), "Gewerkte uren")