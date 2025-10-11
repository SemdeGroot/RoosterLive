from django.urls import path
from .views import (
    home, login_view, logout_view,
    rooster, upload_roster,
    availability_home, availability_medications, availability_nazendingen,
    news, policies,
    admin_panel, group_delete, user_update, user_delete,
)

urlpatterns = [
    path("", home, name="home"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    path("rooster/", rooster, name="rooster"),
    path("rooster/upload/", upload_roster, name="upload_roster"),

    path("availability/", availability_home, name="availability_home"),
    path("availability/medications/", availability_medications, name="availability_medications"),
    path("availability/nazendingen/", availability_nazendingen, name="availability_nazendingen"),

    path("news/", news, name="news"),
    path("policies/", policies, name="policies"),

    path("beheer/", admin_panel, name="admin_panel"),
    path("beheer/group/<int:group_id>/delete/", group_delete, name="group_delete"),
    path("beheer/user/<int:user_id>/update/", user_update, name="user_update"),
    path("beheer/user/<int:user_id>/delete/", user_delete, name="user_delete")
]