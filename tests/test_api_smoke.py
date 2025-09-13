import pytest
from fastapi.testclient import TestClient
from fastapi_project.app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"

def test_wheels_cycles_list():
    response = client.get("/wheels/cycles")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)

def test_importer_scan_admin():
    # This test assumes admin auth is disabled for local/dev
    response = client.post("/importer/scan")
    assert response.status_code in (200, 404)  # 404 if seed folder missing

def test_users_me():
    response = client.get("/users/me")
    assert response.status_code in (200, 401)  # 401 if not authenticated
