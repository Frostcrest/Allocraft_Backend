import pytest
from fastapi_project.app.services.wheel_service import WheelService
from fastapi_project.app.database import SessionLocal

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_list_wheel_cycles(db):
    result = WheelService.list_wheel_cycles(db)
    assert isinstance(result, list)

def test_create_and_delete_wheel_cycle(db):
    from fastapi_project.app import schemas
    payload = schemas.WheelCycleCreate(
        ticker="TEST",
        strategy_type="full_wheel",
        status="active",
        initial_cash=10000.0
    )
    cycle = WheelService.create_wheel_cycle(db, payload)
    assert cycle.ticker == "TEST"
    deleted = WheelService.delete_wheel_cycle(db, cycle.id)
    assert deleted is True
