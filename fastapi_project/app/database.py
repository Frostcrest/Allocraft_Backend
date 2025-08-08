"""
database.py
------------
This file manages the database connection and session for the FastAPI app.
It uses SQLAlchemy to connect to a SQLite database and provides a session factory
for use in other parts of the application.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# --- DATABASE CONFIGURATION ---

# The URL that tells SQLAlchemy how to connect to the SQLite database file.
# './test.db' means the database file will be created in the current directory.
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Create the SQLAlchemy engine.
# The 'connect_args' option is required for SQLite to allow usage in a multithreaded FastAPI app.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

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
