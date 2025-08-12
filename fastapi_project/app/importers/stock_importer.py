from pathlib import Path
import csv
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app import models, crud

def import_stock_csv(db: Session, csv_path: str) -> Dict[str, Any]:
    """
    Import a Stock CSV file from disk. Adds stocks if they don't already exist.
    Expected columns: ticker, shares, cost_basis, entry_date
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(csv_path)
    added = 0
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get("ticker", "").upper()
            shares = float(row.get("shares", 0))
            cost_basis = float(row.get("cost_basis", 0))
            entry_date = row.get("entry_date", "")
            # Check if stock already exists
            exists = db.query(models.Stock).filter(models.Stock.ticker == ticker, models.Stock.entry_date == entry_date).first()
            if not exists:
                stock = models.Stock(
                    ticker=ticker,
                    shares=shares,
                    cost_basis=cost_basis,
                    entry_date=entry_date,
                    status="Open",
                )
                db.add(stock)
                db.flush()
                added += 1
        db.commit()
    return {"added": added}
