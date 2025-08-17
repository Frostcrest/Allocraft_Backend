"""
Enhanced test configuration with better fixtures and utilities.

This module provides:
- Database fixtures with proper isolation
- Authentication helpers
- Mock data factories
- Performance testing utilities
"""

import pytest
import asyncio
from datetime import datetime, UTC
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app import models
from app.utils.security import hash_password

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def engine_fixture():
    """Create database engine for testing."""
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(engine_fixture) -> Generator[Session, None, None]:
    """
    Create a database session with automatic rollback for test isolation.
    Each test gets a fresh database state.
    """
    connection = engine_fixture.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with dependency override for database session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(db_session: Session) -> models.User:
    """Create a test user."""
    user = models.User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        is_active=True,
        roles="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def admin_user(db_session: Session) -> models.User:
    """Create an admin test user."""
    user = models.User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        is_active=True,
        roles="admin,user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def auth_headers(client: TestClient, test_user: models.User) -> dict:
    """Get authentication headers for test requests."""
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def admin_headers(client: TestClient, admin_user: models.User) -> dict:
    """Get authentication headers for admin requests."""
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# Factory fixtures for creating test data
@pytest.fixture
def wheel_cycle_factory(db_session: Session):
    """Factory for creating wheel cycles."""
    def _create_cycle(
        ticker: str = "AAPL",
        cycle_key: str = None,
        status: str = "Open",
        started_at: str = "2024-01-01"
    ) -> models.WheelCycle:
        if cycle_key is None:
            cycle_key = f"{ticker}-TEST-{datetime.now(UTC).timestamp()}"
        
        cycle = models.WheelCycle(
            ticker=ticker,
            cycle_key=cycle_key,
            status=status,
            started_at=started_at,
            notes="Test cycle"
        )
        db_session.add(cycle)
        db_session.commit()
        db_session.refresh(cycle)
        return cycle
    
    return _create_cycle

@pytest.fixture
def wheel_event_factory(db_session: Session):
    """Factory for creating wheel events."""
    def _create_event(
        cycle: models.WheelCycle,
        event_type: str = "BUY_SHARES",
        trade_date: str = "2024-01-01",
        **kwargs
    ) -> models.WheelEvent:
        event = models.WheelEvent(
            cycle_id=cycle.id,
            event_type=event_type,
            trade_date=trade_date,
            **kwargs
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)
        return event
    
    return _create_event

@pytest.fixture
def stock_factory(db_session: Session):
    """Factory for creating stocks."""
    def _create_stock(
        ticker: str = "AAPL",
        shares: float = 100,
        cost_basis: float = 150.0,
        **kwargs
    ) -> models.Stock:
        stock = models.Stock(
            ticker=ticker,
            shares=shares,
            cost_basis=cost_basis,
            entry_date="2024-01-01",
            status="Open",
            **kwargs
        )
        db_session.add(stock)
        db_session.commit()
        db_session.refresh(stock)
        return stock
    
    return _create_stock

@pytest.fixture
def lot_factory(db_session: Session):
    """Factory for creating lots."""
    def _create_lot(
        cycle: models.WheelCycle,
        status: str = "OPEN_UNCOVERED",
        acquisition_method: str = "OUTRIGHT_PURCHASE",
        **kwargs
    ) -> models.Lot:
        lot = models.Lot(
            cycle_id=cycle.id,
            ticker=cycle.ticker,
            status=status,
            acquisition_method=acquisition_method,
            acquisition_date="2024-01-01",
            **kwargs
        )
        db_session.add(lot)
        db_session.commit()
        db_session.refresh(lot)
        return lot
    
    return _create_lot

# Performance testing utilities
@pytest.fixture
def performance_monitor():
    """Monitor for tracking test performance."""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.measurements = {}
        
        def start(self, operation: str):
            self.start_time = time.perf_counter()
            return operation
        
        def stop(self, operation: str):
            if self.start_time is None:
                raise ValueError("Must call start() before stop()")
            
            duration = time.perf_counter() - self.start_time
            self.measurements[operation] = duration
            self.start_time = None
            return duration
        
        def assert_performance(self, operation: str, max_duration: float):
            """Assert that an operation completed within the specified time."""
            duration = self.measurements.get(operation)
            assert duration is not None, f"No measurement found for {operation}"
            assert duration <= max_duration, f"{operation} took {duration:.3f}s, expected <= {max_duration}s"
    
    return PerformanceMonitor()

# Mock external services
@pytest.fixture
def mock_price_service(monkeypatch):
    """Mock the price service to avoid external API calls in tests."""
    def mock_fetch_latest_price(ticker: str) -> float:
        # Return predictable test prices
        prices = {
            "AAPL": 150.0,
            "MSFT": 300.0,
            "GOOGL": 2500.0,
            "TSLA": 200.0
        }
        return prices.get(ticker, 100.0)
    
    def mock_fetch_yf_price(ticker: str) -> float:
        return mock_fetch_latest_price(ticker)
    
    monkeypatch.setattr("app.services.price_service.fetch_latest_price", mock_fetch_latest_price)
    monkeypatch.setattr("app.services.price_service.fetch_yf_price", mock_fetch_yf_price)

# Database performance optimization for tests
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Optimize SQLite for testing performance."""
    cursor = dbapi_connection.cursor()
    # Speed up SQLite for testing
    cursor.execute("PRAGMA journal_mode=MEMORY")
    cursor.execute("PRAGMA synchronous=OFF")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA cache_size=10000")
    cursor.close()

# Test data generators
class TestDataGenerator:
    """Generate realistic test data for comprehensive testing."""
    
    @staticmethod
    def generate_wheel_scenario(
        db_session: Session,
        ticker: str = "AAPL",
        num_events: int = 10
    ) -> tuple[models.WheelCycle, list[models.WheelEvent]]:
        """Generate a complete wheel trading scenario."""
        from app import crud
        
        # Create cycle
        cycle_create = {
            "ticker": ticker,
            "cycle_key": f"{ticker}-TEST",
            "started_at": "2024-01-01",
            "status": "Open"
        }
        cycle = crud.create_wheel_cycle(db_session, cycle_create)
        
        # Generate realistic sequence of events
        events = []
        event_types = [
            ("SELL_PUT_OPEN", {"strike": 140, "premium": 2.5, "contracts": 1}),
            ("ASSIGNMENT", {"strike": 140, "quantity_shares": 100}),
            ("SELL_CALL_OPEN", {"strike": 150, "premium": 3.0, "contracts": 1}),
            ("SELL_CALL_CLOSE", {"premium": 1.5, "contracts": 1}),
            ("SELL_CALL_OPEN", {"strike": 155, "premium": 2.8, "contracts": 1}),
            ("CALLED_AWAY", {"strike": 155, "quantity_shares": 100}),
        ]
        
        for i, (event_type, data) in enumerate(event_types[:min(num_events, len(event_types))]):
            event_create = {
                "cycle_id": cycle.id,
                "event_type": event_type,
                "trade_date": f"2024-01-{i+1:02d}",
                **data
            }
            event = crud.create_wheel_event(db_session, event_create)
            events.append(event)
        
        return cycle, events

@pytest.fixture
def test_data_generator():
    """Provide the test data generator."""
    return TestDataGenerator

# Custom assertions for domain-specific testing
def assert_lot_status(lot: models.Lot, expected_status: str):
    """Assert lot has expected status with helpful error message."""
    assert lot.status == expected_status, (
        f"Expected lot {lot.id} to have status {expected_status}, "
        f"but got {lot.status}"
    )

def assert_event_count(events: list, event_type: str, expected_count: int):
    """Assert correct number of events of specific type."""
    actual_count = sum(1 for e in events if e.event_type == event_type)
    assert actual_count == expected_count, (
        f"Expected {expected_count} {event_type} events, "
        f"but found {actual_count}"
    )

def assert_currency_equal(actual: float, expected: float, tolerance: float = 0.01):
    """Assert currency values are equal within tolerance."""
    assert abs(actual - expected) <= tolerance, (
        f"Expected ${expected:.2f}, but got ${actual:.2f} "
        f"(difference: ${abs(actual - expected):.2f})"
    )

# Export custom assertions
pytest.assert_lot_status = assert_lot_status
pytest.assert_event_count = assert_event_count
pytest.assert_currency_equal = assert_currency_equal
