🧠 RECOMMENDED STACK (WINDOWS)

Use:

✅ PostgreSQL
✅ PostGIS
✅ GeoDjango
✅ psycopg2
⚠️ Avoid SQLite now
🚀 1. INSTALL POSTGRESQL + POSTGIS (WINDOWS)

Download:

PostgreSQL

PostgreSQL Official Website

During installation:

remember username/password
default port 5432 is fine
PostGIS

Usually included through:

Stack Builder

after PostgreSQL installation.

Install:

✅ PostGIS
✅ pgRouting (optional but useful later)
🧱 2. CREATE DATABASE

Open:

pgAdmin

Create database:

delivery_app
🧩 3. ENABLE POSTGIS EXTENSION

Inside Query Tool:

CREATE EXTENSION postgis;

Optional:

CREATE EXTENSION postgis_topology;
⚙️ 4. INSTALL PYTHON PACKAGES

Inside your venv:

pip install psycopg2-binary
⚠️ IMPORTANT: GDAL ON WINDOWS

This is the annoying part.

✅ EASIEST METHOD (RECOMMENDED)

Install precompiled wheel:

Download wheel matching:
your Python version
your Windows architecture

From:

Unofficial Windows Python Wheels

Example:

GDAL-3.x.x-cp312-cp312-win_amd64.whl
Install it:
pip install path_to_wheel.whl

Example:

pip install GDAL-3.10.2-cp312-cp312-win_amd64.whl
⚙️ 5. settings.py
INSTALLED_APPS
INSTALLED_APPS = [
    ...
    "django.contrib.gis",
]
DATABASE ENGINE
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "delivery_app",
        "USER": "postgres",
        "PASSWORD": "your_password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
🧱 6. VERIFY POSTGIS WORKS

Run:

python manage.py shell

Then:

from django.contrib.gis.geos import Point

p = Point(125.4553, 7.1907)
print(p)

If no error:
✅ GeoDjango works.

🗺 7. YOUR FINAL MODEL (WINDOWS READY)
from django.contrib.gis.db import models as gis_models
location = gis_models.PointField(geography=True)
⚠️ IMPORTANT WINDOWS ISSUE

Sometimes Django cannot find GDAL DLLs.

If that happens:

🔧 Add GDAL path manually

In settings.py:

import os

os.environ["GDAL_LIBRARY_PATH"] = r"C:\Program Files\PostgreSQL\17\bin\gdalXXX.dll"

(Replace actual DLL name)

🧠 RECOMMENDED ALTERNATIVE (BETTER LONG TERM)

Honestly:

🔥 Use Docker

Why?

GeoDjango on Windows becomes painful over time.

Using Docker:

avoids DLL issues
portable environment
same setup as production
🚀 BEST PRODUCTION STACK FOR YOU

Since you're building a real marketplace/delivery architecture:

Recommended:
Django
DRF
PostgreSQL
PostGIS
Docker
Redis later
Celery later
🏆 AFTER THIS SETUP

You unlock:

✔ Nearby stores
✔ Rider distance matching
✔ Spatial queries
✔ Delivery radius checks
✔ Real delivery architecture
