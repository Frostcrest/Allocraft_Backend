from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.database import SessionLocal, engine, Base
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import io
import csv
from datetime import datetime

app = FastAPI(
    title="Allocraft API",
    description="A clean, well-structured FastAPI backend for positions and tickers management.",
    version="1.0.0"
)

# CORS configuration
origins = [
    "http://localhost:5173",
    # Add other origins if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
def read_root():
    """Serve the static index.html at root."""
    return FileResponse("app/static/index.html")

# --- Database Initialization ---
Base.metadata.create_all(bind=engine)

# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Stock Endpoints ---

@app.get("/stocks/", response_model=list[schemas.StockRead])
def read_stocks(db: Session = Depends(get_db), refresh_prices: bool = False):
    """
    Get all stocks. Optionally refresh prices by passing ?refresh_prices=true
    """
    return crud.get_stocks(db, refresh_prices=refresh_prices)

@app.post("/stocks/", response_model=schemas.StockRead)
def create_stock(stock: schemas.StockCreate, db: Session = Depends(get_db)):
    return crud.create_stock(db, stock)

@app.put("/stocks/{stock_id}", response_model=schemas.StockRead)
def update_stock(stock_id: int, stock: schemas.StockCreate, db: Session = Depends(get_db)):
    return crud.update_stock(db, stock_id, stock)

@app.delete("/stocks/{stock_id}")
def delete_stock(stock_id: int, db: Session = Depends(get_db)):
    success = crud.delete_stock(db, stock_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"detail": "Stock deleted"}

@app.get("/stocks/template", tags=["Stocks"])
def download_stock_csv_template():
    """
    Download a CSV template for stock positions.
    """
    csv_content = "ticker,shares,cost_basis,status,entry_date\n"
    csv_content += "AAPL,10,150.00,Open,2024-06-01\n"
    csv_content += "MSFT,5,320.50,Sold,2024-05-15\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stock_template.csv"}
    )

@app.post("/stocks/upload", tags=["Stocks"])
async def upload_stock_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for row in reader:
        try:
            db_stock = models.Stock(
                ticker=row["ticker"].strip().upper(),
                shares=float(row["shares"]),
                cost_basis=float(row["cost_basis"]),
                market_price=None,
                status=row.get("status", "Open"),
                entry_date=row.get("entry_date") or None,
                current_price=None,
                price_last_updated=None,
            )
            db.add(db_stock)
            created.append(db_stock)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}

# --- Option Endpoints ---

@app.get("/options/", response_model=list[schemas.OptionRead])
def read_options(db: Session = Depends(get_db)):
    return crud.get_options(db)

@app.post("/options/", response_model=schemas.OptionRead)
def create_option(option: schemas.OptionCreate, db: Session = Depends(get_db)):
    return crud.create_option(db, option)

@app.put("/options/{option_id}", response_model=schemas.OptionRead)
def update_option(option_id: int, option: schemas.OptionCreate, db: Session = Depends(get_db)):
    return crud.update_option(db, option_id, option)

@app.delete("/options/{option_id}")
def delete_option(option_id: int, db: Session = Depends(get_db)):
    success = crud.delete_option(db, option_id)
    if not success:
        raise HTTPException(status_code=404, detail="Option not found")
    return {"detail": "Option deleted"}

# --- Ticker Endpoints ---
@app.post("/tickers/", response_model=schemas.TickerRead, tags=["Tickers"])
def create_ticker_endpoint(ticker: schemas.TickerCreate, db: Session = Depends(get_db)):
    """Create a new ticker by symbol (fetches from external API if needed)."""
    return crud.create_ticker(db, ticker.symbol)

@app.get("/tickers/", response_model=list[schemas.TickerRead], tags=["Tickers"])
def read_tickers(symbol: str = None, db: Session = Depends(get_db)):
    """Get all tickers, or a single ticker by symbol if provided."""
    if symbol:
        ticker = crud.get_ticker_by_symbol(db, symbol)
        return [ticker] if ticker else []
    return crud.get_tickers(db)

@app.get("/tickers/{ticker_id}", response_model=schemas.TickerRead, tags=["Tickers"])
def get_ticker_by_id(ticker_id: int, db: Session = Depends(get_db)):
    """Get a single ticker by its ID."""
    return crud.get_ticker_by_id(db, ticker_id)

@app.delete("/tickers/{ticker_id}", tags=["Tickers"])
def delete_ticker(ticker_id: int, db: Session = Depends(get_db)):
    """Delete a ticker by ID."""
    return crud.delete_ticker(db, ticker_id)

# --- WheelStrategy Endpoints ---

@app.get("/wheels/", response_model=list[schemas.WheelStrategyRead])
def read_wheels(db: Session = Depends(get_db)):
    return crud.get_wheels(db)

@app.post("/wheels/", response_model=schemas.WheelStrategyRead)
def create_wheel(wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    return crud.create_wheel(db, wheel)

@app.put("/wheels/{wheel_id}", response_model=schemas.WheelStrategyRead)
def update_wheel(wheel_id: int, wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    return crud.update_wheel(db, wheel_id, wheel)

@app.delete("/wheels/{wheel_id}")
def delete_wheel(wheel_id: int, db: Session = Depends(get_db)):
    success = crud.delete_wheel(db, wheel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Wheel strategy not found")
    return {"detail": "Wheel strategy deleted"}

@app.get("/option_expiries/{ticker}", tags=["Options"])
def get_option_expiries(ticker: str):
    """
    Return all available option expiry dates for the given ticker, with days until expiry.
    """
    import yfinance as yf
    from datetime import datetime
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
    """
    Return all available option expiry dates for the given ticker, with days until expiry.
    """
    import yfinance as yf
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

# --- Options Template Download ---
@app.get("/options/template", tags=["Options"])
def download_options_csv_template():
    csv_content = "ticker,option_type,strike_price,expiration_date,quantity,cost_basis,status,entry_date\n"
    csv_content += "AAPL,call,150,2024-07-19,1,2.50,Open,2024-06-01\n"
    csv_content += "MSFT,put,320,2024-08-16,2,3.10,Closed,2024-05-15\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=options_template.csv"}
    )

@app.post("/options/upload", tags=["Options"])
async def upload_options_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for row in reader:
        try:
            db_option = models.Option(
                ticker=row["ticker"].strip().upper(),
                option_type=row["option_type"].strip().capitalize(),
                strike_price=float(row["strike_price"]),
                expiry_date=row["expiration_date"],
                contracts=float(row["quantity"]),
                cost_basis=float(row["cost_basis"]),  # <-- Now using cost_basis
                market_price_per_contract=None,
                status=row.get("status", "Open"),
                current_price=None,
            )
            db.add(db_option)
            created.append(db_option)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}

# --- Wheel Strategies Template Download ---
@app.get("/wheels/template", tags=["Wheels"])
def download_wheels_csv_template():
    csv_content = "ticker,strike_price,expiration_date,quantity,premium,call_put,status,trade_date\n"
    csv_content += "AAPL,150,2024-07-19,1,2.50,Put,Open,2024-06-01\n"
    csv_content += "MSFT,320,2024-08-16,2,3.10,Call,Closed,2024-05-15\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wheels_template.csv"}
    )

@app.post("/wheels/upload", tags=["Wheels"])
async def upload_wheels_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for row in reader:
        try:
            db_wheel = models.WheelStrategy(
                wheel_id=row.get("wheel_id") or f"{row['ticker'].strip().upper()}-W",
                ticker=row["ticker"].strip().upper(),
                trade_type=row.get("trade_type", "Sell Put"),
                trade_date=row.get("trade_date"),
                strike_price=float(row["strike_price"]) if row.get("strike_price") else None,
                premium_received=float(row["premium"]) if row.get("premium") else None,
                status=row.get("status", "Active"),
                call_put=row.get("call_put", None),  # <-- New field
            )
            db.add(db_wheel)
            created.append(db_wheel)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}

@app.post("/refresh_all_prices", tags=["Admin"])
def refresh_all_prices(db: Session = Depends(get_db)):
    """
    Refresh prices for all stocks and options in the database.
    """
    # Stocks
    stocks = db.query(models.Stock).all()
    for stock in stocks:
        try:
            price, updated = crud.fetch_latest_price(stock.ticker)
            stock.current_price = price
            stock.price_last_updated = updated
        except Exception:
            continue

    # Options
    options = db.query(models.Option).all()
    for opt in options:
        try:
            price = crud.fetch_option_contract_price(
                opt.ticker, opt.expiry_date, opt.option_type, opt.strike_price
            )
            opt.market_price_per_contract = price
            opt.current_price = price
        except Exception:
            continue

    db.commit()
    return {"detail": "Prices refreshed"}

@app.get("/options/refresh_prices")
def refresh_option_prices():
    """
    Refresh the market prices of options contracts for all tickers in the database.
    """
    db = next(get_db())
    tickers = db.query(models.Ticker).all()
    for ticker in tickers:
        try:
            # For each ticker, refresh the prices of its associated options
            options = db.query(models.Option).filter(models.Option.ticker == ticker.symbol).all()
            for option in options:
                try:
                    price = crud.fetch_option_contract_price(
                        option.ticker, option.expiry_date, option.option_type, option.strike_price
                    )
                    option.market_price_per_contract = price
                    option.current_price = price
                except Exception:
                    continue
        except Exception:
            continue
    db.commit()
    return {"detail": "Option prices refreshed"}