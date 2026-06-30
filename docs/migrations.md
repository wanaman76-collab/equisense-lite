# Database Migrations (Alembic)

Schema lifecycle for EquiSense Lite is managed by **Alembic**.

## Prerequisites

Alembic is installed as part of the backend dependencies:

```bash
cd backend
pip install -r requirements.txt
```

## Running migrations

### Apply all pending migrations (upgrade to head)

```bash
cd backend
alembic upgrade head
```

Or via Makefile:

```bash
make migrate-upgrade
```

### Roll back one migration

```bash
make migrate-downgrade
# or
alembic downgrade -1
```

### Show migration history

```bash
make migrate-history
# or
alembic history --verbose
```

## Creating a new migration

After changing `backend/app/models.py`, auto-generate a new migration:

```bash
make migrate-revision MSG="add_my_column"
# or
cd backend && alembic revision --autogenerate -m "add_my_column"
```

Review the generated file in `backend/alembic/versions/` before applying.

## Local development

The default SQLite URL (`sqlite:///./equisense.db`) is used when no `DATABASE_URL`
environment variable is set.  Run migrations before starting the server:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

## Production / Render

Set `DATABASE_URL` to your PostgreSQL connection string (e.g. Render Postgres).
Run `alembic upgrade head` as part of your deploy pipeline (before the server starts):

```yaml
# Example Render build command
pip install -r requirements.txt && alembic upgrade head
```

## Rollback notes

- Every migration has a corresponding `downgrade()` function.
- Run `alembic downgrade -1` to undo the last migration.
- For a full teardown use `alembic downgrade base`.
- **SQLite** — `render_as_batch=True` is set in `env.py` so that ALTER TABLE
  operations (which SQLite does not support natively) work via table-rebuild.
- **PostgreSQL** — native ALTER TABLE; batch mode is transparent.
