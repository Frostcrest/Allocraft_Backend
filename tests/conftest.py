import os
import sys
import pathlib
import pytest
from fastapi.testclient import TestClient

# Enable local auth bypass for tests
os.environ["DISABLE_AUTH"] = "1"

# Ensure `from app import ...` works like when running under fastapi_project
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
FASTAPI_DIR = BACKEND_ROOT / "fastapi_project"
if str(FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIR))

# Change CWD so sqlite relative path is created inside fastapi_project
os.chdir(str(FASTAPI_DIR))

from fastapi_project.app.main import app  # type: ignore  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="session")
def test_client():
    return client
