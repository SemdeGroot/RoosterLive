from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model, authenticate
from django.core.validators import FileExtensionValidator, MaxLengthValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .views._helpers import PERM_LABELS, PERM_SECTIONS

from two_factor.forms import AuthenticationTokenForm, TOTPDeviceForm 

from core.models import UserProfile, Organization, AgendaItem, NewsItem, Werkafspraak, MedicatieReviewAfdeling, Nazending, VoorraadItem, StandaardInlog

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


class SimpleUserEditForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150, required=True)
    last_name = forms.CharField(label="Achternaam", max_length=150, required=True)
    email = forms.EmailField(label="E-mail", required=True)
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

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)

        self.fields["first_name"].initial = self.instance.first_name or self.instance.username
        self.fields["last_name"].initial = self.instance.last_name
        self.fields["email"].initial = self.instance.email

        g = self.instance.groups.first()
        if g:
            self.fields["group"].initial = g.id

        profile = getattr(self.instance, "profile", None)
        if profile and profile.birth_date:
            self.fields["birth_date"].initial = profile.birth_date.strftime("%d-%m-%Y")
        if profile and profile.organization:
            self.fields["organization"].initial = profile.organization.id

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
        if UserModel.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Er bestaat al een gebruiker met dit e-mailadres.")
        return email

    def save(self):
        u = self.instance
        first = self.cleaned_data["first_name"]
        last = self.cleaned_data["last_name"]
        email = self.cleaned_data["email"]
        group = self.cleaned_data.get("group")
        birth_date = self.cleaned_data.get("birth_date")
        organization = self.cleaned_data.get("organization")

        u.username = email
        u.first_name = first
        u.last_name = last
        u.email = email
        u.save(update_fields=["username", "first_name", "last_name", "email"])

        profile, _ = UserProfile.objects.get_or_create(user=u)
        profile.birth_date = birth_date
        profile.organization = organization
        profile.save(update_fields=["birth_date", "organization"])

        u.groups.clear()
        if group:
            u.groups.add(group)
        return u
    
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

    class Meta:
        model = AgendaItem
        fields = ["title", "description", "date"]

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
        fields = ['organisatie', 'afdeling', 'locatie', 'email', 'email2', 'telefoon']
        widgets = {
            'organisatie': forms.Select(attrs={'class': 'admin-input'}),
            'afdeling': forms.TextInput(attrs={'class': 'admin-input'}),
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