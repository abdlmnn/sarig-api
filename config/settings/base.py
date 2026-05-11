import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
DEBUG = os.getenv("DEBUG", "0").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]


INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "apps.users",
    "apps.vendors",
    "apps.catalog",
    "apps.orders",
    "apps.payments",
    "apps.onboarding",
    "apps.riders",
    "apps.marketing",
    "apps.chat",
    "apps.reviews",
    "apps.rides",
    "cloudinary",
    "cloudinary_storage",
]

USE_POSTGIS = os.getenv("USE_POSTGIS", "False").lower() in {"1", "true", "yes", "on"}
GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH", "")

if USE_POSTGIS and "django.contrib.gis" not in INSTALLED_APPS:
    INSTALLED_APPS.insert(1, "django.contrib.gis")

if GDAL_LIBRARY_PATH:
    os.environ["GDAL_LIBRARY_PATH"] = GDAL_LIBRARY_PATH

ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.getenv("REDIS_HOST", "127.0.0.1"), 6379)],
        },
    },
}

# --- Celery Configuration ---
# Supports Redis by default, but you can override with RabbitMQ (amqp://) on Windows if preferred.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "expire-pending-rides-every-minute": {
        "task": "apps.rides.tasks.expire_pending_rides_task",
        "schedule": 60.0,
    },
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.DeprecationHeaderMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1", "v2"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "5"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "1"))),
    "ROTATE_REFRESH_TOKENS": os.getenv("JWT_ROTATE_REFRESH_TOKENS", "1").lower()
    in {"1", "true", "yes", "on"},
    "BLACKLIST_AFTER_ROTATION": os.getenv("JWT_BLACKLIST_AFTER_ROTATION", "1").lower()
    in {"1", "true", "yes", "on"},
    "ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": (os.getenv("JWT_AUTH_HEADER_TYPE", "Bearer"),),
}


API_V1_SUNSET = os.getenv("API_V1_SUNSET", "2026-12-31")

CORS_ALLOW_ALL_ORIGINS = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_CLOUDINARY = os.getenv("USE_CLOUDINARY", "False").lower() in {"1", "true", "yes", "on"}
ENABLE_FCM_PUSH = os.getenv("ENABLE_FCM_PUSH", "False").lower() in {"1", "true", "yes", "on"}
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

if USE_CLOUDINARY:
    # Use Cloudinary in production
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
        "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Joyride fare defaults (can be overridden by env in deployment)
JOYRIDE_ENABLE_SURGE = os.getenv("JOYRIDE_ENABLE_SURGE", "False").lower() in {"1", "true", "yes", "on"}
JOYRIDE_SURGE_MULTIPLIER = os.getenv("JOYRIDE_SURGE_MULTIPLIER", "1.00")
JOYRIDE_REQUEST_TIMEOUT_MINUTES = int(os.getenv("JOYRIDE_REQUEST_TIMEOUT_MINUTES", "5"))
JOYRIDE_ENABLE_AUTO_MATCHING = os.getenv("JOYRIDE_ENABLE_AUTO_MATCHING", "True").lower() in {"1", "true", "yes", "on"}
JOYRIDE_MATCHING_MAX_RADIUS_KM = float(os.getenv("JOYRIDE_MATCHING_MAX_RADIUS_KM", "10"))
