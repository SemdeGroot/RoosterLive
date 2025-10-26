# core/views/twofa.py
from django.urls import reverse
from two_factor.views import SetupView

class CustomSetupView(SetupView):
    # sla welcome/method over
    condition_dict = {"welcome": False, "method": False}

    def get(self, request, *args, **kwargs):
        self.storage.current_step = "generator"
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.storage.current_step in (None, "welcome", "method"):
            self.storage.current_step = "generator"
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("home")  # of jouw dashboard
