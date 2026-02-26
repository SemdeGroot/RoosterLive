from django.urls import path
from django.views import View
from django.views.generic import RedirectView
from django.conf import settings

from core.views.home import home
from core.views.roster import rooster
from core.views.voorraad import medications_view, email_voorraad_html, export_voorraad_html
from core.views.nazendingen import nazendingen_view, medications_search_api, export_nazendingen_pdf, email_nazendingen_pdf
from core.views.news import news, news_media
from core.views.policies import policies, policies_media
from core.views.admin import admin_dashboard, admin_users, admin_groups, admin_orgs, group_delete, user_update, user_delete, org_delete, org_update, admin_afdelingen, delete_afdeling, afdeling_update, admin_taken,  location_update, task_update, delete_location, delete_task, admin_functies, functie_update, delete_functie, admin_bezorgen, dagdeel_update, user_resend_invite
from core.views.profiel import profiel_index, avatar_upload, avatar_remove, profiel_update_settings
from core.views.twofa import logout_view, kiosk_login_view
from core.views.mijnbeschikbaarheid import mijnbeschikbaarheid_view
from core.views.personeelsdashboard import personeelsdashboard_view, save_concept_shifts_api, delete_shift_api, publish_shifts_api
from core.views import push as push_views
from core.views.push_native import native_push_subscribe, native_push_unsubscribe
from core.views.account import CustomPasswordConfirmView, CustomPasswordResetView
from core.views import agenda as agenda_views
from core.views import medicatiebeoordeling as med_views
from core.views.export_review_pdf import export_afdeling_review_pdf
from core.views import review_settings as med_settings
from core.views.personeel import personeel_tiles
from core.views.onboarding import onboarding_tiles
from core.views.whoiswho import whoiswho
from core.views.inschrijven import inschrijvingen
from core.views.ziekmelden import ziekmelden
from core.views.urendoorgeven import urendoorgeven_view
from core.views.diensten import mijndiensten_view
from core.views.diensten_webcal import diensten_webcal_view
from core.views.onboarding_forms import onboarding_formulieren
from core.views.checklist import checklist
from core.views.baxter import baxter_tiles
from core.views.statistieken import statistieken_tiles
from core.views.machine_statistieken import machine_statistieken_ingest,machine_statistieken_view, machine_statistieken_api_vandaag,machine_statistieken_api_geschiedenis
from core.views.omzettingslijst import omzettingslijst, api_omzettingslijsten, export_omzettingslijst_pdf, email_omzettingslijst_pdf, export_omzettingslijst_label_pdf
from core.views.no_delivery import no_delivery, api_no_delivery_lists, export_no_delivery_pdf, email_no_delivery_pdf, export_no_delivery_label_pdf
from core.views.stshalfjes import stshalfjes, export_stshalfjes_pdf, email_stshalfjes_pdf
from core.views.laatstepotten import laatstepotten
from core.views.openbare import openbare_tiles
from core.views.instellings import instellings_tiles
from core.views.reviewplanner import reviewplanner, reviewplanner_export_overview
from core.views.portavita import portavita_check
from core.views.houdbaarheidcheck import houdbaarheidcheck
from core.views.health import health
from core.views.passkeys import PasskeySetupView, passkey_registration_options,passkey_register, passkey_password_login, passkey_authenticate,passkey_should_offer, passkey_skip, passkey_login_options
from core.views.native_biometric import native_biometric_enable,native_biometric_login, native_biometric_revoke, native_biometric_skip, native_biometric_password_login
from core.views.bezorgers import bezorgers_tiles, bakkenbezorgen, afleverstatus
from core.views.kompasgpt import kompasgpt

urlpatterns = [
    path("", home, name="home"),
    path("personeel/", personeel_tiles, name="personeel_tiles"),
    path("onboarding/", onboarding_tiles, name="onboarding_tiles"),
    path("baxter/", baxter_tiles, name="baxter_tiles"),
    path("statistieken/", statistieken_tiles, name="statistieken_tiles"),
    path("openbare-apotheek/", openbare_tiles, name="openbare_tiles"),
    path("instellingsapotheek/", instellings_tiles, name="instellings_tiles"),
    path("kiosk-login/", kiosk_login_view, name="kiosk_login"),
    path("logout/", logout_view, name="logout"),
    path("accounts/password-reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path("accounts/set-password/<uidb64>/<token>/", CustomPasswordConfirmView.as_view(), name="set_password"),

    # Passkey setup pagina
    path("account/passkeys/setup/", PasskeySetupView.as_view(),name="passkey_setup"),
    # API: passkey registratie
    path("api/passkeys/options/register/", passkey_registration_options,name="passkeys_options_register"),
    path("api/passkeys/register/", passkey_register, name="passkeys_register"),
    # API: passkey login — LET OP: paden laten matchen met JS
    path("api/passkeys/password-login/", passkey_password_login,name="passkeys_password_login"),
    path("api/passkeys/authenticate/", passkey_authenticate, name="passkeys_authenticate"),
    # API: “eerste login op dit device, passkey aanbieden?”
    path("api/passkeys/should-offer/", passkey_should_offer,name="passkeys_should_offer"),
    path("api/passkeys/login/options/", passkey_login_options, name="passkeys_login_options"),
    # API: “Overslaan” op setup-pagina
    path("api/passkeys/skip/", passkey_skip, name="passkeys_skip"),
    # Native biometric
    path("api/native-biometrics/enable/", native_biometric_enable, name="native_biometric_enable"),
    path("api/native-biometrics/login/", native_biometric_login, name="native_biometric_login"),
    path("api/native-biometrics/revoke/", native_biometric_revoke, name="native_biometric_revoke"),
    path("api/native-biometrics/skip/", native_biometric_skip, name="native_bio_skip"),
    path("api/native-biometrics/password-login/", native_biometric_password_login, name="native_bio_password_login"),

    path("health/", health, name="health"),

    path("agenda/", agenda_views.agenda, name="agenda"),

    path("rooster/", rooster, name="rooster"),

    path("beschikbaarheid/", mijnbeschikbaarheid_view, name="mijnbeschikbaarheid"),
    path("personeel/teamdashboard/", personeelsdashboard_view, name="beschikbaarheidpersoneel"),
    path("personeel/teamdashboard/api/save-concept/", save_concept_shifts_api, name="pd_save_concept"),
    path("personeel/teamdashboard/api/delete-shift/", delete_shift_api, name="pd_delete_shift"),
    path("personeel/teamdashboard/api/publish/", publish_shifts_api, name="pd_publish_shifts"),
    path("personeel/diensten/", mijndiensten_view, name="mijndiensten"),
    path("diensten/webcal/<uuid:token>.ics", diensten_webcal_view, name="diensten_webcal"),
    path("personeel/uren-doorgeven/", urendoorgeven_view, name="urendoorgeven"),
    path("personeel/ziek-melden/", ziekmelden, name="ziekmelden"),
    path("personeel/inschrijven/", inschrijvingen, name="inschrijvingen"),
    path("onboarding/team/", whoiswho, name="whoiswho"),
    path("onboarding/formulieren/", onboarding_formulieren, name="onboarding_formulieren"),
    path("onboarding/checklist/", checklist, name="checklist"),

    path("baxter/machine-statistieken/",                       machine_statistieken_view,             name="machine_statistieken"),
    path("api/baxter/machine-statistieken/ingest/",           machine_statistieken_ingest,            name="machine_statistieken_ingest"),
    path("baxter/machine-statistieken/api/vandaag/",          machine_statistieken_api_vandaag,       name="machine_statistieken_api_vandaag"),
    path("baxter/machine-statistieken/api/geschiedenis/",     machine_statistieken_api_geschiedenis,  name="machine_statistieken_api_geschiedenis"),
    path("baxter/omzettingslijst/", omzettingslijst, name="baxter_omzettingslijst"),
    path("api/omzettingslijsten/", api_omzettingslijsten, name="api_omzettingslijsten"),
    path("baxter/omzettingslijst/export-pdf/", export_omzettingslijst_pdf, name="export_omzettingslijst_pdf"),
    path("baxter/omzettingslijst/email/", email_omzettingslijst_pdf, name="email_omzettingslijst_pdf"),
    path("omzettingslijst/label/<int:entry_id>/", export_omzettingslijst_label_pdf, name="export_omzettingslijst_label_pdf"),
    path("baxter/geen-levering/", no_delivery, name="baxter_no_delivery"),
    path("api/no-delivery-lists/", api_no_delivery_lists, name="api_no_delivery_lists"),
    path("baxter/geen-levering/export-pdf/", export_no_delivery_pdf, name="export_no_delivery_pdf"),
    path("baxter/geen-levering/email/", email_no_delivery_pdf, name="email_no_delivery_pdf"),
    path("no-delivery/label/<int:entry_id>/", export_no_delivery_label_pdf,name="export_no_delivery_label_pdf"),
    path("baxter/sts-halfjes/", stshalfjes, name="stshalfjes"),
    path("baxter/sts-halfjes/export-pdf/", export_stshalfjes_pdf, name="export_stshalfjes_pdf"),
    path("baxter/sts-halfjes/email-pdf/", email_stshalfjes_pdf, name="email_stshalfjes_pdf"),
    path("baxter/laatste-potten/", laatstepotten, name="laatstepotten"),

    path("baxter/voorraad/", medications_view, name="medications"),
    path("baxter/voorraad/export-html/", export_voorraad_html, name="voorraad_export_html"),
    path("baxter/voorraad/email-html/", email_voorraad_html, name="voorraad_email_html"),
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
    path("medicatiebeoordeling/afdeling/<int:pk>/export-pdf/", export_afdeling_review_pdf, name="medicatiebeoordeling_afdeling_export_pdf"),
    # Delete urls 
    path('afdeling/<int:pk>/clear/', med_views.clear_afdeling_review, name='medicatiebeoordeling_clear_afdeling'),
    path("medicatiebeoordeling/delete/patient/<int:pk>/", med_views.delete_patient, name="medicatiebeoordeling_delete_patient"),
    # Reviwiew planner
    path("instellingsapotheek/review-planner/", reviewplanner, name="reviewplanner"),
    path("instellingsapotheek/review-planner/export-overview/", reviewplanner_export_overview, name="reviewplanner_export_overview"),
    path("portavita-check/", portavita_check, name="portavita-check"),
    path("houdbaarheidscheck/", houdbaarheidcheck, name="houdbaarheidcheck"),
    # Profiel
    path("profiel/", profiel_index, name="profiel"),
    path("profiel/avatar/upload/", avatar_upload, name="profiel_avatar_upload"),
    path("profiel/avatar/remove/", avatar_remove, name="profiel_avatar_remove"),
    path("profiel/settings/update/", profiel_update_settings, name="profiel_settings_update"),
    # Bezorgers
    path("bezorgers/", bezorgers_tiles, name="bezorgers_tiles"),
    path("bezorgers/bakken-bezorgen", bakkenbezorgen, name="bakkenbezorgen"),
    path("bezorgers/afleverstatus", afleverstatus, name="afleverstatus"),
    # Beheer Dashboard / Landing
    path("beheer/", admin_dashboard, name="beheer_tiles"),
    # De beheer paginas
    path("beheer/gebruikers/", admin_users, name="admin_users"),
    path("beheer/groepen/", admin_groups, name="admin_groups"),
    path("beheer/afdelingen/", admin_afdelingen, name="admin_afdelingen"),
    path("beheer/organisaties/", admin_orgs, name="admin_orgs"),
    path("beheer/taken/", admin_taken, name="admin_taken"),
    path("beheer/functies/", admin_functies, name="admin_functies"),
    path("beheer/bezorgen/", admin_bezorgen, name="admin_bezorgen"),
    # Acties (Delete/Update)
    path("beheer/group/<int:group_id>/delete/", group_delete, name="group_delete"),
    path("beheer/user/<int:user_id>/update/", user_update, name="user_update"),
    path("beheer/user/<int:user_id>/delete/", user_delete, name="user_delete"),
    path("beheer/users/<int:user_id>/resend-invite/", user_resend_invite, name="user_resend_invite"),
    path("beheer/afdeling/<int:pk>/delete/", delete_afdeling, name="delete_afdeling"),
    path("beheer/afdeling/<int:pk>/update/", afdeling_update, name="afdeling_update"),
    path("beheer/org/<int:org_id>/delete/", org_delete, name="org_delete"),
    path("beheer/org/<int:org_id>/update/", org_update, name="org_update"),
    path("beheer/taken/location/<int:pk>/update/", location_update, name="location_update"),
    path("beheer/taken/task/<int:pk>/update/", task_update, name="task_update"),
    path("beheer/taken/location/<int:pk>/delete/", delete_location, name="delete_location"),
    path("beheer/taken/task/<int:pk>/delete/", delete_task, name="delete_task"),
    path("beheer/functies/<int:pk>/update/", functie_update, name="functie_update"),
    path("beheer/functies/<int:pk>/delete/", delete_functie, name="delete_functie"),
    path("beheer/dagdelen/<str:code>/update/", dagdeel_update, name="dagdeel_update"),
    # KompasGPT
    path("apotheekgpt/", kompasgpt, name="kompasgpt"),

    path("api/push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
    path("api/push/native/subscribe/", native_push_subscribe, name="native_push_subscribe"),
    path("api/push/native/unsubscribe/", native_push_unsubscribe, name="native_push_unsubscribe"),
    
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
