from pathlib import Path
import csv
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from .. import models, crud

def import_option_csv(db: Session, csv_path: str) -> Dict[str, Any]:
    """
    Import an Option CSV file from disk. Adds options if they don't already exist.
    Expected columns: ticker, option_type, strike_price, expiry_date, contracts, cost_basis
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(csv_path)
    added = 0
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get("ticker", "").upper()
            option_type = row.get("option_type", "Call").capitalize()
            strike_price = float(row.get("strike_price", 0))
            expiry_date = row.get("expiry_date", "")
            contracts = float(row.get("contracts", 0))
            cost_basis = float(row.get("cost_basis", 0))
            # Check if option already exists
            exists = db.query(models.Option).filter(
                models.Option.ticker == ticker,
                models.Option.option_type == option_type,
                models.Option.strike_price == strike_price,
                models.Option.expiry_date == expiry_date,
                models.Option.contracts == contracts
            ).first()
            if not exists:
                option = models.Option(
                    ticker=ticker,
                    option_type=option_type,
                    strike_price=strike_price,
                    expiry_date=expiry_date,
                    contracts=contracts,
                    cost_basis=cost_basis,
                    status="Open",
                )
                db.add(option)
                db.flush()
                added += 1
        db.commit()
    return {"added": added}
