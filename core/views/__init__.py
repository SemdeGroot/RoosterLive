# core/views/__init__.py
from .auth import login_view, logout_view
from .home import home
from .roster import rooster, upload_roster
from .availability import availability_home, availability_medications, availability_nazendingen
from .news import news
from .policies import policies
from .admin import admin_panel, group_delete, user_update, user_delete

__all__ = [
    "login_view", "logout_view",
    "home",
    "rooster", "upload_roster",
    "availability_home", "availability_medications", "availability_nazendingen",
    "news",
    "policies",
    "admin_panel", "group_delete", "user_update", "user_delete",
]
