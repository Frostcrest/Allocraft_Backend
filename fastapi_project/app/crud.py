from sqlalchemy.orm import Session
from fastapi import HTTPException
from app import models, schemas


def create_item(db: Session, item: schemas.ItemCreate):
    db_item = models.Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def get_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Item).offset(skip).limit(limit).all()

def delete_item(db: Session, item_id: int):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


def create_ticker(db: Session, ticker: schemas.TickerCreate):
    db_ticker = models.Ticker(**ticker.dict())
    db.add(db_ticker)
    db.commit()
    db.refresh(db_ticker)
    return db_ticker

def get_tickers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Ticker).offset(skip).limit(limit).all()

def delete_ticker(db: Session, ticker_id: int):
    ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    db.delete(ticker)
    db.commit()
    return {"ok": True}
