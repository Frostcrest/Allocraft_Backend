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

import uuid

def test_wheel_status_transitions(db):
    # Create a wheel cycle with a unique key
    from fastapi_project.app import schemas
    unique_key = f"CP4-STATUS-{uuid.uuid4()}"
    payload = schemas.WheelCycleCreate(
        cycle_key=unique_key,
        ticker="STATUS",
        strategy_type="full_wheel",
        status="Open"
    )
    cycle = WheelService.create_wheel_cycle(db, payload)
    # Simulate status transitions by updating the cycle with new status
    from fastapi_project.app import crud
    for new_status in ["Closed", "Open"]:
        update_payload = schemas.WheelCycleCreate(
            cycle_key=cycle.cycle_key,
            ticker=cycle.ticker,
            strategy_type=cycle.strategy_type,
            status=new_status
        )
        WheelService.update_wheel_cycle(db, cycle.id, update_payload)
        updated = crud.get_wheel_cycle(db, cycle.id)
        assert updated.status == new_status
    # Cleanup
    WheelService.delete_wheel_cycle(db, cycle.id)
