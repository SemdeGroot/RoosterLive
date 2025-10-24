from django.urls import path
from django.views import View
from django.views.generic import RedirectView
from django.http import HttpResponse, HttpResponseNotFound
from django.contrib.staticfiles import finders
from django.templatetags.static import static

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
from core.views import push as push_views

class ServiceWorkerView(View):
    def get(self, request, *args, **kwargs):
        # zoekt: core/static/pwa/service-worker.js (via staticfiles)
        sw_path = finders.find('pwa/service-worker.js')
        if not sw_path:
            return HttpResponseNotFound('/* service-worker.js not found */')
        with open(sw_path, 'rb') as f:
            content = f.read()
        resp = HttpResponse(content, content_type='application/javascript')
        # laat de SW root-scope claimen
        resp['Service-Worker-Allowed'] = '/'
        # kleine cache-buster zodat updates snel door komen
        resp['Cache-Control'] = 'no-cache'
        return resp

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

    path("api/push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),

    path('service-worker.js', ServiceWorkerView.as_view(), name='service-worker'),
    
    path("favicon.ico", RedirectView.as_view(url=static("pwa/icons/favicon.ico"), permanent=False)),
    path("apple-touch-icon.png", RedirectView.as_view(url=static("pwa/icons/apple-touch-icon.png"), permanent=False)),
    path("apple-touch-icon-precomposed.png", RedirectView.as_view(url=static("pwa/icons/apple-touch-icon.png"), permanent=False)),

]
