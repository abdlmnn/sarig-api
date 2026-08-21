import os
import sys
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


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
    "apps.email_templates",
    "apps.onboarding",
    "apps.riders",
    "apps.marketing",
    "apps.chat",
    "apps.reviews",
    "apps.rides",
    "apps.operations",
    "apps.locations",
    "cloudinary",
    "cloudinary_storage",
]

USE_POSTGIS = os.getenv("USE_POSTGIS", "False").lower() in {"1", "true", "yes", "on"}
GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH", "")

if USE_POSTGIS and "django.contrib.gis" not in INSTALLED_APPS:
    INSTALLED_APPS.insert(1, "django.contrib.gis")

if GDAL_LIBRARY_PATH:
    os.environ["GDAL_LIBRARY_PATH"] = GDAL_LIBRARY_PATH
    if os.name == "nt":
        gdal_directory = os.path.dirname(GDAL_LIBRARY_PATH)
        if os.path.isdir(gdal_directory):
            os.add_dll_directory(gdal_directory)

ASGI_APPLICATION = "config.asgi.application"

IS_TESTING = "test" in sys.argv

if IS_TESTING:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
else:
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
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
)
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "expire-pending-rides-every-minute": {
        "task": "apps.rides.tasks.expire_pending_rides_task",
        "schedule": 60.0,
    },
    "auto-cancel-stale-orders-every-5-minutes": {
        "task": "apps.orders.tasks.auto_cancel_stale_orders",
        "schedule": 300.0,
    },
    "dispatch-pending-onboarding-notifications-every-minute": {
        "task": "apps.onboarding.tasks.dispatch_pending_onboarding_notifications",
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
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_THROTTLE_ANON", "60/min"),
        "user": os.getenv("DRF_THROTTLE_USER", "200/min"),
        "nearby_stores": os.getenv("DRF_THROTTLE_NEARBY_STORES", "30/min"),
        "auth": os.getenv("DRF_THROTTLE_AUTH", "10/min"),
        "registration": os.getenv("DRF_THROTTLE_REGISTRATION", "5/hour"),
        "onboarding": os.getenv("DRF_THROTTLE_ONBOARDING", "10/hour"),
        "onboarding_status": os.getenv("DRF_THROTTLE_ONBOARDING_STATUS", "60/min"),
        "checkout": os.getenv("DRF_THROTTLE_CHECKOUT", "20/hour"),
        "checkout_quote": os.getenv("DRF_THROTTLE_CHECKOUT_QUOTE", "120/min"),
        "payment_webhook": os.getenv("DRF_THROTTLE_PAYMENT_WEBHOOK", "120/min"),
        "search": os.getenv("DRF_THROTTLE_SEARCH", "60/min"),
        "locations": os.getenv("DRF_THROTTLE_LOCATIONS", "60/min"),
        "files": os.getenv("DRF_THROTTLE_FILES", "60/min"),
    },
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

AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "1").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AUTH_REFRESH_COOKIE_NAMES = {
    "ADMIN": (
        "__Host-sarig-admin-refresh" if AUTH_COOKIE_SECURE else "sarig-admin-refresh"
    ),
    "MERCHANT": (
        "__Host-sarig-merchant-refresh"
        if AUTH_COOKIE_SECURE
        else "sarig-merchant-refresh"
    ),
    "CUSTOMER": (
        "__Host-sarig-customer-refresh"
        if AUTH_COOKIE_SECURE
        else "sarig-customer-refresh"
    ),
}
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")
AUTH_SESSION_REFRESH_HOURS = int(os.getenv("AUTH_SESSION_REFRESH_HOURS", "8"))
AUTH_ADMIN_REMEMBER_DAYS = int(os.getenv("AUTH_ADMIN_REMEMBER_DAYS", "7"))
AUTH_MERCHANT_REMEMBER_DAYS = int(os.getenv("AUTH_MERCHANT_REMEMBER_DAYS", "30"))
AUTH_CUSTOMER_REMEMBER_DAYS = int(os.getenv("AUTH_CUSTOMER_REMEMBER_DAYS", "30"))
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = AUTH_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


API_V1_SUNSET = os.getenv("API_V1_SUNSET", "2026-12-31")
ADMIN_URL_PATH = os.getenv("ADMIN_URL_PATH", "admin/")

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_CLOUDINARY = os.getenv("USE_CLOUDINARY", "False").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_FCM_PUSH = os.getenv("ENABLE_FCM_PUSH", "False").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
ONBOARDING_SMS_BACKEND = os.getenv("ONBOARDING_SMS_BACKEND", "")
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() in {"1", "true", "yes", "on"}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@sarig.local")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
PAYMONGO_WEBHOOK_SECRET = os.getenv("PAYMONGO_WEBHOOK_SECRET", "")
PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY", "")
PAYMONGO_SUCCESS_URL = os.getenv("PAYMONGO_SUCCESS_URL", "")
PAYMONGO_CANCEL_URL = os.getenv("PAYMONGO_CANCEL_URL", "")
PAYMONGO_ENABLED_PAYMENT_METHODS = os.getenv(
    "PAYMONGO_ENABLED_PAYMENT_METHODS", "GCASH,MAYA,CARD"
)
PAYMONGO_USE_MOCK = os.getenv("PAYMONGO_USE_MOCK", str(DEBUG)).lower() in {
    "1",
    "true",
    "yes",
    "on",
}

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
JOYRIDE_ENABLE_SURGE = os.getenv("JOYRIDE_ENABLE_SURGE", "False").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
JOYRIDE_SURGE_MULTIPLIER = os.getenv("JOYRIDE_SURGE_MULTIPLIER", "1.00")
JOYRIDE_REQUEST_TIMEOUT_MINUTES = int(os.getenv("JOYRIDE_REQUEST_TIMEOUT_MINUTES", "5"))
JOYRIDE_ENABLE_AUTO_MATCHING = os.getenv(
    "JOYRIDE_ENABLE_AUTO_MATCHING", "True"
).lower() in {"1", "true", "yes", "on"}
JOYRIDE_MATCHING_MAX_RADIUS_KM = float(
    os.getenv("JOYRIDE_MATCHING_MAX_RADIUS_KM", "10")
)
JOYRIDE_RIDER_CANCEL_PENALTY = os.getenv("JOYRIDE_RIDER_CANCEL_PENALTY", "30.00")

# Location provider settings.
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "")
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")
LOCATION_ENABLE_EXTERNAL_APIS = os.getenv(
    "LOCATION_ENABLE_EXTERNAL_APIS", str(DEBUG)
).lower() in {"1", "true", "yes", "on"}
LOCATION_PROVIDER_TIMEOUT_SECONDS = int(
    os.getenv("LOCATION_PROVIDER_TIMEOUT_SECONDS", "8")
)
LOCATION_COUNTRY_CODES = os.getenv("LOCATION_COUNTRY_CODES", "ph")
LOCATION_BIAS_LATITUDE = os.getenv("LOCATION_BIAS_LATITUDE", "8.003400")
LOCATION_BIAS_LONGITUDE = os.getenv("LOCATION_BIAS_LONGITUDE", "124.283900")
DELIVERY_BASE_FEE = os.getenv("DELIVERY_BASE_FEE", "40.00")
DELIVERY_PER_KM_FEE = os.getenv("DELIVERY_PER_KM_FEE", "10.00")
DELIVERY_MIN_FEE = os.getenv("DELIVERY_MIN_FEE", "40.00")
DELIVERY_MAX_DISTANCE_KM = float(os.getenv("DELIVERY_MAX_DISTANCE_KM", "30"))
DELIVERY_SAVER_FEE_MULTIPLIER = os.getenv("DELIVERY_SAVER_FEE_MULTIPLIER", "0.85")
DELIVERY_PRIORITY_FEE_MULTIPLIER = os.getenv("DELIVERY_PRIORITY_FEE_MULTIPLIER", "1.25")
DELIVERY_SAVER_EXTRA_MINUTES = int(os.getenv("DELIVERY_SAVER_EXTRA_MINUTES", "10"))
DELIVERY_PRIORITY_REDUCED_MINUTES = int(
    os.getenv("DELIVERY_PRIORITY_REDUCED_MINUTES", "5")
)
ORDER_SYSTEM_FEE = os.getenv("ORDER_SYSTEM_FEE", "10.00")
ORDER_DEFAULT_PREPARATION_MINUTES = int(
    os.getenv("ORDER_DEFAULT_PREPARATION_MINUTES", "10")
)
