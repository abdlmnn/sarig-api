## Local Development

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate --settings=config.settings.dev
python manage.py runserver
```

### Linux / macOS (Bash)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --settings=config.settings.dev
python manage.py runserver
```

API base URL: `http://127.0.0.1:8000/api/v1/`

## Docker Compose (API + Postgres + Nginx)

```bash
docker compose up --build
```

URLs:
- Nginx: `http://localhost`
- API direct: `http://localhost:8000`

## Environment Variables

Create your local environment file from the template before running the app:

```bash
cp .env.example .env
```

For production-style Docker settings, use:

```bash
cp .env.production.example .env
```

Then update secrets in `.env` (for example `SECRET_KEY` and database credentials).

Location services also require provider keys for address search and road distance estimates:

```env
GEOAPIFY_API_KEY=your_geoapify_api_key_here
OPENROUTESERVICE_API_KEY=your_openrouteservice_api_key_here
```

Do not commit real API keys. See `docs/api/locations_api.md` for the location endpoints and delivery fee flow.

## Settings Modules

- Dev: `config.settings.dev`
- Prod: `config.settings.prod`

Override when needed:

### Windows (PowerShell)
```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.dev"
python manage.py check
```

### Linux / macOS (Bash)
```bash
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py check
```
