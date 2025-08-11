import pytest


def test_stocks_crud_flow(test_client):
    # List empty
    r = test_client.get("/stocks/")
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
    r = test_client.post("/stocks/", json=payload)
    assert r.status_code == 200
    created = r.json()
    assert created["ticker"] == "TEST"

    # Update
    new_payload = dict(payload)
    new_payload["shares"] = 20
    r = test_client.put(f"/stocks/{created['id']}", json=new_payload)
    assert r.status_code == 200
    updated = r.json()
    assert updated["shares"] == 20

    # Delete
    r = test_client.delete(f"/stocks/{created['id']}")
    assert r.status_code == 200

    # Back to baseline
    r = test_client.get("/stocks/")
    assert r.status_code == 200
    assert len(r.json()) == baseline
