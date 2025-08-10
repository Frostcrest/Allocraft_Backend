"""
database.py
------------
This file manages the database connection and session for the FastAPI app.
It uses SQLAlchemy to connect to a SQLite database and provides a session factory
for use in other parts of the application.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# --- DATABASE CONFIGURATION ---

# The database URL is configurable via env var for deploys; falls back to local SQLite.
# Examples:
#   sqlite:///./test.db
#   sqlite:////opt/render/data/app.db  (Render disk)
#   postgresql+psycopg2://user:pass@host:5432/dbname
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# If using SQLite, ensure the target directory exists and is writable.
# This prevents errors like "sqlite3.OperationalError: unable to open database file"
# when running on platforms with read-only code dirs (e.g., Render) or when the
# path points to a mounted disk (e.g., /opt/render/data).
try:
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        url = make_url(SQLALCHEMY_DATABASE_URL)
        db_path = url.database  # May be relative (./test.db) or absolute (/opt/render/data/app.db)
        if db_path and db_path != ":memory:":
            # Resolve relative paths relative to current working directory
            db_file = Path(db_path)
            if not db_file.is_absolute():
                db_file = Path.cwd() / db_file
            db_dir = db_file.parent
            db_dir.mkdir(parents=True, exist_ok=True)
except Exception:
    # Fail open: if anything goes wrong, let SQLAlchemy handle/raise at connect
    # (we avoid crashing import-time with path parsing issues)
    pass

# Create the SQLAlchemy engine.
# The 'connect_args' option is required for SQLite to allow usage in a multithreaded FastAPI app.
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

# Create a session factory.
# SessionLocal() will be used to get a database session in your API endpoints.
# - autoflush=False: Changes are not automatically flushed to the database.
# - autocommit=False: You must explicitly commit changes.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Base class for all ORM models.
# All your models should inherit from Base.
Base = declarative_base()


def get_db() -> Generator:
    """
    FastAPI dependency that yields a SQLAlchemy session and ensures it's closed.
    Usage: `db: Session = Depends(get_db)`
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
