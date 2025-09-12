from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.database import SessionLocal
from app.models import SchwabAccount, SchwabPosition
from app.models_unified import Account, Position


client = TestClient(app)


def _reset_db():
    db = SessionLocal()
    try:
        db.query(SchwabPosition).delete()
        db.query(SchwabAccount).delete()
        db.query(Position).delete()
        db.query(Account).delete()
        db.commit()
    finally:
        db.close()


def _seed_schwab():
    db = SessionLocal()
    try:
        acc = SchwabAccount(
            account_number="ACC-123",
            hash_value="hash-123",
            account_type="MARGIN",
            is_day_trader=False,
            cash_balance=1000.0,
            buying_power=2000.0,
            total_value=5000.0,
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)

        pos = SchwabPosition(
            account_id=acc.id,
            symbol="HIMS",
            asset_type="EQUITY",
            underlying_symbol="HIMS",
            long_quantity=100.0,
            market_value=1000.0,
            average_price=9.5,
            current_day_profit_loss=5.0,
            is_active=True,
            raw_data="{}",
        )
        db.add(pos)
        db.commit()
    finally:
        db.close()


def test_bridge_sync_populates_unified_positions():
    _reset_db()
    _seed_schwab()

    # Run the bridge sync
    r = client.post("/portfolio/sync/from-schwab-tables")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["accounts_processed"] == 1
    assert payload["positions_created"] == 1

    # Verify unified positions endpoint returns the bridged position
    r2 = client.get("/portfolio/positions")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["total_positions"] == 1
    positions = body["positions"]
    assert positions[0]["symbol"] == "HIMS"
    assert positions[0]["asset_type"] == "EQUITY"
    assert positions[0]["status"] == "Open"
