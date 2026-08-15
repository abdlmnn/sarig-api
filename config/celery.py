import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
gdal_library_path = os.getenv("GDAL_LIBRARY_PATH", "")
if os.name == "nt" and gdal_library_path:
    gdal_directory = os.path.dirname(gdal_library_path)
    if os.path.isdir(gdal_directory):
        os.environ["PATH"] = gdal_directory + os.pathsep + os.environ.get("PATH", "")
        os.add_dll_directory(gdal_directory)

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('sarig')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
