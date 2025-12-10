from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

# === Basis ===
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)  # .env lokaal; prod via echte env/secrets

# === Debug ===
DEBUG = os.getenv("DEBUG", "True") == "True"

# === Secret ===
SECRET_KEY = os.getenv("SECRET_KEY")  # zet altijd via secrets/Parameter Store

# === Proxy/HTTPS ===
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# === Domein/Hosts/CSRF ===
if DEBUG:
    SITE_DOMAIN = os.getenv("DEV_SITE_DOMAIN", "http://127.0.0.1:8000")
    ALLOWED_HOSTS = [
        x.strip() for x in os.getenv(
            "DEV_ALLOWED_HOSTS",
            "127.0.0.1,localhost,.ngrok-free.dev"
        ).split(",") if x.strip()
    ]
    CSRF_TRUSTED_ORIGINS = [
        x.strip() for x in os.getenv(
            "DEV_CSRF_TRUSTED_ORIGINS",
            "http://127.0.0.1:8000,https://*.ngrok-free.dev"
        ).split(",") if x.strip()
    ]
else:
    SITE_DOMAIN = os.getenv("PROD_SITE_DOMAIN")
    ALLOWED_HOSTS = [
        x.strip() for x in os.getenv(
            "PROD_ALLOWED_HOSTS",
            ""
        ).split(",") if x.strip()
    ]
    CSRF_TRUSTED_ORIGINS = [
        x.strip() for x in os.getenv(
            "PROD_CSRF_TRUSTED_ORIGINS",
            ""
        ).split(",") if x.strip()
    ]

# Cookies/Security
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False") == "True"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "False") == "True"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False") == "True"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "core.views.errors.csrf_failure"

# === Apps ===
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "core.apps.CoreConfig", 

    # Dev tooling
    "django_browser_reload",

    # 2FA / OTP
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "two_factor",

    # S3 storage
    "storages",
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
]

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

# === Database ===
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}
if DEBUG:
    _db_url = os.getenv("DEV_DATABASE_URL")
else:
    _db_url = os.getenv("PROD_DATABASE_URL")

if _db_url:
    try:
        import dj_database_url
        DATABASES = {
            "default": dj_database_url.parse(
                _db_url,
                conn_max_age=0 if DEBUG else 600
            )
        }
    except Exception:
        # dj_database_url ontbreekt of parse error → blijf op SQLite
        pass

# === Redis / Cache / Sessions ===
if DEBUG:
    REDIS_URL = os.getenv("DEV_REDIS_URL", "redis://127.0.0.1:6379/1")
    CELERY_BROKER_URL = os.getenv("DEV_CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
    CELERY_RESULT_BACKEND = os.getenv("DEV_CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/3")
else:
    REDIS_URL = os.getenv("PROD_REDIS_URL")
    CELERY_BROKER_URL = os.getenv("PROD_CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.getenv("PROD_CELERY_RESULT_BACKEND")

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 3600,  # 1 uur
    }
}

# === Celery ===
CELERY_TASK_ALWAYS_EAGER = False  # True voor sync testen (dev-only)
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_SOFT_TIME_LIMIT = 50
CELERY_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "core.tasks.send_invite_email_task": {"queue": "mail"},
    "core.tasks.send_roster_updated_push_task": {"queue": "push"},
}

# === Auth / Passwords ===
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

# === Static & Media ===

if DEBUG:
    # LOKAAL
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    # Cache (dev) – lokaal
    CACHE_DIR = MEDIA_ROOT / "cache"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    SERVE_MEDIA_LOCALLY = True

    # Django 5: gebruik STORAGES i.p.v. DEFAULT_FILE_STORAGE/STATICFILES_STORAGE
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "core.storage.PartialManifestStaticFilesStorage",
        },
    }
else:
    # PROD: S3 voor static + media
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = "eu-central-1"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ADDRESSING_STYLE = "virtual"

    AWS_S3_CUSTOM_DOMAIN = os.getenv(
        "AWS_S3_CUSTOM_DOMAIN",
        f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com",
    )

    # Dummy STATIC_ROOT zodat Django niet klaagt.
    STATIC_ROOT = BASE_DIR / "staticfiles"

    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

    AWS_DEFAULT_ACL = None

    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=31536000, public",
    }

    MEDIA_ROOT = BASE_DIR / "media"
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    CACHE_DIR = MEDIA_ROOT / "cache"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    SERVE_MEDIA_LOCALLY = False

    # Hier S3 backends koppelen
    STORAGES = {
        "default": {
            "BACKEND": "core.storage.MediaRootS3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "core.storage.PartialManifestStaticFilesS3Storage",
        },
    }

# === Sessies ===
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 uur
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False

# === Email ===
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# === Links in mail ===
USE_HTTPS_IN_EMAIL_LINKS = not DEBUG
# SITE_DOMAIN al gezet hierboven

# === Web Push (VAPID) ===
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_SUB = os.getenv("VAPID_SUB")

# === Custom constants ===
APOTHEEK_JANSEN_ORG_ID = 1

# === MedicatieReview API ===
# Deze key is nodig om de JSON versleuteld in Postgres op te slaan
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if DEBUG:
    # Lokaal: we pakken de DEV url of vallen terug op localhost
    MEDICATIEREVIEW_API_URL = os.getenv("DEV_MEDICATIEREVIEW_API_URL", "http://127.0.0.1:8001/api/review")
else:
    # Productie: we pakken de PROD url (Lambda)
    MEDICATIEREVIEW_API_URL = os.getenv("PROD_MEDICATIEREVIEW_API_URL")

MEDICATIEREVIEW_API_KEY = os.getenv("MEDICATIEREVIEW_API_KEY")

ALLOWED_MEDICATIEREVIEW_IPS = [
    "127.0.0.1",      # Localhost (voor development)
]

LANGUAGE_CODE = 'nl-nl'
TIME_ZONE = 'Europe/Amsterdam'
USE_I18N = True
USE_TZ = True