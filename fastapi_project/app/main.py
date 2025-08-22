"""
Allocraft FastAPI App

Beginner guide:
- Serves the API and a simple static UI at '/'.
- CORS allows the Vite dev server (http://localhost:5173) by default.
- On startup, auto-imports Wheel Tracker CSVs from SEED_DROP_DIR or fastapi_project/seed_drop.
- Ensures a default admin user exists (admin/admin123) for convenience.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .database import Base, engine, SessionLocal
# Import models before calling create_all to ensure all tables are registered
from . import models  # noqa: F401
import os
from dotenv import load_dotenv
from datetime import datetime, UTC
import yfinance as yf
from pathlib import Path
from typing import Optional

# Load environment variables from a .env file (if present)
load_dotenv()

# --- FastAPI App Configuration ---
app = FastAPI(
    title="Allocraft API",
    description="FastAPI backend for Allocraft Lite (stocks, options, wheels, auth).",
    version="1.0.1",
)

# --- CORS configuration ---
frontend_origins = os.getenv("FRONTEND_ORIGINS", "")
allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]
if allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Default: allow any localhost HTTP origin (any port), suitable for Vite dev servers
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Static Files ---
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
def read_root():
    """Serve the static index.html at root."""
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/healthz", tags=["Meta"]) 
def healthz():
    return {"status": "ok"}

# --- Database Initialization ---
Base.metadata.create_all(bind=engine)

# --- Ensure a default admin user exists ---
def _ensure_default_admin():
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

_ensure_default_admin()

# --- Routers ---
from .routers import stocks, options, wheels, tickers, auth, users, importer, dashboard, schwab  # noqa: E402

app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(options.router)
app.include_router(wheels.router)
app.include_router(tickers.router)
app.include_router(users.router)
app.include_router(importer.router)
app.include_router(dashboard.router)
app.include_router(schwab.router)


# --- Expiry helper endpoints for local UI compatibility ---
@app.get("/option_expiries/{ticker}", tags=["Options"])
def get_option_expiries(ticker: str):
    """Return available option expiry dates for a ticker with days until expiry."""
    try:
        ticker = ticker.upper()
        yf_ticker = yf.Ticker(ticker)
        today = datetime.now(UTC).date()
        expiries = []
        for date_str in yf_ticker.options:
            expiry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days = (expiry_date - today).days
            expiries.append({"date": date_str, "days": days})
        return expiries
    except Exception:
        return []

@app.get("/wheel_expiries/{ticker}", tags=["Wheels"])
def get_wheel_expiries(ticker: str):
    """Return available option expiry dates for a ticker with days until expiry (wheel UI)."""
    try:
        ticker = ticker.upper()
        yf_ticker = yf.Ticker(ticker)
        today = datetime.now(UTC).date()
        expiries = []
        for date_str in yf_ticker.options:
            expiry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days = (expiry_date - today).days
            expiries.append({"date": date_str, "days": days})
        return expiries
    except Exception:
        return []

# --- Optional: Seed-drop CSV importer on startup ---
from fastapi import BackgroundTasks
from .database import SessionLocal

def _import_seed_drop_folder(folder: Optional[str]):
    if not folder:
        return
    try:
        basedir = Path(folder)
        if not basedir.exists() or not basedir.is_dir():
            return
        db = SessionLocal()
        try:
            # Wheels: only scan wheels subfolder
            wheels_dir = basedir / "wheels"
            if wheels_dir.exists() and wheels_dir.is_dir():
                from .importers.wheel_tracker import import_wheel_tracker_csv
                for csv_path in sorted(wheels_dir.glob("*.csv")):
                    try:
                        import_wheel_tracker_csv(db, str(csv_path))
                    except Exception:
                        continue
            # Stocks: scan stocks subfolder
            stocks_dir = basedir / "stocks"
            if stocks_dir.exists() and stocks_dir.is_dir():
                from .importers.stock_importer import import_stock_csv
                for csv_path in sorted(stocks_dir.glob("*.csv")):
                    try:
                        import_stock_csv(db, str(csv_path))
                    except Exception:
                        continue
            # Options: scan options subfolder
            options_dir = basedir / "options"
            if options_dir.exists() and options_dir.is_dir():
                from .importers.option_importer import import_option_csv
                for csv_path in sorted(options_dir.glob("*.csv")):
                    try:
                        import_option_csv(db, str(csv_path))
                    except Exception:
                        continue
        finally:
            db.close()
    except Exception:
        pass

seed_drop_dir = os.getenv("SEED_DROP_DIR")
if not seed_drop_dir:
    # default to a repo-local folder for convenience
    seed_drop_dir = str((BASE_DIR.parent / "seed_drop").resolve())

# Import synchronously during startup; folder-based and idempotent
_import_seed_drop_folder(seed_drop_dir)