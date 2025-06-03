from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.database import SessionLocal, engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/items/", response_model=schemas.ItemRead)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db=db, item=item)

@app.get("/items/", response_model=list[schemas.ItemRead])
def read_items(db: Session = Depends(get_db)):
    return crud.get_items(db=db)

@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, item_id)

@app.post("/tickers/", response_model=schemas.TickerRead)
def create_ticker(ticker: schemas.TickerCreate, db: Session = Depends(get_db)):
    return crud.create_ticker(db, ticker)

@app.get("/tickers/", response_model=list[schemas.TickerRead])
def read_tickers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_tickers(db, skip=skip, limit=limit)

@app.delete("/tickers/{ticker_id}")
def delete_ticker(ticker_id: int, db: Session = Depends(get_db)):
    return crud.delete_ticker(db, ticker_id)