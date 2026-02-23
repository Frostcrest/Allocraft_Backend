"""
Admin user creation logic for Allocraft FastAPI app startup.
Extracted from main.py for clarity and testability.
"""
import logging
import os
import secrets

from .database import SessionLocal

logger = logging.getLogger(__name__)


def ensure_default_admin() -> None:
    """Create a default admin user if one does not already exist.

    Password is read from the ADMIN_PASSWORD environment variable.
    If not set in development, a random password is generated and logged once
    so the developer can copy it.
    In production (ENVIRONMENT=production), the app refuses to start without
    ADMIN_PASSWORD explicitly set.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    password = os.getenv("ADMIN_PASSWORD", "")

    if not password:
        if environment == "production":
            raise RuntimeError(
                "ADMIN_PASSWORD env var must be set in production. "
                "The server refuses to create a default admin with a known password."
            )
        password = secrets.token_urlsafe(16)
        logger.warning(
            "ADMIN_PASSWORD not set — generated a random admin password: %s "
            "(set ADMIN_PASSWORD in your .env to override)",
            password,
        )

    try:
        from .models import User  # local import to avoid circular imports at module load
        from .utils.security import hash_password

        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.username == "admin").first()
            if not existing:
                user = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=hash_password(password),
                    is_active=True,
                    roles="admin",
                )
                db.add(user)
                db.commit()
                logger.info("Default admin user created.")
        finally:
            db.close()
    except Exception:
        logger.error("Failed to create default admin user — DB may be unavailable.", exc_info=True)
