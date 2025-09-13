from sqlalchemy.orm import Session
from .. import schemas, crud
from typing import List, Optional

class TickersService:
    @staticmethod
    def create_ticker(db: Session, ticker: schemas.TickerCreate):
        return crud.create_ticker(db, ticker.symbol)

    @staticmethod
    def read_tickers(db: Session, symbol: Optional[str] = None) -> List[schemas.TickerRead]:
        if symbol:
            ticker = crud.get_ticker_by_symbol(db, symbol)
            return [ticker] if ticker else []
        return crud.get_tickers(db)

    @staticmethod
    def get_ticker_by_id(db: Session, ticker_id: int):
        return crud.get_ticker_by_id(db, ticker_id)

    @staticmethod
    def delete_ticker(db: Session, ticker_id: int) -> bool:
        return crud.delete_ticker(db, ticker_id)
