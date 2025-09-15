import pytest
from schwab_transform_service import transform_wheels
import json

# Load a small sample of Schwab transactions (mocked for test)
SAMPLE_TRANSACTIONS = [
    {
        "symbol": "AAPL",
        "transactionType": "SELL",
        "description": "Sold to Open Put",
        "quantity": 1,
        "amount": 100.0,
        "date": "2025-01-01",
    },
    {
        "symbol": "AAPL",
        "transactionType": "BUY",
        "description": "Bought to Close Put",
        "quantity": 1,
        "amount": -50.0,
        "date": "2025-01-08",
    },
    {
        "symbol": "AAPL",
        "transactionType": "ASSIGNMENT",
        "description": "Put Assigned",
        "quantity": 100,
        "amount": -10000.0,
        "date": "2025-01-15",
    },
    {
        "symbol": "AAPL",
        "transactionType": "SELL",
        "description": "Sold to Open Call",
        "quantity": 1,
        "amount": 120.0,
        "date": "2025-01-22",
    },
    {
        "symbol": "AAPL",
        "transactionType": "BUY",
        "description": "Bought to Close Call",
        "quantity": 1,
        "amount": -60.0,
        "date": "2025-01-29",
    },
    {
        "symbol": "AAPL",
        "transactionType": "SELL",
        "description": "Sold 100 shares",
        "quantity": 100,
        "amount": 11000.0,
        "date": "2025-02-05",
    },
]

def test_transform_wheels_basic():
    cycles = transform_wheels(SAMPLE_TRANSACTIONS)
    assert isinstance(cycles, list)
    assert len(cycles) > 0
    # Each cycle should have a symbol and events
    for cycle in cycles:
        assert "symbol" in cycle
        assert isinstance(cycle["events"], list)
        assert any(e["type"] == "put_sold_to_open" for e in cycle["events"])
        # Should close on assignment or sale
        if cycle["status"] == "Closed":
            assert any(e["type"] in ("put_assigned", "stock_sold_100", "option_expired", "call_assigned") for e in cycle["events"])
