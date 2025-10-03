from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload_roster, name="upload_roster"),
    path("adminx/", views.admin_panel, name="admin_panel"),
    path("adminx/user/<int:user_id>/update/", views.user_update, name="user_update"),
    path("adminx/user/<int:user_id>/delete/", views.user_delete, name="user_delete"),
    path("adminx/group/<int:group_id>/delete/", views.group_delete, name="group_delete"),

    # Beschikbaarheid
    path("beschikbaarheid/", views.availability_home, name="availability_home"),
    path("beschikbaarheid/geneesmiddelen/", views.availability_medications, name="availability_medications"),
    path("beschikbaarheid/nazendingen/", views.availability_nazendingen, name="availability_nazendingen"),

    path("hash/", views.hash_endpoint, name="hash"),
]
