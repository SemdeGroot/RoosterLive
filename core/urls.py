from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("rooster/", views.rooster, name="rooster"),

    path("beschikbaarheid/", views.availability_home, name="availability_home"),
    path("beschikbaarheid/voorraad/", views.availability_medications, name="availability_medications"),
    path("beschikbaarheid/nazendingen/", views.availability_nazendingen, name="availability_nazendingen"),

    path("nieuws/", views.news, name="news"),
    path("werkafspraken/", views.policies, name="policies"),
    path("werkafspraken/delete-page/", views.policies_delete_page, name="policies_delete_page"),

    path("beheer/", views.admin_panel, name="admin_panel"),
    path("beheer/user/<int:user_id>/update/", views.user_update, name="user_update"),
    path("beheer/user/<int:user_id>/delete/", views.user_delete, name="user_delete"),
    path("beheer/group/<int:group_id>/delete/", views.group_delete, name="group_delete"),

    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout")
]