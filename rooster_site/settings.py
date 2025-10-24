from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")
DEBUG = os.getenv("DEBUG", "True") == "True"

# ---- Proxy/HTTPS achter ngrok ----
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# ---- Hosts & CSRF (wildcards) ----
ALLOWED_HOSTS = [
    'localhost', '127.0.0.1',
    '.ngrok-free.dev', '.ngrok-free.app', '.ngrok.app',
]
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.dev',
    'https://*.ngrok-free.app',
    'https://*.ngrok.app',
]

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

# Media (uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CACHE_DIR = MEDIA_ROOT / "cache"     # rendered PNGs for roster
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- WebAuthn / Passkeys ---
# Gebruik ENV zodat je eenvoudig kunt wisselen tussen localhost en ngrok/productie
WEBAUTHN_RP_NAME = "Apotheek Jansen"
WEBAUTHN_RP_ID = "ngrok-free.dev" 

# Expected origin = scheme + host (+ optionele poort)
# Chrome accepteert http://localhost, iOS/Safari vereist https in het echt
WEBAUTHN_ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = False  # in dev via ngrok

# 24 uur sessie
SESSION_COOKIE_AGE = 60 * 60 * 24           # 1 dag
# Niet-persistente sessiecookie (logout bij sluiten browser/app*)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# (Optioneel) elke request verlengt de sessie → rolling window
SESSION_SAVE_EVERY_REQUEST = True