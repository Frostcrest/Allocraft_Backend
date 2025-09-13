"""
Admin user creation logic for Allocraft FastAPI app startup.
Extracted from main.py for clarity and testability.
"""
from .database import SessionLocal

def ensure_default_admin() -> None:
    """Create a default admin user (admin/admin123) if missing.
    Intended for development; safe no-op if the user already exists.
    """
    try:
        from .models import User  # local import to avoid circulars at module import
        from .utils.security import hash_password
        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.username == "admin").first()
            if not existing:
                user = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=hash_password("admin123"),
                    is_active=True,
                    roles="admin",
                )
                db.add(user)
                db.commit()
        finally:
            db.close()
    except Exception:
        # Fail-open: do not crash app if DB is unavailable at import time
        pass
