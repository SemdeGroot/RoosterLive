from .auth import login_view, logout_view
from .home import home
from .roster import rooster, upload_roster
from .medications import medications_view
from .nazendingen import nazendingen_view
from .news import news
from .policies import policies
from .admin import admin_panel, group_delete, user_update, user_delete

__all__ = [
    "login_view", "logout_view",
    "home",
    "rooster", "upload_roster",
    "medications_view", "nazendingen_view",
    "news",
    "policies",
    "admin_panel", "group_delete", "user_update", "user_delete",
]
