from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.database import SessionLocal, engine, Base

app = FastAPI(
    title="Allocraft API",
    description="A clean, well-structured FastAPI backend for positions and tickers management.",
    version="1.0.0"
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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
def read_stocks(db: Session = Depends(get_db)):
    return crud.get_stocks(db)

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

# --- LEAP Endpoints ---

@app.get("/leaps/", response_model=list[schemas.LEAPRead])
def read_leaps(db: Session = Depends(get_db)):
    return crud.get_leaps(db)

@app.post("/leaps/", response_model=schemas.LEAPRead)
def create_leap(leap: schemas.LEAPCreate, db: Session = Depends(get_db)):
    return crud.create_leap(db, leap)

@app.put("/leaps/{leap_id}", response_model=schemas.LEAPRead)
def update_leap(leap_id: int, leap: schemas.LEAPCreate, db: Session = Depends(get_db)):
    return crud.update_leap(db, leap_id, leap)

@app.delete("/leaps/{leap_id}")
def delete_leap(leap_id: int, db: Session = Depends(get_db)):
    success = crud.delete_leap(db, leap_id)
    if not success:
        raise HTTPException(status_code=404, detail="LEAP not found")
    return {"detail": "LEAP deleted"}

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