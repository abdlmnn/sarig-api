from .base import *  # noqa: F403


DEBUG = os.getenv("DEBUG", "1").lower() in {"1", "true", "yes", "on"}  # noqa: F405
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")  # noqa: F405
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")  # noqa: F405
    if host.strip()
]
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "1").lower() in {  # noqa: F405
    "1",
    "true",
    "yes",
    "on",
}

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
            "NAME": os.getenv("DEV_DB_NAME", str(BASE_DIR / "db.sqlite3")),  # noqa: F405
        }
    }
