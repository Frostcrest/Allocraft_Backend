from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


from . import models, schemas, crud
from .database import SessionLocal, engine, Base


app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)



# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/positions/", response_model=schemas.PositionRead)
def create_position(position: schemas.PositionCreate, db: Session = Depends(get_db)):
    return crud.create_position(db, position)

@app.get("/positions/", response_model=list[schemas.PositionRead])
def read_positions(db: Session = Depends(get_db)):
    return crud.get_positions(db)

@app.delete("/positions/{position_id}")
def delete_position(position_id: int, db: Session = Depends(get_db)):
    return crud.delete_position(db, position_id)

@app.post("/tickers/", response_model=schemas.TickerRead)
def create_ticker_endpoint(ticker: schemas.TickerCreate, db: Session = Depends(get_db)):
    # ticker.symbol is the only field expected
    return crud.create_ticker(db, ticker.symbol)

@app.get("/tickers/", response_model=list[schemas.TickerRead])
def read_tickers(symbol: str = None, db: Session = Depends(get_db)):
    if symbol:
        return [crud.get_ticker_by_symbol(db, symbol)]
    return crud.get_tickers(db)

@app.delete("/tickers/{ticker_id}")
def delete_ticker(ticker_id: int, db: Session = Depends(get_db)):
    return crud.delete_ticker(db, ticker_id)


app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")