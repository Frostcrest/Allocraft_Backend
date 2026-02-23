"""
Security tests for the authentication system.

Tests: AUTH-001 through AUTH-009

Policy: It is unacceptable to remove or edit these tests — they protect against
known vulnerabilities that were present in production code.
"""

import pytest


# ---------------------------------------------------------------------------
# AUTH-001: Valid login returns JWT access token
# ---------------------------------------------------------------------------
def test_valid_login_returns_jwt(client_no_auth):
    """AUTH-001: Login with valid credentials returns a JWT access_token."""
    # Register a user first
    client_no_auth.post(
        "/auth/register",
        json={"username": "auth001", "email": "auth001@test.com", "password": "ValidPass!1"}
    )

    response = client_no_auth.post(
        "/auth/login",
        data={"username": "auth001", "password": "ValidPass!1"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20  # should be a real JWT, not empty


# ---------------------------------------------------------------------------
# AUTH-002: Invalid password returns 401
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_password", [
    "wrongpassword",
    "",
    "' OR '1'='1",  # SQL injection attempt
    "ValidPass!1" + "x",  # one char off
])
def test_invalid_password_returns_401(client_no_auth, bad_password):
    """AUTH-002: Login with invalid password must return 401."""
    client_no_auth.post(
        "/auth/register",
        json={"username": "auth002", "email": "auth002@test.com", "password": "ValidPass!1"}
    )

    response = client_no_auth.post(
        "/auth/login",
        data={"username": "auth002", "password": bad_password}
    )
    assert response.status_code == 401, (
        f"Expected 401 for password {bad_password!r}, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# AUTH-003: Inactive user cannot log in
# ---------------------------------------------------------------------------
def test_inactive_user_cannot_login(client_no_auth, db_session):
    """AUTH-003: Deactivated user gets 401 even with correct password."""
    from app import models
    from app.utils.security import hash_password

    # Insert inactive user directly in the DB
    user = models.User(
        username="auth003_inactive",
        email="auth003@test.com",
        hashed_password=hash_password("GoodPass!1"),
        is_active=False,
        roles="user",
    )
    db_session.add(user)
    db_session.commit()

    response = client_no_auth.post(
        "/auth/login",
        data={"username": "auth003_inactive", "password": "GoodPass!1"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# AUTH-004: Tampered / expired / missing JWT is rejected
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_header", [
    {},                                                          # no token
    {"Authorization": "Bearer totally.not.a.jwt"},             # garbage JWT
    {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                       ".eyJzdWIiOiIxIiwiZXhwIjoxfQ"
                       ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"},  # expired
    {"Authorization": "NotBearer abc.def.ghi"},                # wrong scheme
])
def test_invalid_jwt_rejected(client_no_auth, bad_header, monkeypatch):
    """AUTH-004: Protected endpoint returns 401 for missing/invalid/expired JWT."""
    monkeypatch.setattr("app.routers.auth.DISABLE_AUTH", False)
    monkeypatch.setattr("app.dependencies.DISABLE_AUTH", False)

    response = client_no_auth.get("/users/me", headers=bad_header)
    assert response.status_code == 401, (
        f"Expected 401 for header {bad_header}, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# AUTH-005: No Frostcrest backdoor — CRITICAL regression test
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dangerous_username", [
    "frostcrest",
    "Frostcrest",
    "FROSTCREST",
    "frostcrest_admin",
    "admin_frostcrest",
])
def test_no_frostcrest_backdoor(client_no_auth, dangerous_username):
    """
    AUTH-005: A user whose username contains 'frostcrest' must NOT receive
    elevated admin privileges.  This test guards against the backdoor that
    existed in the original auth.py implementation.

    THE BACKDOOR CODE WAS:
        def _ensure_admin_for_frostcrest(user):
            if "frostcrest" in user.username.lower():
                user.roles = "admin,user"
    """
    reg = client_no_auth.post(
        "/auth/register",
        json={
            "username": dangerous_username,
            "email": f"{dangerous_username}@test.com",
            "password": "NoDoorForYou!1"
        }
    )
    # If registration succeeds, verify no admin role granted
    if reg.status_code in (200, 201):
        login = client_no_auth.post(
            "/auth/login",
            data={"username": dangerous_username, "password": "NoDoorForYou!1"}
        )
        assert login.status_code == 200
        # Check the /users/me endpoint to see the actual role
        token = login.json().get("access_token")
        me = client_no_auth.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        if me.status_code == 200:
            body = me.json()
            roles = body.get("roles", "")
            assert "admin" not in roles, (
                f"Frostcrest backdoor still active! Username '{dangerous_username}' "
                f"received admin role: {roles}"
            )
    # If registration is rejected (username policy), test passes trivially
    elif reg.status_code in (400, 422):
        pass  # username was rejected at validation — safe
    else:
        pytest.fail(f"Unexpected registration status: {reg.status_code} {reg.text}")


# ---------------------------------------------------------------------------
# AUTH-006: DISABLE_AUTH=0 enforces real auth on unprotected paths
# ---------------------------------------------------------------------------
def test_auth_enforced_when_disable_auth_off(client_no_auth, monkeypatch):
    """
    AUTH-006: With DISABLE_AUTH=0, requests to auth-protected endpoints
    without a token must return 401, not 200.
    """
    monkeypatch.setattr("app.routers.auth.DISABLE_AUTH", False)
    monkeypatch.setattr("app.dependencies.DISABLE_AUTH", False)

    # /users/me is a protected endpoint — must require a valid token
    response = client_no_auth.get("/users/me")
    assert response.status_code == 401, (
        f"Endpoint /users/me returned {response.status_code} with no token "
        f"and DISABLE_AUTH=0 — auth is not being enforced"
    )


# ---------------------------------------------------------------------------
# AUTH-007: Non-admin cannot access admin-only endpoints
# ---------------------------------------------------------------------------
def test_non_admin_cannot_access_admin_endpoint(client_with_auth):
    """AUTH-007: A regular user account gets 403 on admin-only routes."""
    client, headers = client_with_auth

    # /importer/scan is admin-only
    response = client.post("/importer/scan", headers=headers)
    assert response.status_code in (403, 404), (
        f"Expected 403 (or 404) for non-admin user on admin endpoint, "
        f"got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# AUTH-008: OAuth state is cryptographic random, not a sequential user ID
# ---------------------------------------------------------------------------
def test_oauth_state_is_random_not_sequential(client_no_auth):
    """
    AUTH-008: The Schwab OAuth /auth-url endpoint must return a state parameter
    that is a cryptographic random string (not a small integer like user ID).
    """
    response = client_no_auth.get("/schwab/auth-url")

    if response.status_code in (400, 401, 503):
        # Schwab not configured — skip gracefully
        pytest.skip("Schwab not configured in test environment")

    assert response.status_code == 200
    body = response.json()

    # Extract the 'state' query parameter from the auth_url
    auth_url = body.get("auth_url", "")
    assert "state=" in auth_url, "auth_url has no state parameter"

    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(auth_url)
    qs = parse_qs(parsed.query)
    state = qs.get("state", [None])[0]

    assert state is not None, "state param is null"
    assert len(state) >= 32, (
        f"OAuth state '{state}' is too short ({len(state)} chars) — "
        f"expected a cryptographic random token of >= 32 chars"
    )
    try:
        int(state)
        pytest.fail(
            f"OAuth state '{state}' is a plain integer — this is a CSRF vulnerability. "
            f"State must be a cryptographic random string, not a user ID."
        )
    except ValueError:
        pass  # Not a plain int — good


# ---------------------------------------------------------------------------
# AUTH-009: OAuth callback with unknown state is rejected
# ---------------------------------------------------------------------------
def test_oauth_callback_unknown_state_rejected(client_no_auth):
    """
    AUTH-009: Callback with an unknown/spoofed state token must be rejected
    (returns 400 or 401), not processed.
    """
    response = client_no_auth.get(
        "/schwab/callback",
        params={
            "code": "fake-auth-code-from-attacker",
            "state": "attacker-controlled-state-value-that-was-never-issued"
        }
    )

    assert response.status_code in (400, 401, 403), (
        f"OAuth callback with unknown state should be rejected, "
        f"but got {response.status_code}: {response.text}"
    )
