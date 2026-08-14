# Sarig API — Engineering Guide for Agents

This file contains the repo-specific facts an agent is likely to get wrong, plus the guardrails that must not be violated. Keep it small and accurate. Prefer `/docs` for prose; keep `AGENTS.md` for rules.

## Stack (verify against `requirements.txt`, not memory)

Django 6.0 + DRF 3.17, Channels/ASGI (daphne), Celery, SimpleJWT, django-rest-knox, PostGIS (optional), Redis, Cloudinary, `rav` task runner. Python 3.12 (`.python-version`). Delivery super-app: vendors, orders, rides, riders, payments (PayMongo), chat, locations, marketing, reviews, onboarding.

## Setup and commands

- Activate `.venv` and install with `pip install -r requirements.txt`.
- Copy `.env.example` to `.env` before running; secrets and API keys live only in `.env` (git-ignored). Never commit real keys or credentials.
- `manage.py` defaults to `config.settings.dev`. README shows `--settings=config.settings.dev`; prod is `config.settings.prod`.
- Common commands:
  - Run: `python manage.py runserver` (API at `http://127.0.0.1:8000/api/v1/`)
  - Migrate: `python manage.py makemigrations` then `python manage.py migrate`
  - Check: `python manage.py check`
  - Tests: `python manage.py test`
- `rav` task runner is available (`rav dev`, `rav migrate`, `rav test`, `rav check`, `rav seed_onboarding`, `rav tunnel`, `rav admin`). Prefer `manage.py` unless a `rav` script exists.

## Environment / DB quirks

- Env is loaded by `config/settings/base.py` via `python-dotenv` from `.env` at project root (`override=False`). `DJANGO_SETTINGS_MODULE` must be `config.settings.*` (a module, not a file).
- Database is chosen at runtime by `USE_POSTGIS`:
  - `USE_POSTGIS=False` (default) → SQLite at `db.sqlite3`, no GIS.
  - `USE_POSTGIS=1` → PostGIS via psycopg3, adds `django.contrib.gis` to `INSTALLED_APPS`.
- Channels requires Redis unless `IS_TESTING` (tests use in-memory channel layer automatically — no Redis needed for tests).
- Celery broker defaults to Redis (`CELERY_BROKER_URL`/`REDIS_URL`); RabbitMQ `amqp://` is the Windows fallback.
- Location features need `GEOAPIFY_API_KEY` and `OPENROUTESERVICE_API_KEY`. See `docs/api/locations_api.md` for the delivery-fee flow.
- Docker Compose (`docker compose up --build`) runs API + PostGIS + Nginx; it mounts `.env` and forces `USE_POSTGIS=1`.

## Architecture

- Feature apps live under `apps/` (users, vendors, catalog, orders, payments, rides, riders, chat, locations, operations, onboarding, marketing, reviews, email_templates). Shared code lives in `apps/common`.
- All API routes are mounted at `/api/v1/` through `apps/v1/urls.py` (namespace `v1`); `config/urls.py` is the root URLconf. `rest_framework` uses `NamespaceVersioning`.
- Custom user model: `AUTH_USER_MODEL = "users.User"`. Default permission is `IsAuthenticatedOrReadOnly`; JWT auth is the default.
- Auth is role-scoped (ADMIN / MERCHANT / CUSTOMER) with per-role refresh cookies configured in `base.py`. Custom middleware lives in `config/middleware.py` (e.g. `DeprecationHeaderMiddleware`) and `config/jwt_auth_middleware.py`. Read `docs/role-scoped-authentication-architecture.md` before touching auth.
- Async entrypoint is `config.asgi` (daphne); WSGI is `config.wsgi`. Celery beat in `base.py` schedules `apps.rides.tasks.expire_pending_rides_task` every minute.
- Media storage switches to Cloudinary when `USE_CLOUDINARY=1`; local dev uses local `media/`.
- `config/` is the Django project package — keep settings, urls, and middleware there, not inside `apps/`.

## Lint, format, typecheck

- Lint: `flake8 .`. Config in `.flake8` selects only `E9,F63,F7,F82` (syntax/undefined-name errors), `max-line-length=127`, `max-complexity=10`; it excludes `migrations/`, `.venv`, `media`, etc.
- Formatter: Black is the VS Code default formatter. Match existing style; keep lines ≤ 127.
- Type checking config exists at `pyrightconfig.json` (`typeCheckingMode: basic`). Run pyright only if the task touches types; it is not part of CI.

## Tests

- Tests live in the top-level `tests/` package, one folder per domain (mirrors `apps/`). Do not scatter tests inside `apps/`.
- Run a single module: `python manage.py test tests.orders.test_checkout`.
- HTTP request fixtures (`.http`) sit alongside tests in `tests/<domain>/GET|POST/` for manual API verification.
- CI (`.github/workflows/django.yml`) runs flake8, then `makemigrations --check --dry-run`, then a critical suite, then the full suite — against a PostGIS + Redis service. Any model change that produces a missing migration will fail CI.
- Test account setup, permissions, webhook security, and ownership checks — auth/authorization failures are a frequent focus (see `tests/auth/`, `tests/payments/test_webhook_security.py`, `tests/orders/test_prescription_files.py`).

## Docs

- Only `docs/api/**` is committed; all other `docs/**` is git-ignored (private). Put public API reference in `docs/api/`, private notes elsewhere in `docs/`.
- Use `docs/ai-activity/` for implementation/activity logs. Do not auto-commit docs unless explicitly asked.
- Naming: markdown files use descriptive kebab-case (e.g. `some-description-changes.md`).

## Code cleanup and maintainability

- Remove dead code: unused imports, variables, functions, files, and abandoned logic.
- No duplication: shared logic has one clear source of truth; centralize repeated helpers and components. Do not create a new component, hook, service, or helper when an existing reusable one can be used.
- No over-engineering: make the smallest safe change; do not rewrite working code just to make it look different; do not add abstractions, libraries, or layers without a real need.
- Keep functions and components focused on a single responsibility; extract focused hooks or services when a function or component grows.
- Follow the existing folder structure, naming, and style before editing. Do not change unrelated files.

## Guardrails (always)

- Inspect existing code and follow its structure, naming, and style before editing. Make the smallest safe change; do not rewrite working code or change unrelated files.
- Never commit, push, or create PRs unless explicitly asked. When committing, keep it atomic with a clear message; never include secrets.
- Do not add external libraries unless necessary; if one is needed, explain why. Remove dead code and unused imports.
- Never trust client input; validate and sanitize. Enforce auth/ownership/permission checks; do not bypass role or ownership boundaries. Store secrets only in env vars.
- Never expose customer or personal data, credentials, tokens, or connection strings. Do not fabricate test results or claim a command passed that was not run.
- No emojis or decorative characters in code comments, commit messages, logs, or docs. Keep comments short and useful.
- If you cannot run tests/lint, state that clearly and why.