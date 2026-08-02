# Partner B Week 1 Completion

## Overview

The `backend-refresh-week1` branch establishes the Week 1 database and
authentication foundation while preserving the legacy API. The work introduces
centralized configuration, SQLAlchemy persistence, Alembic migrations, local
Docker/MySQL support, and focused authentication tests. Existing chat, OpenAI,
Guardrails, Tortoise profile, and compatibility-route behavior is intentionally
left in place.

## Completed Work

- **SQLAlchemy authentication consolidation:** Active registration, login,
  token validation, and protected-route user lookup use `app.models.User` with
  the SQLAlchemy `Session` supplied by `app.db.session.get_db`. Passwords are
  hashed before persistence, and authentication does not create or query a
  legacy Tortoise user record.
- **Alembic setup:** The repository-root Alembic configuration imports the
  centralized database URL and SQLAlchemy `Base.metadata`. Alembic is the
  authoritative schema-management mechanism; application startup and tests do
  not use `Base.metadata.create_all`.
- **Docker support:** `Dockerfile`, `.dockerignore`, and `docker-compose.yml`
  define a FastAPI backend and a MySQL 8.4 service. The backend waits for the
  MySQL health check, applies `alembic upgrade head`, and serves the application
  on local port 8001.
- **MySQL support:** The Compose environment supplies a local
  `mysql+pymysql` database URL, `PyMySQL` is declared as a dependency, and the
  Alembic migration chain runs against the MySQL 8.4 service. The health check
  uses the application user over TCP so it cannot pass against MySQL's
  temporary initialization server during a cold start.
- **`users.email` migration:** A forward-only follow-up revision adds a nullable
  email column and a unique constraint without removing the existing username
  field or editing the initial migration.
- **`farm_profiles` migration:** A second forward revision creates the
  SQLAlchemy-backed `farm_profiles` table and model. The pre-existing
  `user_profiles` table and model remain available for compatibility.
- **`POST /signup` and `POST /login`:** Compatibility aliases were added and
  delegate to the consolidated authentication behavior.
- **`app/auth/security.py`:** Password hashing, password verification, JWT
  encoding, and JWT decoding are centralized in this module.
- **`app/auth/dependencies.py`:** OAuth2 bearer parsing and
  `get_current_user` are centralized in this module and use the SQLAlchemy
  session dependency.
- **Compatibility with existing routes:** `POST /users/register`,
  `POST /api/token`, and the existing protected endpoint remain available.
  Existing route shapes, status behavior, password hashing, JWT claims and
  expiration behavior were preserved. No chat, OpenAI, Guardrails, thread
  storage, or profile route was intentionally changed.
- **Automated tests:** The SQLite authentication suite covers successful
  registration, duplicate usernames, successful login, incorrect passwords,
  valid-token protected access, missing-token rejection, and the new route
  aliases. An opt-in MySQL integration test covers signup, login, JWT receipt,
  and protected-route access against the Docker MySQL service. The SQLite tests
  apply Alembic migrations rather than auto-creating tables.

## Files Added

The following files are new on this branch relative to `main`:

- `alembic.ini`
- `alembic/README`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/.gitkeep`
- `alembic/versions/781affe3eee7_create_initial_user_tables.py`
- `alembic/versions/d7e35e3f96cb_add_user_email.py`
- `alembic/versions/4679ddbdb662_add_farm_profiles.py`
- `app/__init__.py`
- `app/auth/__init__.py`
- `app/auth/security.py`
- `app/auth/dependencies.py`
- `app/core/__init__.py`
- `app/core/config.py`
- `app/db/__init__.py`
- `app/db/session.py`
- `app/main.py`
- `app/models/__init__.py`
- `app/models/user.py`
- `app/models/user_profile.py`
- `app/models/farm_profile.py`
- `app/profiles/__init__.py`
- `.dockerignore`
- `Dockerfile`
- `docker-compose.yml`
- `tests/test_auth.py`
- `tests/test_auth_mysql.py`

## Files Modified

The following existing files are modified on this branch relative to `main`:

- `.gitignore`
- `README.md`
- `database.py`
- `main.py`
- `requirements.txt`
- `schemas.py`
- `services.py`

## Database Changes

The Alembic history contains three ordered revisions:

1. `781affe3eee7_create_initial_user_tables.py` creates:
   - `users` with `id`, unique indexed `username`, `hashed_password`,
     `created_at`, and `updated_at`.
   - `user_profiles` with `id`, unique indexed `user_id` referencing
     `users.id`, nullable `display_name`, `district`, and
     `preferred_language`, plus `created_at` and `updated_at`.
2. `d7e35e3f96cb_add_user_email.py` adds nullable `users.email` and enforces
   uniqueness. The existing username identity remains supported.
3. `4679ddbdb662_add_farm_profiles.py` creates `farm_profiles` with `id`,
   indexed `user_id` referencing `users.id` with cascade deletion,
   `farm_name`, `district`, `crops`, `farm_size`, and `created_at`.

Each revision includes a downgrade path. The original migrations were not
rewritten when the email and farm-profile schema was added.

## API Changes

New compatibility endpoints:

- `POST /signup` registers a user using the SQLAlchemy users table.
- `POST /login` authenticates a user and returns the existing JWT response
  shape.

Preserved endpoints and behavior:

- `POST /users/register` remains the original registration route.
- `POST /api/token` remains the OAuth2-compatible login/token route.
- The existing protected route continues to require the same bearer-token
  flow.
- Existing health, chat, OpenAI Assistants, Guardrails, and profile routes
  remain available.

The new auth routes delegate to the same underlying auth implementation rather
than creating a second persistence path. Username remains supported for
backward compatibility, while email is added to the database schema without
removing existing fields.

## Verification Performed

- `git diff --check` completed without whitespace errors.
- Python syntax and application import checks completed successfully.
- SQLAlchemy mapper configuration completed successfully.
- Alembic upgraded a fresh temporary SQLite database through all three
  revisions.
- Alembic downgraded the temporary SQLite database to base and removed the
  created application tables.
- `alembic check` reported no new upgrade operations.
- MySQL-dialect offline Alembic SQL rendered through the current head without
  connecting to a database.
- The upgraded SQLite schema was inspected and contained `users`,
  `user_profiles`, and `farm_profiles` with the expected columns and
  constraints.
- The combined authentication run reported `Ran 8 tests` and `OK`: all seven
  SQLite authentication tests and the live MySQL integration test passed.
- A clean `docker compose up --build -d` run created the MySQL data volume,
  waited for MySQL to become healthy, applied all Alembic revisions, and
  started the backend. The backend health endpoint confirmed database
  connectivity, and the live schema was inspected at revision `4679ddbdb662`.

## Notes for Merge

Partner A should retain the ordered Alembic revision chain and run
`alembic upgrade head` in the intended deployment environment before exercising
the SQLAlchemy authentication routes. The Docker Compose credentials and ports
are local-development settings, and deployment database configuration should
continue to come from the centralized environment-based settings.

The branch deliberately retains `username`, `user_profiles`, the original auth
routes, and the legacy non-auth behavior for compatibility. No existing API
behavior was intentionally broken.
