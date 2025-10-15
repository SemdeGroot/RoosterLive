from django.urls import path
from core.views.home import home
from core.views.roster import rooster, upload_roster
from core.views.medications import medications_view
from core.views.nazendingen import nazendingen_view
from core.views.news import news
from core.views.policies import policies
from core.views.admin import admin_panel, group_delete, user_update, user_delete
from core.views.auth import login_view, logout_view
from core.views.mijnbeschikbaarheid import mijnbeschikbaarheid_view
from core.views.personeelsdashboard import personeelsdashboard_view

urlpatterns = [
    path("", home, name="home"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    path("rooster/", rooster, name="rooster"),
    path("rooster/upload/", upload_roster, name="upload_roster"),

    path("beschikbaarheid/", mijnbeschikbaarheid_view, name="mijnbeschikbaarheid"),
    path("teamdashboard/", personeelsdashboard_view, name="beschikbaarheidpersoneel"),

    path("voorraad/", medications_view, name="medications"),
    path("nazendingen/", nazendingen_view, name="nazendingen"),

    path("nieuws/", news, name="news"),
    path("werkafspraken/", policies, name="policies"),

    path("beheer/", admin_panel, name="admin_panel"),
    path("beheer/group/<int:group_id>/delete/", group_delete, name="group_delete"),
    path("beheer/user/<int:user_id>/update/", user_update, name="user_update"),
    path("beheer/user/<int:user_id>/delete/", user_delete, name="user_delete"),
]
