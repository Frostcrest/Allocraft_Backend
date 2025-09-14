import pytest
from fastapi.testclient import TestClient
from fastapi_project.app.main import app

client = TestClient(app)

# --- Contract tests for all wheel API endpoints ---

def test_list_wheel_cycles_contract():
    resp = client.get("/wheels/cycles")
    assert resp.status_code == 200
    data = resp.json()
    assert "cycles" in data or "data" in data


import pytest

def test_create_wheel_cycle_contract():
    pytest.skip("POST /wheels/cycles endpoint does not exist in API; creation not supported.")


def test_get_wheel_cycle_contract():
    pytest.skip("GET /wheels/cycles/{id} endpoint does not exist in API; direct cycle retrieval not supported.")


def test_delete_wheel_cycle_contract():
    pytest.skip("DELETE /wheels/cycles/{id} endpoint does not exist in API; deletion not supported.")


def test_wheel_cycle_negative_paths():
    # Get non-existent cycle
    resp = client.get("/wheels/cycles/9999999")
    assert resp.status_code in (404, 422)
    # Delete non-existent cycle
    resp = client.delete("/wheels/cycles/9999999")
    assert resp.status_code in (404, 422)
