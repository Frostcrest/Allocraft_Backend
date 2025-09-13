from sqlalchemy.orm import Session
from .. import models, schemas, crud
from typing import List

class OptionsService:

    @staticmethod
    def refresh_option_prices(db: Session) -> dict:
        from ..models_unified import Position
        from ..services.price_service import fetch_option_contract_price
        from ..utils.option_parser import parse_option_symbol
        from datetime import datetime, UTC
        option_positions = db.query(Position).filter(
            Position.asset_type == "OPTION",
            Position.is_active == True
        ).all()
        if not option_positions:
            return {"updated": 0, "failed": 0, "message": "No active option positions found"}
        updated_count = 0
        failed_count = 0
        failed_symbols = []
        for position in option_positions:
            try:
                parsed = parse_option_symbol(position.symbol)
                if not parsed:
                    failed_count += 1
                    failed_symbols.append(f"{position.symbol}: Could not parse symbol")
                    continue
                ticker = parsed['ticker']
                expiry_date = parsed['expiry_date']
                option_type = parsed['option_type']
                strike_price = parsed['strike_price']
                current_price = fetch_option_contract_price(
                    ticker=ticker,
                    expiry_date=expiry_date,
                    option_type=option_type,
                    strike_price=strike_price
                )
                if current_price is not None:
                    position.current_price = current_price
                    position.price_last_updated = datetime.now(UTC)
                    updated_count += 1
                else:
                    failed_count += 1
                    failed_symbols.append(f"{position.symbol}: No price data available")
            except Exception as e:
                failed_count += 1
                failed_symbols.append(f"{position.symbol}: {str(e)}")
                continue
        db.commit()
        return {
            "updated": updated_count,
            "failed": failed_count,
            "total_positions": len(option_positions),
            "failed_symbols": failed_symbols[:10] if failed_symbols else [],
            "message": f"Successfully updated {updated_count} of {len(option_positions)} option positions"
        }

    @staticmethod
    def upload_options_csv(contents: bytes, db: Session) -> int:
        import csv
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
                    cost_basis=float(row["cost_basis"]),
                    market_price_per_contract=None,
                    status=row.get("status", "Open"),
                    current_price=None,
                )
                db.add(db_option)
                created.append(db_option)
            except Exception:
                continue
        db.commit()
        return len(created)
    @staticmethod
    def read_options(db: Session) -> List[dict]:
        from ..models_unified import Position
        from ..utils.option_parser import parse_option_symbol
        option_positions = db.query(Position).filter(
            Position.asset_type == "OPTION",
            Position.is_active == True
        ).all()
        options = []
        for pos in option_positions:
            net_contracts = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            parsed = parse_option_symbol(pos.symbol)
            if parsed:
                ticker = parsed['ticker']
                option_type = parsed['option_type']
                strike_price = parsed['strike_price']
                expiry_date = parsed['expiry_date']
            else:
                symbol_parts = pos.symbol.split()
                ticker = symbol_parts[0] if len(symbol_parts) > 0 else pos.underlying_symbol or ""
                option_type = pos.option_type or ("Put" if "P" in pos.symbol else "Call")
                strike_price = pos.strike_price or 0.0
                expiry_date = pos.expiration_date.strftime("%Y-%m-%d") if pos.expiration_date else ""
            option_data = {
                "id": pos.id,
                "ticker": ticker,
                "option_type": option_type,
                "strike_price": strike_price,
                "expiry_date": expiry_date,
                "contracts": abs(net_contracts),
                "cost_basis": pos.average_price or 0.0,
                "market_price_per_contract": pos.current_price or 0.0,
                "status": pos.status or "Open",
                "current_price": pos.current_price or 0.0,
                "price_last_updated": pos.price_last_updated.isoformat() if pos.price_last_updated else None
            }
            options.append(option_data)
        return options

    @staticmethod
    def create_option(db: Session, option: 'schemas.OptionCreate'):
        return crud.create_option(db, option)

    @staticmethod
    def update_option(db: Session, option_id: int, option: 'schemas.OptionCreate'):
        return crud.update_option(db, option_id, option)

    @staticmethod
    def delete_option(db: Session, option_id: int) -> bool:
        return crud.delete_option(db, option_id)
