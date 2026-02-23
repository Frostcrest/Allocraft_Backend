import os
import sys
import pathlib
import pytest
from fastapi.testclient import TestClient
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Enable local auth bypass for tests (existing tests rely on this)
os.environ["DISABLE_AUTH"] = "1"

# Ensure both import styles work:
#   from fastapi_project.app.X import ...   (BACKEND_ROOT in sys.path)
#   from app.X import ...                   (FASTAPI_DIR in sys.path)
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
FASTAPI_DIR = BACKEND_ROOT / "fastapi_project"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIR))

# NOTE: os.chdir() removed — use absolute paths in app config instead.
#       If sqlite relative path breaks, set DATABASE_URL env var to an absolute path.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{FASTAPI_DIR}/test_runner.db")

from app.main import app  # type: ignore  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app import models  # noqa: F401,E402

# --------------------------------------------------------------------------- #
# Legacy session-scoped client (DISABLE_AUTH=1, shared DB)                    #
# --------------------------------------------------------------------------- #
client = TestClient(app)


@pytest.fixture(scope="session")
def test_client():
    return client


# --------------------------------------------------------------------------- #
# In-memory SQLite engine (per-test isolation)                                #
# --------------------------------------------------------------------------- #
_TEST_DB_URL = "sqlite:///:memory:"

_test_engine = create_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once for the in-memory engine."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Isolated DB session: each test gets a clean slate via savepoint rollback.
    """
    conn = _test_engine.connect()
    tx = conn.begin()
    session = _TestingSession(bind=conn)
    nested = conn.begin_nested()  # savepoint

    yield session

    session.close()
    if nested.is_active:
        nested.rollback()
    tx.rollback()
    conn.close()


# --------------------------------------------------------------------------- #
# client_no_auth — DISABLE_AUTH=1 (auth is skipped entirely)                 #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client_no_auth(db_session: Session) -> Generator[TestClient, None, None]:
    """
    TestClient with auth fully disabled.  All endpoints are accessible without
    a token.  Uses an isolated in-memory DB session.
    """
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


# --------------------------------------------------------------------------- #
# client_with_auth — DISABLE_AUTH=0, real JWT required                        #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client_with_auth(db_session: Session, monkeypatch):
    """
    TestClient with auth ENABLED.  A test user is registered and a real JWT is
    obtained.  Returns (client, headers) tuple.

    Usage::
        def test_something(client_with_auth):
            client, headers = client_with_auth
            resp = client.get("/protected", headers=headers)
    """
    # Force DISABLE_AUTH off for both places that read it
    monkeypatch.setattr("app.routers.auth.DISABLE_AUTH", False)
    monkeypatch.setattr("app.dependencies.DISABLE_AUTH", False)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app, raise_server_exceptions=True) as c:
        # Register a fresh test user
        reg = c.post("/auth/register", json={
            "username": "auth_test_user",
            "email": "auth_test@example.com",
            "password": "S3cure!Pass99"
        })
        assert reg.status_code in (200, 201), f"Registration failed: {reg.text}"

        # Login and capture JWT
        login = c.post("/auth/login", data={
            "username": "auth_test_user",
            "password": "S3cure!Pass99"
        })
        assert login.status_code == 200, f"Login failed: {login.text}"
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        yield c, headers

    app.dependency_overrides.pop(get_db, None)
