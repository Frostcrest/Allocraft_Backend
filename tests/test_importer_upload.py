import io
import pytest


def test_importer_upload_minimal_csv(test_client):
    # Minimal CSV with Symbol header and one stock buy row compatible with importer tolerance
    content = "Symbol,TEST\n\n,,,,,,,,,,,,,,,,\n,,,,,,,,,,,,,,,\n,,,,,,,,,,,,,,,\n,,,,,,,,,,,,,,,\n,,,,,,BUY,,,,,,,,\n".encode("utf-8")
    files = {"file": ("TEST.csv", io.BytesIO(content), "text/csv")}
    r = test_client.post("/importer/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "ok"
    summary = data.get("summary") or {}
    assert "cycle_id" in summary
    assert summary.get("ticker") == "TEST"


def test_importer_upload_idempotent_on_second_upload(test_client):
    content = "Symbol,TEST\n\n,,,,,,,,,,,,,,,,\n,,,,,,,,,,,,,,,\n,,,,,,,,,,,,,,,\n,,,,,,,,,,,,,,,\n,,,,,,BUY,,,,,,,,\n".encode("utf-8")
    files = {"file": ("TEST.csv", io.BytesIO(content), "text/csv")}
    # First upload
    r1 = test_client.post("/importer/upload", files=files)
    assert r1.status_code == 200
    # Second upload of the same file should be idempotent (no new events)
    files2 = {"file": ("TEST.csv", io.BytesIO(content), "text/csv")}
    r2 = test_client.post("/importer/upload", files=files2)
    assert r2.status_code == 200
    s2 = r2.json().get("summary") or {}
    assert s2.get("events_created_by_type") in ({}, None)
    assert s2.get("lots_created") in (0, None)
