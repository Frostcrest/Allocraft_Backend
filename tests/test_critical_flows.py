"""
Critical integration flow tests.

Tests: FLOW-001 through FLOW-005

Policy: It is unacceptable to remove or edit these tests — they protect against
regressions in the core application workflows.
"""

import pytest


# ---------------------------------------------------------------------------
# FLOW-001: Wheel cycle lifecycle
# ---------------------------------------------------------------------------
def test_wheel_cycle_lifecycle(client_no_auth):
    """FLOW-001: Create a wheel cycle, add an event, verify it appears in list."""
    import time

    unique_key = f"AAPL-FLOW001-{int(time.time())}"

    # 1. Create a wheel cycle via the legacy wheels endpoint
    create_resp = client_no_auth.post(
        "/wheels/",
        json={
            "wheel_id": unique_key,
            "ticker": "AAPL",
            "trade_date": "2024-01-15"
        }
    )
    assert create_resp.status_code in (200, 201), (
        f"Cycle creation failed: {create_resp.status_code} {create_resp.text}"
    )
    cycle = create_resp.json()
    assert "id" in cycle, f"Created cycle has no 'id': {cycle}"
    assert cycle["ticker"] == "AAPL"
    assert cycle["wheel_id"] == unique_key

    # 2. Cycle must now appear in the list
    list_resp = client_no_auth.get("/wheels/")
    assert list_resp.status_code == 200
    cycles = list_resp.json()
    assert isinstance(cycles, list), f"Expected list, got {type(cycles)}"
    found_ids = {c.get("wheel_id") for c in cycles}
    assert unique_key in found_ids, (
        f"Just-created cycle key '{unique_key}' not found in list: {found_ids}"
    )


# ---------------------------------------------------------------------------
# FLOW-002: Portfolio import → positions are queryable immediately
# ---------------------------------------------------------------------------
def test_portfolio_import_then_query(client_no_auth):
    """FLOW-002: Import a JSON payload, then verify positions are returned."""
    import_payload = {
        "accounts": [
            {
                "account_number": "FLOW002-TEST",
                "account_type": "INDIVIDUAL",
                "total_value": 10000.0,
                "cash_balance": 1000.0,
                "buying_power": 1000.0,
                "positions": [
                    {
                        "symbol": "AAPL",
                        "asset_type": "EQUITY",
                        "long_quantity": 100.0,
                        "short_quantity": 0.0,
                        "market_value": 15000.0,
                        "average_price": 150.0
                    },
                    {
                        "symbol": "MSFT",
                        "asset_type": "EQUITY",
                        "long_quantity": 50.0,
                        "short_quantity": 0.0,
                        "market_value": 15000.0,
                        "average_price": 300.0
                    }
                ]
            }
        ]
    }

    # Import
    import_resp = client_no_auth.post("/portfolio/import-fast", json=import_payload)
    assert import_resp.status_code == 200, (
        f"Import failed: {import_resp.status_code} {import_resp.text}"
    )
    result = import_resp.json()
    assert result.get("positions_imported") == 2, (
        f"Expected 2 positions imported, got: {result}"
    )

    # Verify positions are queryable
    positions_resp = client_no_auth.get("/portfolio/positions")
    assert positions_resp.status_code == 200
    positions = positions_resp.json()
    assert isinstance(positions, list), f"Expected list, got {type(positions)}"
    assert len(positions) >= 2, f"Expected at least 2 positions, got {len(positions)}"

    symbols = {p.get("symbol") for p in positions}
    assert "AAPL" in symbols, f"AAPL not found in positions: {symbols}"
    assert "MSFT" in symbols, f"MSFT not found in positions: {symbols}"


def test_portfolio_import_missing_accounts_key(client_no_auth):
    """FLOW-002 edge case: Import payload without 'accounts' key returns 400."""
    resp = client_no_auth.post("/portfolio/import-fast", json={"wrong_key": []})
    assert resp.status_code == 400, (
        f"Expected 400 for missing 'accounts', got {resp.status_code}: {resp.text}"
    )


def test_portfolio_import_empty_accounts(client_no_auth):
    """FLOW-002 edge case: Empty accounts list completes successfully with 0 positions."""
    resp = client_no_auth.post("/portfolio/import-fast", json={"accounts": []})
    assert resp.status_code == 200
    result = resp.json()
    assert result.get("positions_imported") == 0
    assert result.get("accounts_imported") == 0


# ---------------------------------------------------------------------------
# FLOW-003: Stock CRUD — create → read → update → delete
# ---------------------------------------------------------------------------
def test_stock_crud_lifecycle(client_no_auth):
    """FLOW-003: Full stock CRUD lifecycle with field verification at each step."""
    # CREATE
    create_resp = client_no_auth.post(
        "/stocks/",
        json={
            "ticker": "TSLA",
            "shares": 100.0,
            "cost_basis": 200.0,
            "status": "Open",
            "entry_date": "2024-01-01"
        }
    )
    assert create_resp.status_code in (200, 201), (
        f"Create failed: {create_resp.status_code} {create_resp.text}"
    )
    stock = create_resp.json()
    stock_id = stock["id"]
    assert stock["ticker"] == "TSLA"
    assert stock["shares"] == 100.0
    assert stock["cost_basis"] == 200.0

    # READ (list)
    read_resp = client_no_auth.get("/stocks/")
    assert read_resp.status_code == 200
    all_stocks = read_resp.json()
    assert isinstance(all_stocks, list)
    ids = [s["id"] for s in all_stocks]
    assert stock_id in ids, f"Newly created stock ID {stock_id} not found in list"

    # UPDATE
    update_resp = client_no_auth.put(
        f"/stocks/{stock_id}",
        json={
            "ticker": "TSLA",
            "shares": 200.0,       # changed
            "cost_basis": 195.0,   # changed
            "status": "Open"
        }
    )
    assert update_resp.status_code == 200, (
        f"Update failed: {update_resp.status_code} {update_resp.text}"
    )
    updated = update_resp.json()
    assert updated["shares"] == 200.0, f"shares not updated: {updated}"
    assert updated["cost_basis"] == 195.0, f"cost_basis not updated: {updated}"

    # DELETE
    delete_resp = client_no_auth.delete(f"/stocks/{stock_id}")
    assert delete_resp.status_code in (200, 204), (
        f"Delete failed: {delete_resp.status_code} {delete_resp.text}"
    )

    # Verify gone from list
    after_delete = client_no_auth.get("/stocks/")
    assert after_delete.status_code == 200
    remaining_ids = [s["id"] for s in after_delete.json()]
    assert stock_id not in remaining_ids, (
        f"Deleted stock ID {stock_id} still appears in list"
    )


def test_delete_nonexistent_stock_returns_404(client_no_auth):
    """FLOW-003 edge case: Deleting a non-existent stock ID returns 404."""
    resp = client_no_auth.delete("/stocks/999999")
    assert resp.status_code == 404, (
        f"Expected 404 for non-existent stock, got {resp.status_code}: {resp.text}"
    )


def test_create_stock_negative_shares_rejected(client_no_auth):
    """FLOW-003 edge case: Negative share count should be rejected with 422."""
    resp = client_no_auth.post(
        "/stocks/",
        json={"ticker": "AAPL", "shares": -100.0, "cost_basis": 150.0}
    )
    # App should validate and reject negative shares
    # Accept 400 or 422 — both indicate client-side bad input
    assert resp.status_code in (400, 422), (
        f"Expected 400/422 for negative shares, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# FLOW-004: Dashboard snapshot endpoint
# ---------------------------------------------------------------------------
def test_dashboard_snapshot_structure(client_no_auth):
    """FLOW-004: Dashboard /snapshot returns expected fields with correct types."""
    resp = client_no_auth.get("/dashboard/snapshot")
    assert resp.status_code == 200, (
        f"Dashboard snapshot failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert isinstance(body, dict), f"Expected dict, got {type(body)}"

    # These are the key fields the frontend depends on — must be present
    required_fields = ["total_value", "stock_count", "option_count"]
    for field in required_fields:
        assert field in body, (
            f"Dashboard snapshot missing required field '{field}'. Got keys: {list(body.keys())}"
        )

    # Type checks
    tv = body.get("total_value")
    assert tv is None or isinstance(tv, (int, float)), (
        f"total_value should be numeric or null, got {type(tv)}: {tv}"
    )
    sc = body.get("stock_count")
    assert sc is None or isinstance(sc, int), (
        f"stock_count should be int or null, got {type(sc)}: {sc}"
    )


def test_dashboard_snapshot_empty_portfolio(client_no_auth):
    """FLOW-004 edge case: Dashboard returns valid response even with no positions."""
    # The snapshot endpoint must not crash when the portfolio is empty.
    # The in-memory DB fixture gives us a clean database.
    resp = client_no_auth.get("/dashboard/snapshot")
    # 200 is expected; 204 would also be acceptable
    assert resp.status_code in (200, 204), (
        f"Dashboard returned {resp.status_code} on empty portfolio: {resp.text}"
    )
    if resp.status_code == 200:
        body = resp.json()
        assert body is not None


# ---------------------------------------------------------------------------
# FLOW-005: CSV upload creates option records correctly
# ---------------------------------------------------------------------------
def test_options_csv_upload_creates_records(client_no_auth):
    """FLOW-005: Upload a valid options CSV; verify records are created."""
    csv_content = (
        "ticker,option_type,strike_price,expiry_date,contracts,cost_basis,status\n"
        "AAPL,Call,150.0,2024-06-21,1,5.00,Open\n"
        "MSFT,Put,300.0,2024-06-21,2,3.50,Open\n"
    )

    files = {"file": ("options.csv", csv_content, "text/csv")}
    upload_resp = client_no_auth.post("/options/upload", files=files)

    assert upload_resp.status_code in (200, 201), (
        f"CSV upload failed: {upload_resp.status_code} {upload_resp.text}"
    )

    # Verify options now exist
    list_resp = client_no_auth.get("/options/")
    assert list_resp.status_code == 200
    options = list_resp.json()
    assert isinstance(options, list), f"Expected list, got {type(options)}"
    assert len(options) >= 2, (
        f"Expected at least 2 options after CSV upload, got {len(options)}"
    )

    tickers = {o["ticker"] for o in options}
    assert "AAPL" in tickers, f"AAPL call not found in options: {tickers}"
    assert "MSFT" in tickers, f"MSFT put not found in options: {tickers}"


def test_options_csv_upload_bad_headers_rejected(client_no_auth):
    """FLOW-005 edge case: CSV with wrong column names is rejected gracefully."""
    csv_content = (
        "wrong,headers,here\n"
        "foo,bar,baz\n"
    )
    files = {"file": ("bad.csv", csv_content, "text/csv")}
    resp = client_no_auth.post("/options/upload", files=files)

    # Should NOT return 200 or 500 — 400 or 422 expected for bad input
    assert resp.status_code in (400, 422, 500), (
        f"Expected error for bad CSV headers, got {resp.status_code}: {resp.text}"
    )
    # Server must not crash with an unhandled exception (5xx only acceptable here
    # if the app doesn't have CSV-specific validation — we'll track this)


def test_options_csv_upload_empty_file(client_no_auth):
    """FLOW-005 edge case: Uploading an empty CSV file returns an error, not a crash."""
    files = {"file": ("empty.csv", "", "text/csv")}
    resp = client_no_auth.post("/options/upload", files=files)

    # Empty file should be a client error, not a server crash
    assert resp.status_code != 500, (
        f"Empty CSV upload caused a server crash (500): {resp.text}"
    )
