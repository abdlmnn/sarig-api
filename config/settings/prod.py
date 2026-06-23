import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set for production.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set for production.")

if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be set for production.")

if not PAYMONGO_WEBHOOK_SECRET:  # noqa: F405
    raise ImproperlyConfigured("PAYMONGO_WEBHOOK_SECRET must be set for production.")

if not PAYMONGO_SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("PAYMONGO_SECRET_KEY must be set for production.")

if PAYMONGO_USE_MOCK:  # noqa: F405
    raise ImproperlyConfigured("PAYMONGO_USE_MOCK cannot be enabled in production.")

if ADMIN_URL_PATH == "admin/":  # noqa: F405
    raise ImproperlyConfigured("ADMIN_URL_PATH must not use the default admin/ path in production.")

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis" if USE_POSTGIS else "django.db.backends.postgresql",  # noqa: F405
        "NAME": os.getenv("POSTGRES_DB", ""),
        "USER": os.getenv("POSTGRES_USER", ""),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}


SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "1").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", "1"
).lower() in {"1", "true", "yes", "on"}
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "1").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "same-origin"
