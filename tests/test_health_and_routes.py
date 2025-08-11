import pytest

def test_healthz(test_client):
    r = test_client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_option_expiries_returns_list(test_client):
    # This will hit yfinance; in CI you might mock it. Here we just assert it returns a list or empty.
    r = test_client.get("/option_expiries/AAPL")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
