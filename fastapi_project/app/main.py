"""
Allocraft FastAPI App

Beginner guide:
- Serves the API and a simple static UI at '/'.

# --- Routers ---
from .routers import stocks, options, wheels, tickers, auth, users, importer, dashboard, schwab, portfolio_fast  # noqa: E402

app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(options.router)
app.include_router(wheels.router)
app.include_router(tickers.router)
app.include_router(users.router)
app.include_router(importer.router)
app.include_router(dashboard.router)
app.include_router(schwab.router)
app.include_router(portfolio_fast.router)  # Fast unified portfolio with progress trackinghe Vite dev server (http://localhost:5173) by default.
- On startup, auto-imports Wheel Tracker CSVs from SEED_DROP_DIR or fastapi_project/seed_drop.
- Ensures a default admin user exists (admin/admin123) for convenience.
"""

from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .limiter import limiter
from .database import Base, engine, SessionLocal
# Import models before calling create_all to ensure all tables are registered
from . import models  # noqa: F401 - imports all models from models.py
from . import models_unified  # noqa: F401 - imports unified models for new tables
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

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger = logging.getLogger(__name__)

# Configure root logging once (INFO default)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

# --- CORS configuration ---
# Environment variable override for CORS origins
env_origins = os.getenv("FRONTEND_ORIGINS", "")
if env_origins:
    origins = [origin.strip() for origin in env_origins.split(",") if origin.strip()]
else:
    origins = [
        "http://localhost:5173",
        "http://localhost:5174",  # Added for when 5173 is in use
        "http://localhost:5175",  # Added for when 5174 is in use
        "http://127.0.0.1:5173",  # Include 127.0.0.1 variants
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://localhost:8000",  # Backend self-requests
        "http://127.0.0.1:8000",  # Backend self-requests
        "http://localhost:8001",
        "https://allocraft.app",
        "https://www.allocraft.app"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
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

@app.get("/health", tags=["Meta"])
def health():
    """Lightweight health endpoint.

    Returns status, app version, UTC time, and a best-effort database connectivity flag.
    Fails open on DB errors (no exception propagation) so health remains responsive.
    """
    from sqlalchemy import text
    db_ok = False
    try:
        db = SessionLocal()
        try:
            # Minimal connectivity probe
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception:
        db_ok = False

    return {
        "status": "ok",
        "version": app.version,
        "db_connected": db_ok,
        "time_utc": datetime.now(UTC).isoformat(),
    }

# --- Database Initialization ---
Base.metadata.create_all(bind=engine)


# --- Ensure a default admin user exists ---
from .startup_admin import ensure_default_admin
ensure_default_admin()

# --- Routers ---
from .routers import stocks, options, wheels, tickers, auth, users, importer, dashboard, schwab, portfolio_fast, portfolio, stocks_fast  # noqa: E402

app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(options.router)
app.include_router(wheels.router)
app.include_router(tickers.router)
app.include_router(users.router)
app.include_router(importer.router)
app.include_router(dashboard.router)
app.include_router(schwab.router)
app.include_router(portfolio.router)  # Portfolio import/export
app.include_router(portfolio_fast.router)  # Fast unified portfolio with progress tracking
app.include_router(stocks_fast.router)  # Ultra-fast stocks endpoint


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
    except Exception as e:
        logger.warning("Failed to fetch option expiries for %s: %s", ticker, e)
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
    except Exception as e:
        logger.warning("Failed to fetch wheel expiries for %s: %s", ticker, e)
        return []

# --- Optional: Seed-drop CSV importer on startup ---

# --- Seed-drop CSV importer on startup ---
from .seed_importer import import_seed_drop_folder

seed_drop_dir = os.getenv("SEED_DROP_DIR")
if not seed_drop_dir:
    # default to a repo-local folder for convenience
    seed_drop_dir = str((BASE_DIR.parent / "seed_drop").resolve())

# Import synchronously during startup; folder-based and idempotent
import_seed_drop_folder(seed_drop_dir)