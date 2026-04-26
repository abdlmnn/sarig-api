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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DEV_DB_NAME", str(BASE_DIR / "db.sqlite3")),  # noqa: F405
    }
}
