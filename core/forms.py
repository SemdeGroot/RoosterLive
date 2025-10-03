from django import forms
from django.contrib.auth.models import User, Group, Permission
from django.utils.text import slugify
from .models import Roster

class RosterUploadForm(forms.ModelForm):
    class Meta:
        model = Roster
        fields = ["title", "pdf"]
    def clean_pdf(self):
        f = self.cleaned_data["pdf"]
        if not f.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Upload een PDF-bestand.")
        return f

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    role = forms.ChoiceField(choices=[("Admin","Admin"), ("Manager","Manager"), ("Viewer","Viewer")])

    class Meta:
        model = User
        fields = ["username", "email", "password", "is_active"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # rol toewijzen via Groups
            role = self.cleaned_data["role"]
            for gname in ["Admin","Manager","Viewer"]:
                user.groups.remove(Group.objects.get_or_create(name=gname)[0])
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user

# ---- Simpele gebruiker toevoegen ----
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

        # username uit e-mail (voor '@'), fallback op slug van voornaam
        base = (email.split("@")[0] or slugify(first) or "user")[:150]
        username = base
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base}{i}"

        user = User.objects.create_user(username=username, email=email, password=password,
                                        first_name=first, is_active=True)
        user.groups.add(group)
        return user

# ---- Groep met checkbox-permissies ----
class GroupWithPermsForm(forms.ModelForm):
    # beheer
    can_access_admin         = forms.BooleanField(required=False, label="Mag beheer openen")
    can_manage_users         = forms.BooleanField(required=False, label="Mag gebruikers beheren")
    # rooster
    can_view_roster          = forms.BooleanField(required=False, label="Mag rooster bekijken")
    can_upload_roster        = forms.BooleanField(required=False, label="Mag roosters uploaden")
    # beschikbaarheid
    can_access_availability  = forms.BooleanField(required=False, label="Mag Beschikbaarheid openen")
    can_view_av_medications  = forms.BooleanField(required=False, label="Mag subtab Geneesmiddelen zien")
    can_view_av_nazendingen  = forms.BooleanField(required=False, label="Mag subtab Nazendingen zien")

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
        }
        if self.instance and self.instance.pk:
            current = set(self.instance.permissions.values_list("codename", flat=True))
            for field, perm in self.perm_map.items():
                self.fields[field].initial = (perm.codename in current)

    def save(self, commit=True):
        group = super().save(commit)
        chosen = [perm for field, perm in self.perm_map.items() if self.cleaned_data.get(field)]
        group.permissions.set(chosen)
        return group

class SimpleUserUpdateForm(forms.Form):
    first_name = forms.CharField(label="Voornaam", max_length=150, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    is_active = forms.BooleanField(label="Actief", required=False, initial=True)
    group = forms.ModelChoiceField(label="Groep", queryset=Group.objects.all(), empty_label=None)

    def __init__(self, *args, **kwargs):
        self.instance: User = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        # init met huidige waarden
        self.fields["first_name"].initial = self.instance.first_name
        self.fields["email"].initial = self.instance.email
        self.fields["is_active"].initial = self.instance.is_active
        # init group: kies eerste groep (of laat leeg als geen groep)
        g = self.instance.groups.first()
        if g:
            self.fields["group"].initial = g.id

    def save(self):
        u = self.instance
        # Basisgegevens (alleen invullen als opgegeven)
        fn = self.cleaned_data.get("first_name")
        em = self.cleaned_data.get("email")
        if fn is not None:
            u.first_name = fn
        if em:
            u.email = em
        u.is_active = bool(self.cleaned_data.get("is_active"))

        # Zet precies één gekozen groep (en haal andere weg)
        new_group: Group = self.cleaned_data["group"]
        u.groups.clear()
        if new_group:
            u.groups.add(new_group)
        u.save()
        return u