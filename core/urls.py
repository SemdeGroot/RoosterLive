from django.urls import path
from django.views import View
from django.views.generic import RedirectView
from django.conf import settings

from core.views.home import home
from core.views.roster import rooster
from core.views.medications import medications_view
from core.views.nazendingen import nazendingen_view
from core.views.news import news
from core.views.policies import policies
from core.views.admin import admin_panel, group_delete, user_update, user_delete, org_delete, org_update
from core.views.twofa import logout_view
from core.views.mijnbeschikbaarheid import mijnbeschikbaarheid_view
from core.views.personeelsdashboard import personeelsdashboard_view
from core.views import push as push_views
from core.views.account import CustomPasswordConfirmView, CustomPasswordResetView
from core.views import agenda as agenda_views
from core.views import medicatiebeoordeling as medicatiebeoordeling_views
from core.views.personeel import personeel_tiles
from core.views.onboarding import onboarding_tiles
from core.views.whoiswho import whoiswho
from core.views.onboarding_forms import forms
from core.views.checklist import checklist
from core.views.baxter import baxter_tiles
from core.views.omzettingslijst import omzettingslijst
from core.views.no_delivery import no_delivery
from core.views.sts_halfjes import sts_halfjes
from core.views.laatste_potten import laatste_potten
from core.views.openbare import openbare_tiles
from core.views.instellings import instellings_tiles
from core.views.health import health
from core.views.passkeys import (
    PasskeySetupView,
    passkey_registration_options,
    passkey_register,
    passkey_password_login,
    passkey_authenticate,
    passkey_should_offer,
    passkey_skip,
)

urlpatterns = [
    path("", home, name="home"),
    path("personeel/", personeel_tiles, name="personeel_tiles"),
    path("onboarding/", onboarding_tiles, name="onboarding_tiles"),
    path("baxter/", baxter_tiles, name="baxter_tiles"),
    path("openbare-apotheek/", openbare_tiles, name="openbare_tiles"),
    path("instellingsapotheek/", instellings_tiles, name="instellings_tiles"),
    path("logout/", logout_view, name="logout"),
    path("accounts/password-reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path("accounts/set-password/<uidb64>/<token>/", CustomPasswordConfirmView.as_view(), name="set_password"),

    # Passkey setup pagina
        path(
        "account/passkeys/setup/",
        PasskeySetupView.as_view(),
        name="passkey_setup",
    ),

    # API: passkey registratie
    path(
        "api/passkeys/options/register/",
        passkey_registration_options,
        name="passkeys_options_register",
    ),
    path(
        "api/passkeys/register/",
        passkey_register,
        name="passkeys_register",
    ),

    # API: passkey login — LET OP: paden laten matchen met JS
    path(
        "api/passkeys/password-login/",
        passkey_password_login,
        name="passkeys_password_login",
    ),
    path(
        "api/passkeys/authenticate/",
        passkey_authenticate,
        name="passkeys_authenticate",
    ),

    # API: “eerste login op dit device, passkey aanbieden?”
    path(
        "api/passkeys/should-offer/",
        passkey_should_offer,
        name="passkeys_should_offer",
    ),

    # API: “Overslaan” op setup-pagina
    path(
        "api/passkeys/skip/",
        passkey_skip,
        name="passkeys_skip",
    ),

    path("health/", health, name="health"),

    path("agenda/", agenda_views.agenda, name="agenda"),

    path("rooster/", rooster, name="rooster"),

    path("beschikbaarheid/", mijnbeschikbaarheid_view, name="mijnbeschikbaarheid"),
    path("personeel/teamdashboard/", personeelsdashboard_view, name="beschikbaarheidpersoneel"),
    path("onboarding/wieiswie/", whoiswho, name="whoiswho"),
    path("onboarding/formulieren/", forms, name="forms"),
    path("onboarding/checklist/", checklist, name="checklist"),

    path("baxter/omzettingslijst/", omzettingslijst, name="baxter_omzettingslijst"),
    path("baxter/geen-levering/", no_delivery, name="baxter_no_delivery"),
    path("baxter/sts-halfjes/", sts_halfjes, name="baxter_sts_halfjes"),
    path("baxter/laatste-potten/", laatste_potten, name="baxter_laatste_potten"),

    path("baxter/voorraad/", medications_view, name="medications"),
    path("baxter/nazendingen/", nazendingen_view, name="nazendingen"),

    path("nieuws/", news, name="news"),
    path("werkafspraken/", policies, name="policies"),

    path("medicatiebeoordeling/", medicatiebeoordeling_views.medicatiebeoordeling, name="medicatiebeoordeling"),

    path("beheer/", admin_panel, name="admin_panel"),
    path("beheer/group/<int:group_id>/delete/", group_delete, name="group_delete"),
    path("beheer/user/<int:user_id>/update/", user_update, name="user_update"),
    path("beheer/user/<int:user_id>/delete/", user_delete, name="user_delete"),
    path("beheer/org/<int:org_id>/delete/", org_delete, name="org_delete"),
    path("beheer/org/<int:org_id>/update/", org_update, name="org_update"),

    path("api/push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
    
    path(
        "favicon.ico",
        RedirectView.as_view(
            url=f"{settings.STATIC_URL}pwa/icons/favicon.ico",
            permanent=False,
        ),
    ),
    path(
        "apple-touch-icon.png",
        RedirectView.as_view(
            url=f"{settings.STATIC_URL}pwa/icons/apple-touch-icon.v4.png",
            permanent=False,
        ),
    ),
    path(
        "apple-touch-icon-precomposed.png",
        RedirectView.as_view(
            url=f"{settings.STATIC_URL}pwa/icons/apple-touch-icon.v4.png",
            permanent=False,
        ),
    ),
]
