"""Alembic environment configuration for Allocraft.

Reads DATABASE_URL from the environment (same as the FastAPI app) so
migrations always target the same database as the running service.
"""
from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Make the app importable from this env.py (which lives inside fastapi_project/)
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent.parent  # fastapi_project/
sys.path.insert(0, str(APP_DIR))

# Import all models so Alembic can see the full metadata graph
from app.database import Base  # noqa: E402  — must come after sys.path patch
import app.models              # noqa: E402, F401
import app.models_unified      # noqa: E402, F401

# ---------------------------------------------------------------------------
# Alembic Config object providing access to alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url with the runtime DATABASE_URL env var
database_url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
# SQLAlchemy ≥2 requires psycopg2 scheme for Render's postgres:// URLs
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
config.set_main_option("sqlalchemy.url", database_url)

# Interpret alembic.ini logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata object from our declarative Base — enables --autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a real DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
