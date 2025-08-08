"""
Seed the local SQLite database with sample data for testing the frontend.

Run from the backend project folder (fastapi_project):
    python -m app.seed_data

This script is idempotent: it only inserts data if the respective tables are empty.
"""

from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from . import models


def seed_stocks(db: Session) -> int:
    if db.query(models.Stock).count() > 0:
        return 0
    stocks = [
        models.Stock(
            ticker="AAPL",
            shares=20,
            cost_basis=150.0,
            market_price=None,
            status="Open",
            entry_date="2024-06-01",
            current_price=None,
            price_last_updated=None,
        ),
        models.Stock(
            ticker="MSFT",
            shares=10,
            cost_basis=320.5,
            market_price=None,
            status="Open",
            entry_date="2024-05-15",
            current_price=None,
            price_last_updated=None,
        ),
        models.Stock(
            ticker="TSLA",
            shares=5,
            cost_basis=210.0,
            market_price=None,
            status="Open",
            entry_date="2024-07-01",
            current_price=None,
            price_last_updated=None,
        ),
    ]
    db.add_all(stocks)
    db.commit()
    return len(stocks)


def seed_options(db: Session) -> int:
    if db.query(models.Option).count() > 0:
        return 0
    options = [
        models.Option(
            ticker="AAPL",
            option_type="Call",
            strike_price=160.0,
            expiry_date="2025-09-19",
            contracts=1,
            cost_basis=2.35,
            market_price_per_contract=None,
            status="Open",
            current_price=None,
        ),
        models.Option(
            ticker="MSFT",
            option_type="Put",
            strike_price=320.0,
            expiry_date="2025-10-17",
            contracts=2,
            cost_basis=3.10,
            market_price_per_contract=None,
            status="Open",
            current_price=None,
        ),
    ]
    db.add_all(options)
    db.commit()
    return len(options)


def seed_wheels(db: Session) -> int:
    if db.query(models.WheelStrategy).count() > 0:
        return 0
    wheels = [
        models.WheelStrategy(
            wheel_id="AAPL-W1",
            ticker="AAPL",
            trade_date="2025-08-01",
            sell_put_strike_price=155.0,
            sell_put_open_premium=2.2,
            sell_put_closed_premium=None,
            sell_put_status="Open",
            sell_put_quantity=1,
        ),
        models.WheelStrategy(
            wheel_id="MSFT-W1",
            ticker="MSFT",
            trade_date="2025-07-15",
            assignment_strike_price=320.0,
            assignment_shares_quantity=100,
            assignment_status="Closed",
            sell_call_strike_price=330.0,
            sell_call_open_premium=3.1,
            sell_call_closed_premium=3.0,
            sell_call_status="Closed",
            sell_call_quantity=1,
            called_away_strike_price=330.0,
            called_away_shares_quantity=100,
            called_away_status="Closed",
        ),
    ]
    db.add_all(wheels)
    db.commit()
    return len(wheels)


def main() -> None:
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed admin user if none exist
        if db.query(models.User).count() == 0:
            admin = models.User(
                username="admin",
                email="admin@example.com",
                hashed_password=__import__('app.utils.security', fromlist=['hash_password']).hash_password("admin123"),
                is_active=True,
                roles="admin,user",
            )
            db.add(admin)
            db.commit()
        s_count = seed_stocks(db)
        o_count = seed_options(db)
        w_count = seed_wheels(db)
        print(f"Seed complete: stocks={s_count}, options={o_count}, wheels={w_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
