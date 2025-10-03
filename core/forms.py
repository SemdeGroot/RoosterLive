from django import forms
from django.contrib.auth.models import Group, Permission, User
from django.utils.text import slugify

class GroupWithPermsForm(forms.ModelForm):
    # Beheer
    can_access_admin         = forms.BooleanField(required=False, label="Mag beheer openen")
    can_manage_users         = forms.BooleanField(required=False, label="Mag gebruikers beheren")
    # Rooster
    can_view_roster          = forms.BooleanField(required=False, label="Mag rooster bekijken")
    can_upload_roster        = forms.BooleanField(required=False, label="Mag roosters uploaden")
    # Beschikbaarheid
    can_access_availability  = forms.BooleanField(required=False, label="Mag Beschikbaarheid openen")
    can_view_av_medications  = forms.BooleanField(required=False, label="Mag subtab Geneesmiddelen zien")
    can_view_av_nazendingen  = forms.BooleanField(required=False, label="Mag subtab Nazendingen zien")
    # Nieuwe tabs
    can_view_news            = forms.BooleanField(required=False, label="Mag Nieuws bekijken")
    can_view_policies        = forms.BooleanField(required=False, label="Mag Werkafspraken bekijken")

    class Meta:
        model = Group
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        perms_qs = Permission.objects.filter(content_type__app_label="core")
        self.perm_map = {
            "can_access_admin":        perms_qs.get(codename="can_access_admin"),
            "can_manage_users":        perms_qs.get(codename="can_manage_users"),
            "can_view_roster":         perms_qs.get(codename="can_view_roster"),
            "can_upload_roster":       perms_qs.get(codename="can_upload_roster"),
            "can_access_availability": perms_qs.get(codename="can_access_availability"),
            "can_view_av_medications": perms_qs.get(codename="can_view_av_medications"),
            "can_view_av_nazendingen": perms_qs.get(codename="can_view_av_nazendingen"),
            "can_view_news":           perms_qs.get(codename="can_view_news"),
            "can_view_policies":       perms_qs.get(codename="can_view_policies"),
        }
        if self.instance and self.instance.pk:
            current = set(self.instance.permissions.values_list("codename", flat=True))
            for field, perm in self.perm_map.items():
                self.fields[field].initial = (perm.codename in current)

    def save(self, commit=True):
        g = super().save(commit)
        chosen = [perm for field, perm in self.perm_map.items() if self.cleaned_data.get(field)]
        g.permissions.set(chosen)
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
