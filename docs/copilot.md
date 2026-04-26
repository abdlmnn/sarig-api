kauyagan-backend/
├─ .env.example
├─ requirements.txt
├─ manage.py
├─ config/
│  ├─ __init__.py
│  ├─ urls.py
│  ├─ wsgi.py
│  └─ settings/
│     ├─ __init__.py
│     ├─ base.py
│     └─ dev.py
├─ apps/
│  ├─ __init__.py
│  ├─ users/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ models.py
│  │  ├─ serializers.py
│  │  ├─ views.py
│  │  └─ urls.py
│  ├─ jobs/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ models.py
│  │  ├─ serializers.py
│  │  ├─ views.py
│  │  └─ urls.py
│  ├─ verification/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ models.py
│  │  ├─ serializers.py
│  │  └─ views.py
│  └─ v1/
│     ├─ __init__.py
│     └─ urls.py
└─ scripts/
   └─ seed.py
