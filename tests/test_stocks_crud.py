from fastapi.testclient import TestClient
from fastapi_project.app.main import app

client = TestClient(app)


def test_stocks_crud_flow():
    # List empty
    r = client.get("/stocks/")
    assert r.status_code == 200
    baseline = len(r.json())

    # Create
    payload = {
        "ticker": "TEST",
        "shares": 10,
        "cost_basis": 100.0,
        "status": "Open",
        "entry_date": None
    }
    r = client.post("/stocks/", json=payload)
    assert r.status_code == 200
    created = r.json()
    assert created["ticker"] == "TEST"

    # Update
    new_payload = dict(payload)
    new_payload["shares"] = 20
    r = client.put(f"/stocks/{created['id']}", json=new_payload)
    assert r.status_code == 200
    updated = r.json()
    assert updated["shares"] == 20

    # Delete
    r = client.delete(f"/stocks/{created['id']}")
    assert r.status_code == 200

    # Back to baseline
    r = client.get("/stocks/")
    assert r.status_code == 200
    assert len(r.json()) == baseline
