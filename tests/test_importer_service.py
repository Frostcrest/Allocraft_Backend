import pytest
from fastapi_project.app.services.importer_service import ImporterService
from fastapi_project.app.database import SessionLocal

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_scan_seed_folder_handles_missing(db):
    # Should raise FileNotFoundError if folder missing
    import os
    os.environ['SEED_DROP_DIR'] = 'nonexistent_folder'
    try:
        ImporterService.scan_seed_folder(db)
    except FileNotFoundError:
        assert True
    else:
        assert False, "Expected FileNotFoundError"
