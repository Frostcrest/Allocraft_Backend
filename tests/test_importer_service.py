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
    """scan_seed_folder must raise FileNotFoundError when the seed folder doesn't exist."""
    import os
    os.environ['SEED_DROP_DIR'] = 'nonexistent_folder_that_does_not_exist'
    with pytest.raises(FileNotFoundError, match="Seed folder not found"):
        ImporterService.scan_seed_folder(db)
