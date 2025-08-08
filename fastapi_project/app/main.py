from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import Base, engine
import os
from dotenv import load_dotenv
from datetime import datetime
import yfinance as yf

# Load environment variables from a .env file (if present)
load_dotenv()

# --- FastAPI App Configuration ---
app = FastAPI(
    title="Allocraft API",
    description="FastAPI backend for Allocraft Lite (stocks, options, wheels, auth).",
    version="1.0.1",
)

# --- CORS configuration ---
frontend_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
def read_root():
    """Serve the static index.html at root."""
    return FileResponse("app/static/index.html")

@app.get("/healthz", tags=["Meta"]) 
def healthz():
    return {"status": "ok"}

# --- Database Initialization ---
Base.metadata.create_all(bind=engine)

# --- Routers ---
from app.routers import stocks, options, wheels, tickers, auth, users  # noqa: E402

app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(options.router)
app.include_router(wheels.router)
app.include_router(tickers.router)
app.include_router(users.router)


# --- Expiry helper endpoints for local UI compatibility ---
@app.get("/option_expiries/{ticker}", tags=["Options"])
def get_option_expiries(ticker: str):
    """Return available option expiry dates for a ticker with days until expiry."""
    try:
        ticker = ticker.upper()
        yf_ticker = yf.Ticker(ticker)
        today = datetime.utcnow().date()
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
        today = datetime.utcnow().date()
        expiries = []
        for date_str in yf_ticker.options:
            expiry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days = (expiry_date - today).days
            expiries.append({"date": date_str, "days": days})
        return expiries
    except Exception:
        return []