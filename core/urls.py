from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload_roster, name="upload_roster"),
    path("users/", views.manage_users, name="manage_users"),
    path("hash/", views.hash_endpoint, name="hash"),
]

