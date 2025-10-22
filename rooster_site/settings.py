from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "treasonably-noncerebral-samir.ngrok-free.dev"]
CSRF_TRUSTED_ORIGINS = ["https://treasonably-noncerebral-samir.ngrok-free.dev"]

VAPID_PUBLIC_KEY = "BLuUoPe86VS0fs2JyKKTNi2llpDso3tWd7CSxwZEOAoksOD9oUxxPA5pmrTZ8XUZYHS1A7RWmYc0Jnnf-nrYWrQ="
VAPID_PRIVATE_KEY = "ilECdajPSsDaev-gkhnlvm99dq3sjdRd1OlsSKTW0_Y="
VAPID_CLAIMS = {"sub": "mailto:semdegroot2003@gmail.com"}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "django_browser_reload",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

ROOT_URLCONF = "rooster_site.urls"
WSGI_APPLICATION = "rooster_site.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "core.context_processors.security_flags",
        ]},
    }
]

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

# Static (serve icons from data/)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "data"]

# Media (uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Convenience dirs
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR = MEDIA_ROOT / "cache"     # rendered PNGs for roster
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- WebAuthn / Passkeys ---
# Gebruik ENV zodat je eenvoudig kunt wisselen tussen localhost en ngrok/productie
WEBAUTHN_RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "Apotheek Jansen")

# RP ID = hostname (zonder schema en zonder poort)
# Voor dev is 'localhost' toegestaan als 'secure context'
WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")

# Expected origin = scheme + host (+ optionele poort)
# Chrome accepteert http://localhost, iOS/Safari vereist https in het echt
WEBAUTHN_ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")

# Cookies & security (zet deze aan in echte omgeving)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Houd Lax aan, dan werkt je app prima met standaard navigaties
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# In productie meestal True:
SECURE_SSL_REDIRECT = False if DEBUG else True
