from .base import *  # noqa: F403

DEBUG = os.getenv("DEBUG", "1").lower() in {"1", "true", "yes", "on"}  # noqa: F405
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")  # noqa: F405
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")  # noqa: F405
    if host.strip()
]
# CORS_ALLOW_ALL_ORIGINS = False  # noqa: F405
# CORS_ALLOW_CREDENTIALS = True  # noqa: F405
CORS_ALLOWED_ORIGINS = [  # noqa: F405
    origin.strip()
    for origin in os.getenv(  # noqa: F405
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [  # noqa: F405
    origin.strip()
    for origin in os.getenv(  # noqa: F405
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

if USE_POSTGIS:  # noqa: F405
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.getenv("POSTGRES_DB", "delivery_app"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv(
                "DEV_DB_NAME", str(BASE_DIR / "db.sqlite3")
            ),  # noqa: F405
        }
    }
