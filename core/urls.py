from django.urls import path
from django.views import View
from django.views.generic import RedirectView
from django.conf import settings

from core.views.home import home
from core.views.roster import rooster
from core.views.voorraad import medications_view
from core.views.nazendingen import nazendingen_view, medications_search_api, export_nazendingen_pdf, email_nazendingen_pdf
from core.views.news import news, news_media
from core.views.policies import policies, policies_media
from core.views.admin import admin_dashboard, admin_users, admin_groups, admin_orgs, group_delete, user_update, user_delete, org_delete, org_update, admin_afdelingen, delete_afdeling, afdeling_update
from core.views.twofa import logout_view, kiosk_login_view
from core.views.mijnbeschikbaarheid import mijnbeschikbaarheid_view
from core.views.personeelsdashboard import personeelsdashboard_view
from core.views import push as push_views
from core.views.account import CustomPasswordConfirmView, CustomPasswordResetView
from core.views import agenda as agenda_views
from core.views import medicatiebeoordeling as med_views
from core.views.export_review_pdf import export_patient_review_pdf, export_afdeling_review_pdf
from core.views import review_settings as med_settings
from core.views.personeel import personeel_tiles
from core.views.onboarding import onboarding_tiles
from core.views.whoiswho import whoiswho
from core.views.ziekmelden import ziekmelden
from core.views.urendoorgeven import urendoorgeven
from core.views.diensten import diensten
from core.views.onboarding_forms import forms
from core.views.checklist import checklist
from core.views.baxter import baxter_tiles
from core.views.omzettingslijst import omzettingslijst
from core.views.no_delivery import no_delivery
from core.views.stshalfjes import stshalfjes
from core.views.laatstepotten import laatstepotten
from core.views.openbare import openbare_tiles
from core.views.instellings import instellings_tiles
from core.views.reviewplanner import reviewplanner
from core.views.portavita import portavita_check
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
    path("kiosk-login/", kiosk_login_view, name="kiosk_login"),
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
    path("personeel/diensten/", diensten, name="diensten"),
    path("personeel/uren-doorgeven/", urendoorgeven, name="urendoorgeven"),
    path("personeel/ziek-melden/", ziekmelden, name="ziekmelden"),
    path("onboarding/wie-is-wie/", whoiswho, name="whoiswho"),
    path("onboarding/formulieren/", forms, name="forms"),
    path("onboarding/checklist/", checklist, name="checklist"),

    path("baxter/omzettingslijst/", omzettingslijst, name="baxter_omzettingslijst"),
    path("baxter/geen-levering/", no_delivery, name="baxter_no_delivery"),
    path("baxter/sts-halfjes/", stshalfjes, name="stshalfjes"),
    path("baxter/laatste-potten/", laatstepotten, name="laatstepotten"),

    path("baxter/voorraad/", medications_view, name="medications"),
    path("baxter/nazendingen/", nazendingen_view, name="nazendingen"),
    path('baxter/nazendingen/export-pdf', export_nazendingen_pdf, name='nazendingen_export_pdf'),
    path('baxter/nazendingen/email-pdf', email_nazendingen_pdf, name='nazendingen_email_pdf'),
    path('api/voorraad-zoeken/', medications_search_api, name='api_voorraad_zoeken'),

    path("nieuws/", news, name="news"),
    path("nieuws/media/<int:item_id>/", news_media, name="news_media"),
    path("werkafspraken/", policies, name="policies"),
    path("werkafspraken/media/<int:item_id>/", policies_media, name="policies_media"),
    # Tiles
    path("medicatiebeoordeling/", med_views.dashboard, name="medicatiebeoordeling_tiles"),
    # Genereren med review
    path("medicatiebeoordeling/genereren/", med_views.review_create, name="medicatiebeoordeling_create"),
    # Oude review openen
    path("medicatiebeoordeling/historie/", med_views.review_list, name="medicatiebeoordeling_list"),
    path("medicatiebeoordeling/search/", med_views.review_search_api, name="medicatiebeoordeling_search_api"),
    # med review settings aanpassen
    path("medicatiebeoordeling/instellingen/", med_settings.standaardvragen, name="medicatiebeoordeling_settings"),
    path("medicatiebeoordeling/api/atc-lookup/", med_settings.atc_lookup, name="api_atc_lookup"),
    # Details
    path("medicatiebeoordeling/afdeling/<int:pk>/", med_views.afdeling_detail, name="medicatiebeoordeling_afdeling_detail"),
    path("medicatiebeoordeling/patient/<int:pk>/", med_views.patient_detail, name="medicatiebeoordeling_patient_detail"),
    # Export pdf
    path("medicatiebeoordeling/patient/<int:pk>/export-pdf/", export_patient_review_pdf, name="medicatiebeoordeling_patient_export_pdf"),
    path("medicatiebeoordeling/afdeling/<int:pk>/export-pdf/", export_afdeling_review_pdf, name="medicatiebeoordeling_afdeling_export_pdf"),
    # Delete urls 
    path('afdeling/<int:pk>/clear/', med_views.clear_afdeling_review, name='medicatiebeoordeling_clear_afdeling'),
    path("medicatiebeoordeling/delete/patient/<int:pk>/", med_views.delete_patient, name="medicatiebeoordeling_delete_patient"),
    # Reviwiew planner
    path("reviewplanner/", reviewplanner, name="reviewplanner"),
    path("portavita-check/", portavita_check, name="portavita-check"),

        # Beheer Dashboard / Landing
        path("beheer/", admin_dashboard, name="beheer_tiles"),
        # De beheer paginas
        path("beheer/gebruikers/", admin_users, name="admin_users"),
        path("beheer/groepen/", admin_groups, name="admin_groups"),
        path("beheer/afdelingen/", admin_afdelingen, name="admin_afdelingen"),
        path("beheer/organisaties/", admin_orgs, name="admin_orgs"),
        # Acties (Delete/Update)
        path("beheer/group/<int:group_id>/delete/", group_delete, name="group_delete"),
        path("beheer/user/<int:user_id>/update/", user_update, name="user_update"),
        path("beheer/user/<int:user_id>/delete/", user_delete, name="user_delete"),
        path("beheer/afdeling/<int:pk>/delete/", delete_afdeling, name="delete_afdeling"),
        path("beheer/afdeling/<int:pk>/update/", afdeling_update, name="afdeling_update"),
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
