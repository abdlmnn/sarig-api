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
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "same-origin"
