from django import forms
from django.contrib.auth.models import User, Group
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
