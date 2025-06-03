from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.database import SessionLocal, engine, Base

from . import models, schemas, crud
from .database import SessionLocal, engine, Base

from app.schemas import PositionCreate

app = FastAPI(
    title="Allocraft API",
    description="A clean, well-structured FastAPI backend for positions and tickers management.",
    version="1.0.0"
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")
# --- Database Initialization ---
Base.metadata.create_all(bind=engine)

# --- Dependency ---
def get_db():
    """Yields a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Positions Endpoints

@app.get("/positions/", response_model=list[schemas.PositionRead])
def read_positions(db: Session = Depends(get_db)):
    return crud.get_positions(db)

@app.post("/positions/", response_model=schemas.PositionRead)
def create_position(position: schemas.PositionCreate, db: Session = Depends(get_db)):
    return crud.create_position(db, position)

@app.put("/positions/{position_id}", response_model=schemas.PositionRead)
def update_position_endpoint(position_id: int, position: schemas.PositionCreate, db: Session = Depends(get_db)):
    return crud.update_position(db, position_id, position)


@app.delete("/positions/{position_id}")
def delete_position(position_id: int, db: Session = Depends(get_db)):
    success = crud.delete_position(db, position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"detail": "Position deleted"}

# Option Positions Endpoints

@app.get("/option_positions/", response_model=list[schemas.OptionPositionRead])
def read_option_positions(db: Session = Depends(get_db)):
    return crud.get_option_positions(db)

@app.post("/option_positions/", response_model=schemas.OptionPositionRead)
def create_option_position(option_position: schemas.OptionPositionCreate, db: Session = Depends(get_db)):
    db_opt = models.OptionPosition(**option_position.dict())
    return crud.create_option_position(db, db_opt)

@app.put("/option_positions/{option_position_id}", response_model=schemas.OptionPositionRead)
def update_option_position(option_position_id: int, option_position: schemas.OptionPositionCreate, db: Session = Depends(get_db)):
    return crud.update_option_position(db, option_position_id, option_position.dict())

@app.delete("/option_positions/{option_position_id}")
def delete_option_position(option_position_id: int, db: Session = Depends(get_db)):
    success = crud.delete_option_position(db, option_position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Option position not found")
    return {"detail": "Option position deleted"}

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

# --- Static Files & Root ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
def read_root():
    """Serve the static index.html at root."""
    return FileResponse("app/static/index.html")