from django import forms
from django.contrib.auth.models import Group, Permission, User
from django.utils.text import slugify
from django.core.validators import FileExtensionValidator
from django.contrib.contenttypes.models import ContentType

from .views._helpers import PERM_LABELS, PERM_SECTIONS


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
        #    NB: we gebruiken de labels uit PERM_LABELS
        for code, label in PERM_LABELS.items():
            self.fields[code] = forms.BooleanField(required=False, label=label)

        # 3) Initial waarden zetten als er een bestaande groep is
        if self.instance and self.instance.pk:
            current_codes = set(self.instance.permissions.values_list("codename", flat=True))
            for code in PERM_LABELS.keys():
                # initial True als deze permission in de groep zit
                self.fields[code].initial = (code in current_codes)

        # 4) Optioneel: secties doorgeven aan de form zelf, gefilterd op bestaande velden
        #    (handig als je in de template via form.sections wilt loopen)
        self.sections = [(title, [c for c in codes if c in self.fields]) for title, codes in PERM_SECTIONS]

    def save(self, commit=True):
        g = super().save(commit)
        # Verzamel alle gekozen codenames die we als veld hebben
        chosen_codes = [code for code in PERM_LABELS.keys() if self.cleaned_data.get(code)]
        # Converteer naar Permission objects; permissies die nog niet bestaan gewoon overslaan
        chosen_perms = [self.perm_map[code] for code in chosen_codes if code in self.perm_map]
        g.permissions.set(chosen_perms)
        return g


class SimpleUserCreateForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150)
    email = forms.EmailField(label="E-mail")
    password = forms.CharField(label="Wachtwoord", widget=forms.PasswordInput)
    group = forms.ModelChoiceField(label="Groep", queryset=Group.objects.all())

    def save(self):
        first = self.cleaned_data["first_name"].strip()
        email = self.cleaned_data["email"].lower().strip()
        password = self.cleaned_data["password"]
        group = self.cleaned_data["group"]

        base = slugify(first) or "user"
        username = base[:150]
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base}-{i}"[:150]

        u = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first, is_active=True
        )
        u.groups.add(group)
        return u


class SimpleUserEditForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150)
    email = forms.EmailField(label="E-mail")
    group = forms.ModelChoiceField(label="Groep", queryset=Group.objects.all(), empty_label=None)

    def __init__(self, *args, **kwargs):
        self.instance: User = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = self.instance.first_name or self.instance.username
        self.fields["email"].initial = self.instance.email
        g = self.instance.groups.first()
        if g:
            self.fields["group"].initial = g.id

    def save(self):
        u = self.instance
        first = self.cleaned_data["first_name"].strip()
        email = self.cleaned_data["email"].lower().strip()
        group = self.cleaned_data["group"]

        base = slugify(first) or "user"
        candidate = base[:150]
        if candidate != u.username:
            i = 1
            uname = candidate
            while User.objects.filter(username=uname).exclude(pk=u.pk).exists():
                i += 1
                uname = f"{base}-{i}"[:150]
            u.username = uname

        u.first_name = first
        u.email = email
        u.save()
        u.groups.clear()
        if group:
            u.groups.add(group)
        return u


class AvailabilityUploadForm(forms.Form):
    file = forms.FileField(label="Bestand (CSV of XLSX)", help_text="Upload een CSV of Excel-bestand.")
    limit = forms.IntegerField(label="Max. rijen", min_value=1, max_value=1000, initial=50, required=False)


class EmailOrUsernameLoginForm(forms.Form):
    identifier = forms.CharField(label="Gebruikersnaam of e-mail")
    password = forms.CharField(label="Wachtwoord", widget=forms.PasswordInput)

class RosterUploadForm(forms.Form):
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        allow_empty_file=False,
        label="Rooster (PDF)"
    )