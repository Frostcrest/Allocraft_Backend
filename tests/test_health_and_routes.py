from fastapi.testclient import TestClient
from fastapi_project.app.main import app

client = TestClient(app)

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_option_expiries_returns_list():
    # This will hit yfinance; in CI you might mock it. Here we just assert it returns a list or empty.
    r = client.get("/option_expiries/AAPL")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
