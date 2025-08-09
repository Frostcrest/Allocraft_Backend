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


def seed_wheel_cycle_rigetti(db: Session) -> int:
    """Seed a WheelCycle and WheelEvents for Rigetti Computing Inc (RGTI).
    Data comes from the attached sheet snapshot (July–Aug 2025).
    Idempotent: only creates when cycle_key not present.
    """
    cycle_key = "RGTI-1"
    existing = db.query(models.WheelCycle).filter(models.WheelCycle.cycle_key == cycle_key).first()
    if existing:
        cycle = existing
    else:
        # Create cycle
        cycle = models.WheelCycle(
            cycle_key=cycle_key,
            ticker="RGTI",
            started_at="2025-07-09",
            status="Open",
            notes="Seeded from Rigetti sheet (calls/puts + stock buys)",
        )
        db.add(cycle)
        db.flush()  # get cycle.id

    # If this cycle already has events, skip to keep idempotency
    if db.query(models.WheelEvent).filter(models.WheelEvent.cycle_id == cycle.id).count() > 0:
        return 0

    created = 0

    def add_evt(**kwargs):
        nonlocal created
        evt = models.WheelEvent(cycle_id=cycle.id, **kwargs)
        db.add(evt)
        db.flush()
        created += 1
        return evt

    # Stock buys (right table)
    add_evt(event_type="BUY_SHARES", trade_date="2025-07-09", quantity_shares=100, price=12.94, fees=0.0)
    add_evt(event_type="BUY_SHARES", trade_date="2025-07-31", quantity_shares=100, price=14.51, fees=0.0)
    add_evt(event_type="BUY_SHARES", trade_date="2025-08-08", quantity_shares=29, price=14.74, fees=0.0)

    # Put sold then closed
    put_open = add_evt(event_type="SELL_PUT_OPEN", trade_date="2025-07-09", contracts=1, strike=12.00, premium=1.00, fees=0.0)
    add_evt(event_type="SELL_PUT_CLOSE", trade_date="2025-07-16", contracts=1, premium=0.46, fees=0.0, link_event_id=put_open.id)

    # Calls sold and closed
    c1_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-11", contracts=1, strike=13.00, premium=0.38, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-16", contracts=1, premium=2.57, fees=0.0, link_event_id=c1_open.id)

    c2_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-16", contracts=1, strike=16.00, premium=0.80, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-16", contracts=1, premium=0.97, fees=0.0, link_event_id=c2_open.id)

    c3_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-16", contracts=1, strike=16.00, premium=1.04, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-25", contracts=1, premium=0.05, fees=0.0, link_event_id=c3_open.id)

    c4_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-28", contracts=1, strike=16.00, premium=0.60, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-29", contracts=1, premium=0.30, fees=0.0, link_event_id=c4_open.id)

    c5_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-30", contracts=1, strike=15.00, premium=0.24, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-08-01", contracts=1, premium=0.02, fees=0.0, link_event_id=c5_open.id)

    # Open calls (still open as of 08/01)
    add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-08-01", contracts=1, strike=14.00, premium=0.63, fees=0.0)
    add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-08-01", contracts=1, strike=14.50, premium=0.64, fees=0.0)

    db.commit()
    return created


def seed_wheel_cycle_bigbear(db: Session) -> int:
    """Seed a WheelCycle and WheelEvents for BigBear.ai Holdings Inc (BBAI).
    Data captured from the attached sheet (July–Aug 2025).
    Idempotent: only creates when cycle_key not present or has no events.
    """
    cycle_key = "BBAI-1"
    existing = db.query(models.WheelCycle).filter(models.WheelCycle.cycle_key == cycle_key).first()
    if existing:
        cycle = existing
    else:
        cycle = models.WheelCycle(
            cycle_key=cycle_key,
            ticker="BBAI",
            started_at="2025-07-09",
            status="Open",
            notes="Seeded from BigBear.ai sheet (calls/puts + stock buys)",
        )
        db.add(cycle)
        db.flush()

    if db.query(models.WheelEvent).filter(models.WheelEvent.cycle_id == cycle.id).count() > 0:
        return 0

    created = 0

    def add_evt(**kwargs):
        nonlocal created
        evt = models.WheelEvent(cycle_id=cycle.id, **kwargs)
        db.add(evt)
        db.flush()
        created += 1
        return evt

    # Stock buys (right table)
    add_evt(event_type="BUY_SHARES", trade_date="2025-07-09", quantity_shares=100, price=7.19, fees=0.0)
    add_evt(event_type="BUY_SHARES", trade_date="2025-07-31", quantity_shares=100, price=6.65, fees=0.0)
    add_evt(event_type="BUY_SHARES", trade_date="2025-07-31", quantity_shares=100, price=6.41, fees=0.0)
    add_evt(event_type="BUY_SHARES", trade_date="2025-08-08", quantity_shares=13, price=6.51, fees=0.0)

    # 07/09/2025 Put sell -> closed 07/16
    p1_open = add_evt(event_type="SELL_PUT_OPEN", trade_date="2025-07-09", contracts=1, strike=6.00, premium=0.75, fees=0.0)
    add_evt(event_type="SELL_PUT_CLOSE", trade_date="2025-07-16", contracts=1, premium=0.55, fees=0.0, link_event_id=p1_open.id)

    # 07/11/2025 Call sell -> closed same day
    c1_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-11", contracts=1, strike=7.50, premium=0.40, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-11", contracts=1, premium=0.20, fees=0.0, link_event_id=c1_open.id)

    # 07/11/2025 Put sell -> closed 07/16
    p2_open = add_evt(event_type="SELL_PUT_OPEN", trade_date="2025-07-11", contracts=1, strike=6.50, premium=1.10, fees=0.0)
    add_evt(event_type="SELL_PUT_CLOSE", trade_date="2025-07-16", contracts=1, premium=0.90, fees=0.0, link_event_id=p2_open.id)

    # 07/11/2025 Call sell -> rolled/closed 07/16 at equal premium
    c2_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-11", contracts=1, strike=7.00, premium=0.30, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-16", contracts=1, premium=0.30, fees=0.0, link_event_id=c2_open.id)

    # 07/16/2025 Call sell -> closed 07/17 at loss
    c3_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-16", contracts=1, strike=7.50, premium=0.40, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-17", contracts=1, premium=0.82, fees=0.0, link_event_id=c3_open.id)

    # 07/17/2025 Call sell -> expired 07/25 (model as close at $0.10)
    c4_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-07-17", contracts=1, strike=8.00, premium=0.56, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-07-25", contracts=1, premium=0.10, fees=0.0, link_event_id=c4_open.id)

    # 08/01/2025 Put sell -> closed 08/04
    p3_open = add_evt(event_type="SELL_PUT_OPEN", trade_date="2025-08-01", contracts=1, strike=6.00, premium=0.55, fees=0.0)
    add_evt(event_type="SELL_PUT_CLOSE", trade_date="2025-08-04", contracts=1, premium=0.23, fees=0.0, link_event_id=p3_open.id)

    # 08/01/2025 Call sell 3x -> rolled/closed 08/08
    c5_open = add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-08-01", contracts=3, strike=6.50, premium=0.30, fees=0.0)
    add_evt(event_type="SELL_CALL_CLOSE", trade_date="2025-08-08", contracts=3, premium=0.57, fees=0.0, link_event_id=c5_open.id)

    # 08/08/2025 Call sell 3x -> still open
    add_evt(event_type="SELL_CALL_OPEN", trade_date="2025-08-08", contracts=3, strike=7.50, premium=0.63, fees=0.0)

    db.commit()
    return created

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
        r_count = seed_wheel_cycle_rigetti(db)
        b_count = seed_wheel_cycle_bigbear(db)
        print(f"Seed complete: stocks={s_count}, options={o_count}, wheels={w_count}, rigetti_events={r_count}, bbai_events={b_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
