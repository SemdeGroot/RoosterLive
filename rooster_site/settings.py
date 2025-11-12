from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # lokaal .env; in prod zet je env via Parameter Store

# ---------- Helpers ----------
def csv_env(name, default=""):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

DEBUG = os.getenv("DEBUG", "True") == "True"

def pick(prod_key, dev_key, default=None):
    """Kies PROD_* (prod) of DEV_* (dev) waarde op basis van DEBUG."""
    return os.getenv(prod_key if not DEBUG else dev_key, default)

# ---------- Secret ----------
SECRET_KEY = os.getenv("SECRET_KEY")

# ---------- Proxy/HTTPS ----------
# Laat Django weten dat we soms achter een proxy/NGINX/ALB zitten
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ---------- Domein/Hosts/CSRF ----------
SITE_DOMAIN = pick("PROD_SITE_DOMAIN", "DEV_SITE_DOMAIN", "http://127.0.0.1:8000")
ALLOWED_HOSTS = csv_env(pick("PROD_ALLOWED_HOSTS", "DEV_ALLOWED_HOSTS", "127.0.0.1,localhost"))
CSRF_TRUSTED_ORIGINS = csv_env(pick("PROD_CSRF_TRUSTED_ORIGINS", "DEV_CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:8000"))

# Zonder HTTPS (IP in prod) wil je cookies NIET secure forceren:
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False  # zet True zodra je echt TLS aan de voorkant hebt
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ---------- Apps ----------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "core",

    # Optional dev tooling
    "django_browser_reload",

    # 2FA / OTP
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "two_factor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static optimalisatie
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "two_factor.middleware.threadlocals.ThreadLocals",
    "core.middleware.Enforce2FAMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Alleen in DEBUG de browser-reload middleware bijladen
if DEBUG:
    MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")

ROOT_URLCONF = "rooster_site.urls"
WSGI_APPLICATION = "rooster_site.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# ---------- Database ----------
# Gebruik DATABASE_URL varianten wanneer aanwezig (prod ↔ dev), anders SQLite fallback.
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}
_prod_db = os.getenv("PROD_DATABASE_URL")
_dev_db = os.getenv("DEV_DATABASE_URL")
if (not DEBUG and _prod_db) or (DEBUG and _dev_db):
    try:
        import dj_database_url
        DATABASES = {
            "default": dj_database_url.parse(_prod_db if not DEBUG else _dev_db, conn_max_age=600 if not DEBUG else 0)
        }
    except Exception:
        # dj-database-url niet geïnstalleerd of parse error -> blijf op SQLite
        pass

# ---------- Redis / Cache / Sessions ----------
REDIS_URL = pick("PROD_REDIS_URL", "DEV_REDIS_URL")
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ---------- Celery ----------
CELERY_BROKER_URL = pick("PROD_CELERY_BROKER_URL", "DEV_CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = pick("PROD_CELERY_RESULT_BACKEND", "DEV_CELERY_RESULT_BACKEND")

CELERY_TASK_ALWAYS_EAGER = False  # True = sync testen (dev-only)
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_SOFT_TIME_LIMIT = 50
CELERY_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "core.tasks.send_invite_email_task": {"queue": "mail"},
    "core.tasks.send_roster_updated_push_task": {"queue": "push"},
}

# ---------- Auth / Passwords ----------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/account/login/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- Static & Media ----------
# WhiteNoise optimalisatie + hashed filenames
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CACHE_DIR = MEDIA_ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Sessies ----------
# 8 uur sessie, niet persistent bij sluiten
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# ---------- Email ----------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ---------- Links in mail ----------
# In prod stel je een echte https domein in; nu mag het IP/http zijn
USE_HTTPS_IN_EMAIL_LINKS = not DEBUG
SITE_DOMAIN = SITE_DOMAIN  # reuse

# ---------- Web Push (VAPID) ----------
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_CLAIMS = {"sub": os.getenv("VAPID_SUB")}
