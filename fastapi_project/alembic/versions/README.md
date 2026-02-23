# Alembic Version Scripts

This directory contains Alembic migration scripts for Allocraft.

## Usage

```bash
# Apply all pending migrations
alembic upgrade head

# Generate a new migration from model changes
alembic revision --autogenerate -m "describe change"

# Roll back last migration
alembic downgrade -1

# Show current revision
alembic current
```

## Notes
- Always run `alembic upgrade head` before starting the server in production
- Never edit committed migration files; create a new revision instead
- Keep `DATABASE_URL` in env so migrations target the correct database
