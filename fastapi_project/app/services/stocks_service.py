from sqlalchemy.orm import Session
from .. import models, schemas, crud
from typing import List

class StocksService:

    @staticmethod
    def upload_stock_csv(contents: bytes, db: Session) -> int:
        import csv, io
        decoded = contents.decode("utf-8", errors="ignore").splitlines()
        reader = csv.DictReader(decoded)
        created = []
        for raw_row in reader:
            try:
                row = { (k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items() }
                ticker = row.get("ticker")
                if not ticker or ticker.lower() == "total":
                    continue
                shares_str = row.get("shares")
                cost_basis_str = row.get("cost_basis") or row.get("basis") or row.get("avg_cost") or row.get("average_cost")
                if not shares_str or not cost_basis_str:
                    continue
                shares = float(shares_str)
                cost_basis = float(cost_basis_str)
                db_stock = models.Stock(
                    ticker=ticker.upper(),
                    shares=shares,
                    cost_basis=cost_basis,
                    market_price=None,
                    status=row.get("status") or "Open",
                    entry_date=row.get("entry_date") or row.get("date") or None,
                    current_price=None,
                    price_last_updated=None,
                )
                db.add(db_stock)
                created.append(db_stock)
            except Exception:
                continue
        db.commit()
        return len(created)
    @staticmethod
    def create_stock(db: Session, stock: 'schemas.StockCreate'):
        return crud.create_stock(db, stock)

    @staticmethod
    def update_stock(db: Session, stock_id: int, stock: 'schemas.StockCreate'):
        return crud.update_stock(db, stock_id, stock)

    @staticmethod
    def delete_stock(db: Session, stock_id: int) -> bool:
        return crud.delete_stock(db, stock_id)
    @staticmethod
    def read_stocks(db: Session, skip: int = 0, limit: int = 1000) -> List[dict]:
        from ..models_unified import Position
        equity_positions = db.query(Position).filter(
            Position.asset_type.in_(["EQUITY", "COLLECTIVE_INVESTMENT"]),
            Position.is_active == True
        ).offset(skip).limit(limit).all()
        stocks = []
        for pos in equity_positions:
            net_quantity = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            stock_data = {
                "id": pos.id,
                "ticker": pos.symbol,
                "shares": net_quantity,
                "cost_basis": pos.average_price or 0.0,
                "market_price": pos.current_price or 0.0,
                "status": pos.status or "Open",
                "current_price": pos.current_price or 0.0,
                "entry_date": pos.entry_date,
                "price_last_updated": None
            }
            stocks.append(stock_data)
        return stocks

    @staticmethod
    def get_all_positions(db: Session) -> dict:
        from ..models_unified import Position, Account
        positions = []
        all_positions = db.query(Position).filter(Position.is_active == True).all()
        accounts = {acc.id: acc for acc in db.query(Account).all()}
        for pos in all_positions:
            account = accounts.get(pos.account_id)
            net_quantity = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            position_data = {
                "id": f"unified_{pos.id}",
                "symbol": pos.symbol,
                "shares": abs(net_quantity) if pos.asset_type in ["EQUITY", "COLLECTIVE_INVESTMENT"] else 0,
                "costBasis": pos.average_price or 0,
                "marketPrice": (pos.market_value or 0) / abs(net_quantity) if net_quantity != 0 else 0,
                "marketValue": pos.market_value or 0,
                "profitLoss": pos.current_day_profit_loss or 0,
                "source": pos.data_source or "unknown",
                "accountType": account.account_type if account else "Unknown",
                "accountNumber": account.account_number if account else "Unknown",
                "brokerage": account.brokerage if account else "Unknown",
                "isOption": pos.asset_type == "OPTION",
                "isShort": net_quantity < 0,
                "assetType": pos.asset_type,
                "status": pos.status
            }
            if pos.asset_type == "OPTION":
                position_data.update({
                    "underlyingSymbol": pos.underlying_symbol,
                    "optionType": pos.option_type,
                    "strikePrice": pos.strike_price,
                    "expirationDate": pos.expiration_date.isoformat() if pos.expiration_date else None,
                    "contracts": abs(net_quantity)
                })
            positions.append(position_data)
        return {
            "positions": positions,
            "summary": {
                "total_positions": len(positions),
                "manual_positions": len([p for p in positions if p["source"] == "manual"]),
                "schwab_positions": len([p for p in positions if "schwab" in p["source"]]),
                "accounts": len(accounts),
                "equity_positions": len([p for p in positions if not p["isOption"]]),
                "option_positions": len([p for p in positions if p["isOption"]]),
                "total_market_value": sum(p["marketValue"] for p in positions),
            }
        }
