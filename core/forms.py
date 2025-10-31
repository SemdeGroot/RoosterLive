from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model, authenticate
from django.core.validators import FileExtensionValidator
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from .views._helpers import PERM_LABELS, PERM_SECTIONS

from two_factor.forms import AuthenticationTokenForm, TOTPDeviceForm 

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


class SimpleUserCreateForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150)
    email = forms.EmailField(label="E-mail")
    group = forms.ModelChoiceField(
        label="Groep",
        queryset=Group.objects.all(),
        required=False,
        empty_label="----------",
    )

    def clean_first_name(self):
        # Consistent in lowercase opslaan
        first = (self.cleaned_data.get("first_name") or "").strip().lower()
        if not first:
            raise forms.ValidationError("Voornaam is verplicht.")
        return first

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("E-mail is verplicht.")
        # Unieke e-mail afdwingen (case-insensitive)
        if UserModel.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Er bestaat al een gebruiker met dit e-mailadres.")
        return email


class SimpleUserEditForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150)
    email = forms.EmailField(label="E-mail")
    group = forms.ModelChoiceField(
        label="Groep",
        queryset=Group.objects.all(),
        required=False,
        empty_label="----------",
    )

    def __init__(self, *args, **kwargs):
        # instance = een instance van het actieve user model
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)

        self.fields["first_name"].initial = self.instance.first_name or self.instance.username
        self.fields["email"].initial = self.instance.email
        g = self.instance.groups.first()
        if g:
            self.fields["group"].initial = g.id

    def clean_first_name(self):
        # Consistent in lowercase opslaan
        first = (self.cleaned_data.get("first_name") or "").strip().lower()
        if not first:
            raise forms.ValidationError("Voornaam is verplicht.")
        return first

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        # Unieke e-mail, behalve voor jezelf
        if UserModel.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Er bestaat al een gebruiker met dit e-mailadres.")
        return email

    def save(self):
        u = self.instance
        first = self.cleaned_data["first_name"]          # al lowercase via clean_first_name
        email = self.cleaned_data["email"]               # al lowercase via clean_email
        group = self.cleaned_data.get("group")

        # Username blijft ALTIJD gelijk aan email (lowercase)
        u.username = email
        u.first_name = first
        u.email = email
        u.save(update_fields=["username", "first_name", "email"])

        # Groep bijwerken (optioneel)
        u.groups.clear()
        if group:
            u.groups.add(group)
        return u


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
    """
    Setup-stap (generator): toon maar 2 meldingen.
    - 'Voer 6 cijfers in.' (leeg/te kort/lang/niet numeriek)
    - 'De code klopt niet. Probeer het nog een keer.' (6 cijfers maar OTP fout)
    """
    # Vervang het veld door een kale CharField zonder validators
    token = forms.CharField(
        label=_("Token"),
        required=True,
        widget=forms.TextInput(attrs={
            'autofocus': 'autofocus',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autocomplete': 'one-time-code',
        }),
    )

    error_messages = {
        "invalid_length": _("Voer 6 cijfers in."),
        "invalid_token":  _("De code klopt niet. Probeer het nog een keer."),
    }

    def clean(self):
        """
        1) Zelf 6-cijfer check
        2) Daarna OTP-valideren met dezelfde logica als parent (clean_token),
           maar map elke fout naar 1 uniforme melding.
        """
        # Sla field-level validators van parent over:
        cleaned = super(forms.Form, self).clean()

        raw = (self.data.get(self.add_prefix('token')) or "").strip()
        if not (raw.isdigit() and len(raw) == 6):
            raise ValidationError(self.error_messages["invalid_length"], code="invalid_length")

        # Zet token in cleaned_data zodat parent clean_token 'm pakt
        self.cleaned_data = cleaned
        self.cleaned_data['token'] = int(raw)

        # Gebruik de bestaande OTP-logica van TOTPDeviceForm.clean_token(),
        # maar map elke fout op onze ene boodschap:
        try:
            self.clean_token()  # roept de TOTP-check aan; zet evt. drift/metadata
        except ValidationError:
            raise ValidationError(self.error_messages["invalid_token"], code="invalid_token")

        return self.cleaned_data