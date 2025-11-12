from pathlib import Path
import os
from datetime import timedelta
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
    '.ngrok-free.dev',
]
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.dev',
    'https://*.apotheekjansen.com'
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
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "two_factor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "two_factor.middleware.threadlocals.ThreadLocals",
    "core.middleware.Enforce2FAMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
        ]},
    }
]

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

# === Redis and sessions ===

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# === Celery ===

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/3")

CELERY_TASK_ALWAYS_EAGER = False           # True voor sync testen (development-only)
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_SOFT_TIME_LIMIT = 50
CELERY_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "core.tasks.send_invite_email_task": {"queue": "mail"},
    "core.tasks.send_roster_updated_push_task": {"queue": "push"},
}

# == Password validation ==

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},  # pas aan naar jouw eis
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Static (serve icons from data/)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# Media (uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CACHE_DIR = MEDIA_ROOT / "cache"     # rendered PNGs for roster
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Auth
LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/account/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = False  # in dev via ngrok

# 24 uur sessie
SESSION_COOKIE_AGE = 60 * 60 * 8           # 8 uur
# Niet-persistente sessiecookie (logout bij sluiten browser/app*)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# (Optioneel) elke request verlengt de sessie → rolling window
SESSION_SAVE_EVERY_REQUEST = True

# ==== EMAIL (eerst voor test) ====
# Voor lokaal debuggen kan ook: "django.core.mail.backends.console.EmailBackend"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "testwachtwoordreset@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Link-opbouw in mails
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "https://treasonably-noncerebral-samir.ngrok-free.dev")  # in prod: jouw domein
USE_HTTPS_IN_EMAIL_LINKS = os.getenv("USE_HTTPS_IN_EMAIL_LINKS", "False") == "True"